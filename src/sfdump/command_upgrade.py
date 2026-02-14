from __future__ import annotations

import subprocess
import sys
import tempfile

import click

from .update_check import get_latest_release, is_update_available


def _upgrade_windows(asset_url: str, latest: str) -> None:
    """Spawn a detached cmd window that waits for the exe to unlock, then pip-installs."""
    python_exe = sys.executable
    # Write a temp .cmd script
    script = tempfile.NamedTemporaryFile(
        mode="w", suffix=".cmd", delete=False, prefix="sfdump_upgrade_"
    )
    script.write(f"""\
@echo off
echo Waiting for sfdump to exit...
timeout /t 2 /nobreak >nul
echo.
echo Installing sfdump {latest} ...
"{python_exe}" -m pip install "{asset_url}"
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

    # Launch in a new visible console window
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
    """Check for updates and upgrade sfdump from the latest GitHub release."""
    available, current, latest = is_update_available()

    click.echo(f"Current version: {current}")

    if not latest:
        click.echo("Could not reach GitHub to check for updates.")
        return

    click.echo(f"Latest version:  {latest}")

    if not available:
        click.echo("You are up to date.")
        return

    click.echo(f"Update available: {current} -> {latest}")

    if check:
        click.echo("Run 'sfdump upgrade' (without --check) to install.")
        return

    release = get_latest_release()
    if release is None or not release.get("asset_url"):
        click.echo("Could not find a release asset to install.", err=True)
        click.echo("")
        click.echo("To upgrade manually, run setup.ps1 and choose option 1,")
        click.echo("or install the wheel directly with:")
        click.echo(
            f"  pip install https://github.com/ksteptoe/sfdump/releases/download/v{latest}/sfdump-{latest}-py3-none-any.whl"
        )
        raise SystemExit(1)

    asset_url = release["asset_url"]
    click.echo(f"Installing from {asset_url} ...")

    if sys.platform == "win32":
        _upgrade_windows(asset_url, latest)
    else:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", asset_url],
            check=False,
        )
        if result.returncode == 0:
            click.echo(f"Successfully upgraded to {latest}.")
        else:
            click.echo("pip install failed. See output above for details.", err=True)
            raise SystemExit(result.returncode)
