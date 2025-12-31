from __future__ import annotations

import sys
from pathlib import Path

import click


def _configure_stdio() -> None:
    # Force UTF-8 + never crash on unencodable output
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


@click.command("files-backfill")
@click.option(
    "--export-root",
    "-d",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Existing sfdump export root (contains meta/master_documents_index.csv).",
)
@click.option(
    "--instance-url",
    type=str,
    default=None,
    help="Salesforce instance URL override (otherwise from env/.env).",
)
@click.option(
    "--limit",
    type=int,
    default=0,
    show_default=True,
    help="Max number of missing files to download (0 = no limit).",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    show_default=True,
    help="Show what would be downloaded without making requests.",
)
def files_backfill_cmd(
    export_root: Path,
    instance_url: str | None,
    limit: int,
    dry_run: bool,
) -> None:
    """Backfill missing Salesforce Files into an existing export."""
    _configure_stdio()

    from sfdump.download_missing_files import run_backfill

    rc = run_backfill(
        export_root=export_root,
        instance_url=instance_url,
        limit=limit,
        dry_run=dry_run,
    )
    if rc not in (0, None):
        raise click.ClickException(f"files-backfill failed (exit={rc})")
