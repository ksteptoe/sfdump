"""CLI command to launch the Streamlit DB viewer."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click


@click.command(name="db-viewer")
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
        "Path to the SQLite database file to view. "
        "If omitted, --export-dir must be given and the DB is assumed at <export-dir>/meta/sfdata.db."
    ),
)
def db_viewer_command(export_dir: Optional[Path], db_path: Optional[Path]) -> None:
    """Launch the interactive Streamlit DB viewer for a viewer SQLite database."""
    if db_path is None:
        if export_dir is None:
            raise click.ClickException("Either --db or --export-dir must be provided")
        db_path = export_dir / "meta" / "sfdata.db"

    if not db_path.exists():
        raise click.ClickException(
            f"SQLite DB not found at {db_path}. "
            "Run 'sfdump build-db --export-dir <export-dir>' first."
        )

    # Check that Streamlit is available
    if importlib.util.find_spec("streamlit") is None:
        raise click.ClickException(
            "Streamlit is not installed in this environment. "
            "Install it with 'pip install streamlit' and try again."
        )

    # Resolve the path to the Streamlit app script inside the installed package
    try:
        mod = importlib.import_module("sfdump.viewer.db_app")
    except ImportError as exc:  # pragma: no cover - packaging issue
        raise click.ClickException(
            "Could not import sfdump.viewer.db_app; is sfdump installed correctly?"
        ) from exc

    script_path = Path(inspect.getfile(mod))

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script_path),
        "--",
        str(db_path),
    ]

    click.echo(f"Launching Streamlit viewer for {db_path} ...")
    try:
        # Do not use check=True; we want Streamlit's own exit code/messages.
        subprocess.run(cmd)
    except OSError as exc:  # pragma: no cover - runtime environment issue
        raise click.ClickException(f"Failed to launch Streamlit: {exc}") from exc
