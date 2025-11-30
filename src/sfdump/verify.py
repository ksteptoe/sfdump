"""
Verification helpers for exported files.
"""

import csv
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

_logger = logging.getLogger(__name__)


def _sha256_of_file(path: str) -> str:
    """Compute SHA256 of a file with buffered reading."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_csv(path: str) -> List[Dict[str, str]]:
    """Load CSV into a list of dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_csv(path: str, rows: List[dict], fieldnames: List[str]) -> None:
    """Write rows to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _verify_rows(rows: List[dict], export_root: str) -> Tuple[List[dict], List[dict]]:
    """
    Given metadata rows (each with 'path' and 'sha256'), check for:
      - Missing files
      - Corrupt files (SHA mismatch)
    Returns (missing_rows, corrupt_rows)
    """
    missing = []
    corrupt = []

    for r in rows:
        rel = r.get("path") or ""
        sha_expected = (r.get("sha256") or "").strip().lower()

        if not rel:
            r["verify_error"] = "missing-path-field"
            missing.append(r)
            continue

        abs_path = os.path.join(export_root, rel)
        if not os.path.exists(abs_path):
            r["verify_error"] = "file-not-found"
            missing.append(r)
            continue

        if os.path.getsize(abs_path) == 0:
            r["verify_error"] = "zero-size-file"
            missing.append(r)
            continue

        # SHA256 check if present
        if sha_expected:
            try:
                sha_actual = _sha256_of_file(abs_path)
                if sha_actual.lower() != sha_expected:
                    r["sha256_actual"] = sha_actual
                    r["verify_error"] = "sha256-mismatch"
                    corrupt.append(r)
            except Exception as e:
                r["verify_error"] = f"sha256-error: {e}"
                corrupt.append(r)
        else:
            # No sha256 in metadata → treat as missing integrity data
            r["verify_error"] = "sha256-missing"
            corrupt.append(r)

    return missing, corrupt


def verify_attachments(meta_csv: str, export_root: str) -> None:
    """Verify exported legacy Attachment binaries."""
    rows = _load_csv(meta_csv)
    missing, corrupt = _verify_rows(rows, export_root)

    links_dir = os.path.dirname(meta_csv)

    missing_csv = os.path.join(links_dir, "attachments_missing.csv")
    corrupt_csv = os.path.join(links_dir, "attachments_corrupt.csv")

    if missing:
        _write_csv(missing_csv, missing, sorted(missing[0].keys()))
        _logger.warning("Attachment verification: %d missing files → %s", len(missing), missing_csv)
    else:
        _logger.info("Attachment verification: no missing files.")

    if corrupt:
        _write_csv(corrupt_csv, corrupt, sorted(corrupt[0].keys()))
        _logger.warning("Attachment verification: %d corrupt files → %s", len(corrupt), corrupt_csv)
    else:
        _logger.info("Attachment verification: no corrupt files.")


def verify_content_versions(meta_csv: str, export_root: str) -> None:
    """Verify exported ContentVersion binaries."""
    rows = _load_csv(meta_csv)
    missing, corrupt = _verify_rows(rows, export_root)

    links_dir = os.path.dirname(meta_csv)

    missing_csv = os.path.join(links_dir, "content_versions_missing.csv")
    corrupt_csv = os.path.join(links_dir, "content_versions_corrupt.csv")

    if missing:
        _write_csv(missing_csv, missing, sorted(missing[0].keys()))
        _logger.warning(
            "ContentVersion verification: %d missing files → %s", len(missing), missing_csv
        )
    else:
        _logger.info("ContentVersion verification: no missing files.")

    if corrupt:
        _write_csv(corrupt_csv, corrupt, sorted(corrupt[0].keys()))
        _logger.warning(
            "ContentVersion verification: %d corrupt files → %s", len(corrupt), corrupt_csv
        )
    else:
        _logger.info("ContentVersion verification: no corrupt files.")


def load_missing_csv(path: Path) -> list[dict]:
    """
    Load missing-attachments or retry CSV into a list of dicts.
    Returns an empty list if the file doesn't exist.
    """
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def build_cfo_report(export_dir: Path, redact: bool = False) -> str:
    """
    Build CFO audit report markdown string summarising missing and retry files.
    The report can later be included into Sphinx documentation or converted to PDF.
    """
    export_dir = Path(export_dir)
    links = export_dir / "links"

    missing_csv = links / "attachments_missing.csv"
    retry_csv = links / "attachments_missing_retry.csv"

    missing_rows = load_missing_csv(missing_csv)
    retry_rows = load_missing_csv(retry_csv)

    md = []
    md.append("# CFO Forensic Audit Report\n")
    md.append("## Summary\n")

    md.append(f"- Missing attachments found: **{len(missing_rows)}**")
    md.append(f"- Retry attempts recorded: **{len(retry_rows)}**")

    recovered = [r for r in retry_rows if r.get("retry_status") == "recovered"]
    unrecovered = [r for r in retry_rows if r.get("retry_status") != "recovered"]
    md.append(f"- Files recovered on retry: **{len(recovered)}**")
    md.append(f"- Still missing after retry: **{len(unrecovered)}**\n")

    # Detailed Missing Files
    md.append("## Missing Attachments\n")
    if missing_rows:
        md.append("| Id | ParentId | Name |")
        md.append("| --- | --- | --- |")
        for row in missing_rows:
            name = "[REDACTED]" if redact else row.get("Name", "")
            md.append(f"| {row.get('Id','')} | {row.get('ParentId','')} | {name} |")
    else:
        md.append("No missing attachments detected.\n")

    # Retry Results
    md.append("\n## Retry Results\n")
    if retry_rows:
        md.append("| Id | Status | Error |")
        md.append("| --- | --- | --- |")
        for row in retry_rows:
            error = (row.get("retry_error") or "").replace("|", "/")
            md.append(f"| {row.get('Id','')} | {row.get('retry_status','')} | {error} |")
    else:
        md.append("No retry data available.\n")

    return "\n".join(md) + "\n"
