"""
Backfill module for recovering missing files from master_documents_index.csv.

This module provides second-pass recovery for files that were never recorded
in content_versions.csv due to chunking. It uses master_documents_index.csv
to identify missing files and downloads them via the Salesforce API.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from tqdm import tqdm

from .exceptions import RateLimitError

if TYPE_CHECKING:
    from .api import SalesforceAPI

_logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """Result of a backfill operation."""

    total_missing: int
    downloaded: int
    failed: int
    skipped: int


def _safe_filename(stem: str, ext: str) -> str:
    """Create a safe filename from stem and extension."""
    stem = (stem or "").strip()
    stem = re.sub(r"[^\w\-. ()]+", "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if not stem:
        stem = "file"
    if len(stem) > 120:
        stem = stem[:120].rstrip()
    ext = (ext or "").lstrip(".")
    return f"{stem}.{ext}" if ext else stem


def load_missing_from_index(index_path: Path) -> list[dict]:
    """
    Load rows with blank local_path from master_documents_index.csv.

    Only returns rows where:
    - file_source == "File"
    - local_path is blank/empty
    - file_id starts with "069" (ContentDocument) or "068" (ContentVersion)

    Args:
        index_path: Path to master_documents_index.csv

    Returns:
        List of row dictionaries that need backfilling
    """
    if not index_path.exists():
        return []

    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    missing = [
        r
        for r in rows
        if (r.get("file_source") == "File")
        and (r.get("local_path") or "") == ""
        and (
            (r.get("file_id") or "").startswith("069") or (r.get("file_id") or "").startswith("068")
        )
    ]

    return missing


def resolve_content_version_id(api: SalesforceAPI, content_document_id: str) -> str | None:
    """
    Resolve ContentDocumentId (069...) to LatestPublishedVersionId (068...).

    Args:
        api: Connected SalesforceAPI instance
        content_document_id: The ContentDocument ID (starts with 069)

    Returns:
        The LatestPublishedVersionId, or None if not found

    Raises:
        RateLimitError: If API rate limit is exceeded
    """
    url = f"/services/data/{api.api_version}/sobjects/ContentDocument/{content_document_id}"
    try:
        resp = api._get(f"{api.instance_url}{url}")
        data = resp.json()
        return data.get("LatestPublishedVersionId")
    except RateLimitError:
        raise  # Re-raise to stop processing
    except Exception as e:
        _logger.debug("Failed to resolve %s: %s", content_document_id, e)
        return None


def _download_content_version(
    api: SalesforceAPI,
    content_version_id: str,
    target_path: Path,
) -> bool:
    """
    Download a ContentVersion's VersionData to a file.

    Args:
        api: Connected SalesforceAPI instance
        content_version_id: The ContentVersion ID (starts with 068)
        target_path: Where to save the file

    Returns:
        True if successful, False otherwise

    Raises:
        RateLimitError: If API rate limit is exceeded
    """
    rel_path = (
        f"/services/data/{api.api_version}/sobjects/ContentVersion/{content_version_id}/VersionData"
    )
    try:
        api.download_path_to_file(rel_path, str(target_path))
        return True
    except RateLimitError:
        raise  # Re-raise to stop processing
    except Exception as e:
        _logger.debug("Failed to download %s: %s", content_version_id, e)
        return False


def run_backfill(
    api: SalesforceAPI,
    export_root: Path,
    *,
    limit: int = 0,
    dry_run: bool = False,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    progress_interval: int = 100,
    show_progress: bool = True,
) -> BackfillResult:
    """
    Download missing files from master_documents_index.csv.

    This is the second-pass recovery that handles files not recorded in
    content_versions.csv due to chunking during the initial export.

    Args:
        api: Connected SalesforceAPI instance
        export_root: Root path of the export (contains meta/, files/, etc.)
        limit: Maximum files to process (0 = no limit)
        dry_run: If True, don't actually download, just report what would happen
        progress_callback: Optional callback(processed, total, downloaded, failed)
        progress_interval: How often to call progress_callback (every N files)
        show_progress: If True, show tqdm progress bar

    Returns:
        BackfillResult with counts of what happened
    """
    export_root = Path(export_root)
    index_path = export_root / "meta" / "master_documents_index.csv"
    files_root = export_root / "files"

    if not index_path.exists():
        _logger.warning("Master index not found: %s", index_path)
        return BackfillResult(total_missing=0, downloaded=0, failed=0, skipped=0)

    # Load all rows for update, and filter for missing
    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    if "local_path" not in fieldnames:
        _logger.error("master_documents_index.csv has no 'local_path' column")
        return BackfillResult(total_missing=0, downloaded=0, failed=0, skipped=0)

    # Build a lookup from file_id to row for efficient updates
    rows_by_id: dict[str, dict] = {}
    for row in all_rows:
        file_id = row.get("file_id", "")
        if file_id:
            rows_by_id[file_id] = row

    # Filter for missing files
    missing = [
        r
        for r in all_rows
        if (r.get("file_source") == "File")
        and (r.get("local_path") or "") == ""
        and (
            (r.get("file_id") or "").startswith("069") or (r.get("file_id") or "").startswith("068")
        )
    ]

    total_missing = len(missing)
    if total_missing == 0:
        return BackfillResult(total_missing=0, downloaded=0, failed=0, skipped=0)

    # Apply limit
    todo = missing if limit <= 0 else missing[:limit]
    _logger.info(
        "Backfill: %d missing files, processing %d (limit=%d, dry_run=%s)",
        total_missing,
        len(todo),
        limit,
        dry_run,
    )

    files_root.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    failed = 0
    skipped = 0

    # Use tqdm for visual progress
    iterator = todo
    if show_progress and not dry_run:
        iterator = tqdm(
            todo,
            desc="        Downloading",
            unit="file",
            leave=True,
            ncols=80,
        )

    for i, row in enumerate(iterator):
        file_id = str(row.get("file_id") or "").strip()
        name = str(row.get("file_name") or "").strip()
        ext = str(row.get("file_extension") or "").strip()

        # Resolve to ContentVersion ID if needed
        if file_id.startswith("069"):
            ver_id = resolve_content_version_id(api, file_id)
            if not ver_id:
                failed += 1
                _logger.debug("Could not resolve ContentDocument %s", file_id)
                continue
        elif file_id.startswith("068"):
            ver_id = file_id
        else:
            skipped += 1
            _logger.debug("Skipping unsupported file_id: %s", file_id)
            continue

        # Build target path
        subdir = files_root / file_id[:2]
        subdir.mkdir(parents=True, exist_ok=True)

        fname = _safe_filename(f"{file_id}_{name}", ext)
        rel_path = Path("files") / file_id[:2] / fname
        abs_path = export_root / rel_path

        # Skip if already exists
        if abs_path.exists():
            # Update the index with the path
            row["local_path"] = str(rel_path).replace("/", "\\")
            skipped += 1
            _logger.debug("File exists, updating path: %s", file_id)
            continue

        if dry_run:
            _logger.debug("DRY-RUN: would download %s -> %s", file_id, rel_path)
            continue

        # Download the file
        if _download_content_version(api, ver_id, abs_path):
            row["local_path"] = str(rel_path).replace("/", "\\")
            downloaded += 1
            _logger.debug("Downloaded: %s -> %s", file_id, rel_path)
        else:
            failed += 1

        # Legacy progress callback (for backward compat)
        processed = i + 1
        if progress_callback and (processed % progress_interval == 0 or processed == len(todo)):
            progress_callback(processed, len(todo), downloaded, failed)

    # Write updated index (atomic: write to temp, then rename)
    if not dry_run and (downloaded > 0 or skipped > 0):
        tmp = index_path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        tmp.replace(index_path)
        _logger.info("Updated master_documents_index.csv with %d new paths", downloaded + skipped)

    return BackfillResult(
        total_missing=total_missing,
        downloaded=downloaded,
        failed=failed,
        skipped=skipped,
    )
