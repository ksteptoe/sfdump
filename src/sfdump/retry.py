"""
Retry helpers for missing Attachment and ContentVersion files.
"""

import csv
import logging
import os
from typing import Dict, List, Tuple

from tqdm import tqdm

_logger = logging.getLogger(__name__)


def load_missing_csv(path: str) -> List[Dict[str, str]]:
    """Load a missing-files CSV produced by verify-files."""
    rows = []
    if not os.path.exists(path):
        return rows

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def _attempt_download(api, rel_url: str, out_path: str) -> Tuple[bool, str]:
    """
    Attempt a single download.
    Returns: (success: bool, error_message: str)
    """
    try:
        api.download_path_to_file(rel_url, out_path)
        return True, ""
    except Exception as e:
        return False, str(e)


def _write_retry_results(path: str, rows: List[dict], fieldnames: List[str]) -> None:
    """Write the retry results to a CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def retry_missing_attachments(api, rows: List[dict], export_root: str, links_dir: str) -> None:
    """
    Retry missing legacy Attachment downloads.
    """
    if not rows:
        _logger.info("retry_missing_attachments: No missing attachment rows.")
        return

    results = []

    for r in tqdm(rows, desc="Retry Attachments"):
        attach_id = r.get("Id")
        rel_path = r.get("path") or ""
        out_path = os.path.join(export_root, rel_path) if rel_path else None

        # Reconstruct Body URL
        rel_url = f"/services/data/{api.api_version}/sobjects/Attachment/{attach_id}/Body"

        if not out_path:
            r["retry_status"] = "invalid-path"
            r["retry_error"] = "Missing path in metadata"
            results.append(r)
            continue

        # Ensure directory exists
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        success, err = _attempt_download(api, rel_url, out_path)
        r["retry_success"] = "true" if success else "false"
        r["retry_error"] = err

        if success:
            r["retry_status"] = "recovered"
        else:
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


def retry_missing_content_versions(api, rows: List[dict], export_root: str, links_dir: str) -> None:
    """
    Retry missing ContentVersion downloads.
    """
    if not rows:
        _logger.info("retry_missing_content_versions: No missing CV rows.")
        return

    results = []

    for r in tqdm(rows, desc="Retry ContentVersions"):
        cv_id = r.get("Id")
        rel_path = r.get("path") or ""
        out_path = os.path.join(export_root, rel_path) if rel_path else None

        # Reconstruct VersionData URL
        rel_url = f"/services/data/{api.api_version}/sobjects/ContentVersion/{cv_id}/VersionData"

        if not out_path:
            r["retry_status"] = "invalid-path"
            r["retry_error"] = "Missing path in metadata"
            results.append(r)
            continue

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        success, err = _attempt_download(api, rel_url, out_path)
        r["retry_success"] = "true" if success else "false"
        r["retry_error"] = err

        if success:
            r["retry_status"] = "recovered"
        else:
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
