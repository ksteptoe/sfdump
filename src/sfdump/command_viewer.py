from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


@click.command("viewer")
@click.option(
    "--exports-base",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Optional: Path to the exports/ directory. Defaults to OneDrive SF/exports.",
)
@click.option(
    "--open",
    "open_browser",
    is_flag=True,
    default=True,
    help="Automatically open the viewer in a browser (default: yes).",
)
def viewer_cmd(exports_base: Path | None, open_browser: bool) -> None:
    """
    Launch the SFdump Web Viewer (Streamlit-based UI) for browsing
    exported Salesforce files, indexes, and attachments.

    Finance-friendly: zero setup required beyond having export folders.
    """
    # ------------------------------------------------------------
    # 1. Locate the viewer script
    # ------------------------------------------------------------
    project_root = Path(__file__).resolve().parents[1]
    viewer_script = project_root / "src" / "sfdump" / "viewer" / "files_app.py"

    if not viewer_script.exists():
        raise click.ClickException(
            f"Viewer script not found:\n{viewer_script}\nEnsure src/sfdump/viewer/files_app.py exists."
        )

    # ------------------------------------------------------------
    # 2. Resolve exports base
    # ------------------------------------------------------------
    if exports_base is None:
        exports_base = Path.home() / "OneDrive - Example Company" / "SF" / "exports"

    exports_base = exports_base.expanduser().resolve()

    click.echo("Launching SFdump Viewer…")
    click.echo(f"- Viewer script:   {viewer_script}")
    click.echo(f"- Exports folder:  {exports_base}")

    if not exports_base.exists():
        raise click.ClickException(
            f"Exports directory does not exist:\n{exports_base}\n\n"
            "Run 'make export-all' first to generate your initial export."
        )

    # ------------------------------------------------------------
    # 3. Construct Streamlit command using same Python as sfdump
    # ------------------------------------------------------------
    python_exec = sys.executable  # respects venv

    cmd = [
        python_exec,
        "-m",
        "streamlit",
        "run",
        str(viewer_script),
        "--server.headless=false",
        "--",
        "--exports-base",
        str(exports_base),
    ]

    # ------------------------------------------------------------
    # 4. Run viewer
    # ------------------------------------------------------------
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        click.echo("\nViewer closed.")
