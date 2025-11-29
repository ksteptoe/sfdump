# sfdump/commands/command_audit_missing_files.py
from __future__ import annotations

from pathlib import Path

import click
import pandas as pd


def _find_latest_export(root: Path) -> Path:
    """Return the most recent export directory under the given root."""
    dirs = [d for d in root.iterdir() if d.is_dir()]
    if not dirs:
        raise RuntimeError(f"No export directories found under: {root}")
    return sorted(dirs, reverse=True)[0]


@click.command(name="audit-missing-files")
@click.option(
    "--exports-root",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("./exports"),
    show_default=True,
)
def audit_missing_files_cmd(exports_root: Path):
    """
    Analyse the latest export and generate evidence for attachments
    that Salesforce refused to provide (403 errors etc.).
    """
    export_dir = _find_latest_export(exports_root)
    click.echo(f"Using export directory: {export_dir}")

    att_path = export_dir / "files" / "links" / "attachments.csv"
    if not att_path.exists():
        raise click.ClickException(f"attachments.csv not found at {att_path}")

    df = pd.read_csv(att_path, dtype=str).fillna("")
    failed = df[df["download_error"] != ""]

    meta_dir = export_dir / "meta"
    meta_dir.mkdir(exist_ok=True)

    # Write detailed evidence CSV
    failed_csv = meta_dir / "attachments_download_failed.csv"
    failed.to_csv(failed_csv, index=False)

    # Summary by parent object
    def parent_prefix(pid: str) -> str:
        return pid[:3] if isinstance(pid, str) else ""

    failed["parent_object_prefix"] = failed["ParentId"].apply(parent_prefix)
    summary = failed.groupby("parent_object_prefix").size().reset_index(name="count")

    summary_csv = meta_dir / "attachments_download_failed_summary.csv"
    summary.to_csv(summary_csv, index=False)

    click.echo("")
    click.echo("=== Missing File Audit Complete ===")
    click.echo(f"Total attachments: {len(df)}")
    click.echo(f"Failed downloads: {len(failed)}")
    click.echo("")
    click.echo(f"Details written to:  {failed_csv}")
    click.echo(f"Summary written to:  {summary_csv}")
