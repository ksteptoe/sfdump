"""CLI command for inspecting a SQLite viewer database."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from sfdump.viewer import inspect_sqlite_db


@click.command(name="db-info")
@click.option(
    "--export-dir",
    "export_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
    help=(
        "Root export directory (e.g. exports/export-YYYY-MM-DD). "
        "If provided and --db is not, the DB is assumed at <export-dir>/meta/sfdata.db."
    ),
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(dir_okay=False, path_type=Path),
    required=False,
    help=(
        "Path to the SQLite database file to inspect. "
        "If omitted, export-dir must be given and the DB is assumed at <export-dir>/meta/sfdata.db."
    ),
)
def db_info_command(export_dir: Optional[Path], db_path: Optional[Path]) -> None:
    """Show a summary of tables and row counts in a SQLite viewer database."""
    if db_path is None:
        if export_dir is None:
            raise click.ClickException("Either --db or --export-dir must be provided")
        db_path = export_dir / "meta" / "sfdata.db"

    try:
        overview = inspect_sqlite_db(db_path)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"SQLite DB: {overview.path}")
    click.echo(f"Indexes:   {overview.index_count}")
    click.echo("")
    if not overview.tables:
        click.echo("No tables found.")
        return

    click.echo("Tables:")
    for t in overview.tables:
        click.echo(f"  - {t.name}: {t.row_count} rows")
