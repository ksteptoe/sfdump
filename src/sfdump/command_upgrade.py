from __future__ import annotations

import subprocess
import sys

import click

from .update_check import get_latest_release, is_update_available


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
    if release is None or not release.get("zip_url"):
        click.echo("Could not find a release ZIP asset to install.", err=True)
        raise click.Abort()

    zip_url = release["zip_url"]
    click.echo(f"Installing from {zip_url} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", zip_url],
        check=False,
    )
    if result.returncode == 0:
        click.echo(f"Successfully upgraded to {latest}.")
    else:
        click.echo("pip install failed. See output above for details.", err=True)
        raise SystemExit(result.returncode)
