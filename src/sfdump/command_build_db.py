"""CLI command for building a SQLite viewer database from CSV exports.

This module defines a Click command that wraps the core
``sfdump.viewer.build_sqlite_from_export`` function. It is intentionally
not wired into the top-level CLI group here; that wiring happens in
``sfdump.cli`` so this module stays reusable and easy to test.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from sfdump.viewer import build_sqlite_from_export

LOG = logging.getLogger(__name__)


@click.command(name="build-db")
@click.option(
    "--export-dir",
    "export_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing CSV exports for Salesforce objects.",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Path to the SQLite database file to create.",
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
    db_path: Path,
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

    LOG.info("Building SQLite viewer database")
    LOG.info("  export_dir: %s", export_dir)
    LOG.info("  db_path:    %s", db_path)
    LOG.info("  overwrite:  %s", overwrite)

    build_sqlite_from_export(
        export_dir=export_dir,
        db_path=db_path,
        overwrite=overwrite,
        logger=LOG,
    )

    click.echo(f"SQLite viewer database created at {db_path}")
