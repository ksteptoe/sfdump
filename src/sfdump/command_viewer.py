from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click


@click.command(name="viewer")
@click.option(
    "--export-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    required=True,
    help="sfdump export root directory (contains meta/).",
)
@click.option("--port", type=int, default=8501, show_default=True)
def viewer_cmd(export_root: Path, port: int) -> None:
    """
    Launch the Streamlit viewer for an export.
    """
    app_path = Path(__file__).resolve().parent / "viewer" / "app.py"
    env = os.environ.copy()
    env["SFDUMP_EXPORT_ROOT"] = str(export_root.resolve())

    cmd = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    raise SystemExit(subprocess.call(cmd, env=env))
