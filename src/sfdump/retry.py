"""
Retry helpers for missing Attachment and ContentVersion files.
"""

import csv
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from tqdm import tqdm

from .exceptions import RateLimitError

DEFAULT_MAX_WORKERS = 16

_logger = logging.getLogger(__name__)


def merge_recovered_into_metadata(
    original_csv: str,
    retry_csv: str,
    id_field: str = "Id",
    path_field: str = "path",
) -> int:
    """
    Merge recovered file paths from retry CSV back into original metadata CSV.

    After retry, files that were successfully recovered have paths in retry_csv
    but the original metadata CSV still has empty paths. This function updates
    the original CSV with paths from recovered files.

    Args:
        original_csv: Path to original metadata CSV (e.g., attachments.csv)
        retry_csv: Path to retry results CSV (e.g., attachments_missing_retry.csv)
        id_field: Field name for record ID
        path_field: Field name for file path

    Returns:
        Number of records updated
    """
    if not os.path.exists(original_csv) or not os.path.exists(retry_csv):
        return 0

    # Load retry results and build lookup of recovered paths
    recovered_paths: Dict[str, str] = {}
    with open(retry_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("retry_status") == "recovered":
                record_id = row.get(id_field, "")
                path = row.get(path_field, "")
                if record_id and path:
                    recovered_paths[record_id] = path

    if not recovered_paths:
        _logger.info("No recovered files to merge from %s", retry_csv)
        return 0

    # Load original CSV
    rows = []
    fieldnames = []
    with open(original_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # Update paths for recovered files
    updated_count = 0
    for row in rows:
        record_id = row.get(id_field, "")
        if record_id in recovered_paths:
            current_path = row.get(path_field, "")
            # Only update if currently empty
            if not current_path or current_path.strip() == "":
                row[path_field] = recovered_paths[record_id]
                updated_count += 1

    # Write back
    if updated_count > 0:
        with open(original_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        _logger.info(
            "Merged %d recovered paths from %s into %s",
            updated_count,
            retry_csv,
            original_csv,
        )

    return updated_count


def load_missing_csv(path: str) -> List[Dict[str, str]]:
    """Load a missing-files CSV produced by verify-files."""
    rows = []
    if not os.path.exists(path):
        return rows

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def _write_retry_results(path: str, rows: List[dict], fieldnames: List[str]) -> None:
    """Write the retry results to a CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def retry_missing_attachments(
    api, rows: List[dict], export_root: str, links_dir: str, max_workers: int = DEFAULT_MAX_WORKERS
) -> None:
    """
    Retry missing legacy Attachment downloads using parallel threads.

    Args:
        api: Salesforce API client
        rows: List of missing attachment rows from verify
        export_root: Root export directory
        links_dir: Directory for link CSVs
        max_workers: Number of parallel download threads (default 8)
    """
    if not rows:
        _logger.info("retry_missing_attachments: No missing attachment rows.")
        return

    results = []

    # First pass: prepare downloads and filter invalid rows
    to_download = []
    for r in rows:
        attach_id = r.get("Id")
        rel_path = r.get("path") or ""
        out_path = os.path.join(export_root, rel_path) if rel_path else None

        if not out_path:
            r["retry_status"] = "invalid-path"
            r["retry_error"] = "Missing path in metadata"
            results.append(r)
            continue

        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Reconstruct Body URL
        rel_url = f"/services/data/{api.api_version}/sobjects/Attachment/{attach_id}/Body"
        to_download.append((r, rel_url, out_path))

    # Parallel download phase
    if to_download:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(api.download_path_to_file, rel_url, out_path): (r, out_path)
                for r, rel_url, out_path in to_download
            }

            pbar = tqdm(
                as_completed(futures),
                total=len(futures),
                desc="        Attachments",
                unit="file",
                ncols=80,
            )

            for fut in pbar:
                r, out_path = futures[fut]
                try:
                    fut.result()
                    r["retry_success"] = "true"
                    r["retry_error"] = ""
                    r["retry_status"] = "recovered"
                except RateLimitError:
                    raise  # Stop immediately on rate limit
                except Exception as e:
                    err = str(e)
                    r["retry_success"] = "false"
                    r["retry_error"] = err
                    if "403" in err:
                        r["retry_status"] = "forbidden"
                    elif "404" in err:
                        r["retry_status"] = "not-found"
                    elif "Connection" in err or "RemoteDisconnected" in err:
                        r["retry_status"] = "connection-error"
                    else:
                        r["retry_status"] = "unknown"
                results.append(r)

    out_csv = os.path.join(links_dir, "attachments_missing_retry.csv")
    fieldnames = sorted({k for r in results for k in r.keys()})
    _write_retry_results(out_csv, results, fieldnames)

    _logger.info(
        "retry_missing_attachments: wrote retry results for %d rows → %s",
        len(results),
        out_csv,
    )


def retry_missing_content_versions(
    api, rows: List[dict], export_root: str, links_dir: str, max_workers: int = DEFAULT_MAX_WORKERS
) -> None:
    """
    Retry missing ContentVersion downloads using parallel threads.

    Args:
        api: Salesforce API client
        rows: List of missing content version rows from verify
        export_root: Root export directory
        links_dir: Directory for link CSVs
        max_workers: Number of parallel download threads (default 8)
    """
    if not rows:
        _logger.info("retry_missing_content_versions: No missing CV rows.")
        return

    results = []

    # First pass: prepare downloads and filter invalid rows
    to_download = []
    for r in rows:
        cv_id = r.get("Id")
        rel_path = r.get("path") or ""
        out_path = os.path.join(export_root, rel_path) if rel_path else None

        if not out_path:
            r["retry_status"] = "invalid-path"
            r["retry_error"] = "Missing path in metadata"
            results.append(r)
            continue

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Reconstruct VersionData URL
        rel_url = f"/services/data/{api.api_version}/sobjects/ContentVersion/{cv_id}/VersionData"
        to_download.append((r, rel_url, out_path))

    # Parallel download phase
    if to_download:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(api.download_path_to_file, rel_url, out_path): (r, out_path)
                for r, rel_url, out_path in to_download
            }

            pbar = tqdm(
                as_completed(futures),
                total=len(futures),
                desc="        Documents",
                unit="file",
                ncols=80,
            )

            for fut in pbar:
                r, out_path = futures[fut]
                try:
                    fut.result()
                    r["retry_success"] = "true"
                    r["retry_error"] = ""
                    r["retry_status"] = "recovered"
                except RateLimitError:
                    raise  # Stop immediately on rate limit
                except Exception as e:
                    err = str(e)
                    r["retry_success"] = "false"
                    r["retry_error"] = err
                    if "403" in err:
                        r["retry_status"] = "forbidden"
                    elif "404" in err:
                        r["retry_status"] = "not-found"
                    elif "Connection" in err or "RemoteDisconnected" in err:
                        r["retry_status"] = "connection-error"
                    else:
                        r["retry_status"] = "unknown"
                results.append(r)

    out_csv = os.path.join(links_dir, "content_versions_missing_retry.csv")
    fieldnames = sorted({k for r in results for k in r.keys()})
    _write_retry_results(out_csv, results, fieldnames)

    _logger.info(
        "retry_missing_content_versions: wrote retry results for %d rows → %s",
        len(results),
        out_csv,
    )
