from __future__ import annotations

import subprocess
import sys
import tempfile

import click

from .update_check import is_update_available


def _upgrade_windows(latest: str) -> None:
    """Spawn a detached cmd window that waits for the exe to unlock, then pip-installs."""
    python_exe = sys.executable
    script = tempfile.NamedTemporaryFile(
        mode="w", suffix=".cmd", delete=False, prefix="sfdump_upgrade_"
    )
    script.write(f"""\
@echo off
echo Waiting for sfdump to exit...
timeout /t 2 /nobreak >nul
echo.
echo Installing sfdump {latest} ...
"{python_exe}" -m pip install --upgrade sfdump
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Successfully upgraded to {latest}.
) else (
    echo.
    echo pip install failed. See output above for details.
)
echo.
pause
""")
    script.close()

    CREATE_NEW_CONSOLE = 0x00000010
    subprocess.Popen(  # noqa: S603
        ["cmd.exe", "/c", script.name],
        creationflags=CREATE_NEW_CONSOLE,
    )
    click.echo("Upgrade started in a new window. This window will close.")
    raise SystemExit(0)


@click.command(name="upgrade")
@click.option("--check", is_flag=True, help="Only check for updates, don't install.")
def upgrade_cmd(check: bool) -> None:
    """Check for updates and upgrade sfdump from PyPI."""
    available, current, latest = is_update_available()

    click.echo(f"Current version: {current}")

    if not latest:
        click.echo("Could not reach PyPI to check for updates.")
        return

    click.echo(f"Latest version:  {latest}")

    if not available:
        click.echo("You are up to date.")
        return

    click.echo(f"Update available: {current} -> {latest}")

    if check:
        click.echo("Run 'sfdump upgrade' (without --check) to install.")
        return

    click.echo("Installing from PyPI ...")

    if sys.platform == "win32":
        _upgrade_windows(latest)
    else:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "sfdump"],
            check=False,
        )
        if result.returncode == 0:
            click.echo(f"Successfully upgraded to {latest}.")
        else:
            click.echo("pip install failed. See output above for details.", err=True)
            click.echo(
                "\nTo upgrade manually, run:\n  pip install --upgrade sfdump",
                err=True,
            )
            raise SystemExit(result.returncode)
