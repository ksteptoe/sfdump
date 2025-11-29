# sfdump/audit/missing_files.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class AuditResult:
    export_root: Path
    failed_csv: Path
    summary_csv: Path
    total_attachments: int
    failed_count: int


def find_latest_export(root: Path) -> Path:
    exports = [d for d in root.iterdir() if d.is_dir()]
    if not exports:
        raise RuntimeError("No export directories found under ./exports")
    return sorted(exports, reverse=True)[0]


def run_audit(export_dir: Path) -> AuditResult:
    att_path = export_dir / "files" / "links" / "attachments.csv"
    if not att_path.exists():
        raise RuntimeError(f"attachments.csv not found at {att_path}")

    df = pd.read_csv(att_path, dtype=str).fillna("")

    failed = df[df["download_error"] != ""]
    total = len(df)
    failed_count = len(failed)

    meta_dir = export_dir / "meta"
    meta_dir.mkdir(exist_ok=True)

    # Write detailed CSV
    failed_csv = meta_dir / "attachments_download_failed.csv"
    failed.to_csv(failed_csv, index=False)

    # Parent object summary
    def parent_prefix(pid: str) -> str:
        return pid[:3] if isinstance(pid, str) else ""

    failed["parent_object_prefix"] = failed["ParentId"].apply(parent_prefix)
    summary = failed.groupby("parent_object_prefix").size().reset_index(name="count")

    summary_csv = meta_dir / "attachments_download_failed_summary.csv"
    summary.to_csv(summary_csv, index=False)

    return AuditResult(
        export_root=export_dir,
        failed_csv=failed_csv,
        summary_csv=summary_csv,
        total_attachments=total,
        failed_count=failed_count,
    )
