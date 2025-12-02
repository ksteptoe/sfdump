"""CLI command for building a SQLite viewer database from CSV exports.

This module defines a Click command that wraps the core
``sfdump.viewer.build_sqlite_from_export`` function.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import click

from sfdump.viewer import build_sqlite_from_export

LOG = logging.getLogger(__name__)


@click.command(name="build-db")
@click.option(
    "--export-dir",
    "export_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help=(
        "Root export directory (e.g. exports/export-YYYY-MM-DD). "
        "Object CSVs are expected under csv/, files/objects/, or objects/."
    ),
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(dir_okay=False, path_type=Path),
    required=False,
    default=None,
    help=(
        "Path to the SQLite database file to create. "
        "Defaults to <export-dir>/meta/sfdata.db if not provided."
    ),
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="Whether to overwrite an existing SQLite database file.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (can be used multiple times).",
)
def build_db_command(
    export_dir: Path,
    db_path: Optional[Path],
    overwrite: bool,
    verbose: int,
) -> None:
    """Build a SQLite database for offline viewing of exported Salesforce data."""
    # Simple logging level control; can later be unified with any global setup.
    if verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")

    # Default DB location lives under the chosen export
    if db_path is None:
        db_path = export_dir / "meta" / "sfdata.db"

    LOG.info("Building SQLite viewer database")
    LOG.info("  export_dir: %s", export_dir)
    LOG.info("  db_path:    %s", db_path)
    LOG.info("  overwrite:  %s", overwrite)

    try:
        build_sqlite_from_export(
            export_dir=export_dir,
            db_path=db_path,
            overwrite=overwrite,
            logger=LOG,
        )
    except FileExistsError as exc:
        # Let Click present this nicely
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        # e.g. no CSVs found, wrong layout, etc.
        raise click.ClickException(str(exc)) from exc

    click.echo(f"SQLite viewer database created at {db_path}")
