"""
Simplified CLI for SF data export and viewing.

This module provides the `sf` command with two simple subcommands:
- sf dump  - Export all data from Salesforce
- sf view  - Browse exported data in web viewer

For advanced options, use the full `sfdump` command.
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path

import click

from .exceptions import RateLimitError
from .orchestrator import find_latest_export, launch_viewer, run_full_export
from .progress import BAR_EMPTY, BAR_FILLED


def _display_usage_info() -> bool:
    """Display API usage info. Returns True if successful, False otherwise."""
    try:
        from .api import SalesforceAPI

        api = SalesforceAPI()
        api.connect()

        try:
            limits = api.get_limits()
        except RateLimitError:
            click.echo()
            click.echo("Cannot query usage details - API limit exceeded.")
            return False

        daily = limits.get("DailyApiRequests", {})
        used = daily.get("Max", 0) - daily.get("Remaining", 0)
        max_limit = daily.get("Max", 0)
        remaining = daily.get("Remaining", 0)

        if max_limit > 0:
            pct_used = (used / max_limit) * 100
            pct_remaining = (remaining / max_limit) * 100

            click.echo("Current API Usage:")
            click.echo(f"  Used:      {used:>10,} ({pct_used:.1f}%)")
            click.echo(f"  Remaining: {remaining:>10,} ({pct_remaining:.1f}%)")
            click.echo(f"  Limit:     {max_limit:>10,}")
            click.echo()

            # Visual bar
            bar_width = 40
            filled = int((used / max_limit) * bar_width)
            bar = BAR_FILLED * filled + BAR_EMPTY * (bar_width - filled)
            click.echo(f"  [{bar}] {pct_used:.0f}%")
            return True
        return False
    except Exception:
        return False


# Track if first Ctrl+C was pressed
_interrupted_once = False


def _handle_sigint(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _interrupted_once
    if _interrupted_once:
        # Second Ctrl+C - force exit immediately
        click.echo("\n\nForce quit.", err=True)
        sys.exit(130)
    else:
        _interrupted_once = True
        click.echo("\n\nCancelling... (press Ctrl+C again to force quit)", err=True)
        # Raise KeyboardInterrupt to stop current operation
        raise KeyboardInterrupt()


@click.group()
@click.version_option(package_name="sfdump")
def cli() -> None:
    """
    SF - Simple Salesforce Data Export & Viewer

    Export your Salesforce data and browse it offline.

    \b
    First time setup:
      sf setup    # Configure Salesforce credentials
      sf test     # Verify connection works

    \b
    Daily use:
      sf dump     # Export everything from Salesforce
      sf view     # Browse your exported data
      sf status   # Show available exports
      sf usage    # Check API usage and limits

    For advanced options, use 'sfdump' instead.
    """
    pass


@cli.command()
@click.option(
    "--export-dir",
    "-d",
    type=click.Path(path_type=Path),
    help="Export directory (default: ./exports/export-YYYY-MM-DD).",
)
@click.option(
    "--retry",
    is_flag=True,
    default=False,
    help="Retry failed file downloads after initial export.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show detailed progress for each object.",
)
def dump(export_dir: Path | None, retry: bool, verbose: bool) -> None:
    """
    Export all data from Salesforce.

    Downloads files (Attachments, Documents) and data (Accounts,
    Opportunities, Invoices, etc.) to ./exports/export-YYYY-MM-DD.

    \b
    Examples:
      sf dump                       # Standard export
      sf dump --retry               # Export and retry any failed downloads
      sf dump -v                    # Verbose output showing each object
      sf dump -d ./my-export        # Export to custom directory
    """
    global _interrupted_once
    _interrupted_once = False

    # Install graceful Ctrl+C handler (works on Windows and Linux)
    original_handler = signal.signal(signal.SIGINT, _handle_sigint)

    try:
        result = run_full_export(
            export_path=export_dir,
            retry=retry,
            verbose=verbose,
        )

        if not result.success:
            click.echo(f"Export failed: {result.error}", err=True)
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo()
        click.echo("=" * 50)
        click.echo("Export cancelled.")
        click.echo("=" * 50)
        click.echo()
        click.echo("Partial data may have been saved to the export directory.")
        click.echo("Run 'sf dump' again to resume where you left off.")
        click.echo()
        sys.exit(130)
    except RateLimitError as e:
        click.echo()
        click.echo()
        click.echo("=" * 50)
        click.echo("Salesforce API Limit Reached")
        click.echo("=" * 50)
        click.echo()
        click.echo("Your Salesforce org has exceeded its daily API request limit.")
        click.echo()
        if e.used is not None and e.max_limit is not None:
            click.echo(f"  Usage: {e.used:,} / {e.max_limit:,} requests")
            pct = (e.used / e.max_limit) * 100 if e.max_limit > 0 else 0
            click.echo(f"  At {pct:.0f}% of daily limit")
            click.echo()
        else:
            # Try to fetch and display current usage
            _display_usage_info()
            click.echo()
        click.echo("The limit resets on a rolling 24-hour window.")
        click.echo("Oldest requests drop off continuously, so you can retry")
        click.echo("in 2-4 hours as capacity frees up.")
        click.echo()
        click.echo("Retry when capacity is available:")
        click.echo("  sf dump")
        click.echo()
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_handler)


@cli.command()
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
def view(path: Path | None) -> None:
    """
    Browse exported Salesforce data in a web viewer.

    If PATH is not specified, opens the most recent export.

    \b
    Examples:
      sf view                              # Open latest export
      sf view ./exports/export-2026-01-23  # Open specific export
    """
    try:
        launch_viewer(path)
    except KeyboardInterrupt:
        click.echo("\nViewer stopped.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """
    Show status of exports.

    Lists available exports and their details.
    """
    exports_dir = Path("./exports")

    if not exports_dir.exists():
        click.echo("No exports found.")
        click.echo("Run 'sf dump' to create an export.")
        return

    exports = sorted(
        [d for d in exports_dir.iterdir() if d.is_dir() and d.name.startswith("export-")],
        key=lambda d: d.name,
        reverse=True,
    )

    if not exports:
        click.echo("No exports found.")
        click.echo("Run 'sf dump' to create an export.")
        return

    click.echo()
    click.echo("Available Exports")
    click.echo("=" * 50)

    for export_path in exports[:10]:  # Show last 10
        db_path = export_path / "meta" / "sfdata.db"
        files_dir = export_path / "files"
        csv_dir = export_path / "csv"

        # Count files and CSVs
        file_count = (
            sum(1 for _ in files_dir.rglob("*") if _.is_file()) if files_dir.exists() else 0
        )
        csv_files = sorted(csv_dir.glob("*.csv")) if csv_dir.exists() else []
        csv_count = len(csv_files)
        has_db = db_path.exists()

        status_icon = "[ready]" if has_db else "[no db]"

        # Get example table names
        csv_names = [f.stem for f in csv_files[:3]]
        table_hint = f" ({', '.join(csv_names)}, ...)" if csv_names else ""

        click.echo(f"\n  {export_path.name} {status_icon}")
        click.echo(f"    Path:    {export_path}")
        click.echo(f"    Files:   {file_count:,}")
        click.echo(f"    Tables:  {csv_count}{table_hint}")

    latest = find_latest_export()
    if latest:
        click.echo()
        click.echo(f"Latest: {latest.name}")
        click.echo("Run 'sf view' to browse.")
    click.echo()


@cli.command()
def setup() -> None:
    """
    Configure Salesforce credentials.

    Creates a .env file with your Salesforce Connected App credentials.
    You'll need a Connected App configured in Salesforce Setup.
    """
    env_path = Path(".env")

    if env_path.exists():
        click.echo(f"Configuration file already exists: {env_path.resolve()}")
        if not click.confirm("Overwrite?"):
            click.echo("Setup cancelled.")
            return

    click.echo()
    click.echo("SF Setup - Configure Salesforce Credentials")
    click.echo("=" * 50)
    click.echo()
    click.echo("You need a Connected App in Salesforce.")
    click.echo("Go to: Setup > Apps > App Manager > New Connected App")
    click.echo()

    client_id = click.prompt("Consumer Key (SF_CLIENT_ID)")
    client_secret = click.prompt("Consumer Secret (SF_CLIENT_SECRET)", hide_input=True)
    username = click.prompt("Salesforce Username")
    password = click.prompt("Password + Security Token", hide_input=True)

    # Optional: login URL
    login_url = click.prompt(
        "Login URL",
        default="https://login.salesforce.com",
        show_default=True,
    )

    # Write .env file
    env_content = f"""# Salesforce Credentials for SF Data Export
# Generated by: sf setup

SF_CLIENT_ID={client_id}
SF_CLIENT_SECRET={client_secret}
SF_USERNAME={username}
SF_PASSWORD={password}
SF_LOGIN_URL={login_url}
"""

    env_path.write_text(env_content)
    click.echo()
    click.echo(f"Configuration saved to: {env_path.resolve()}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  sf dump    # Export your Salesforce data")
    click.echo("  sf view    # Browse exported data")
    click.echo()


@cli.command()
def test() -> None:
    """
    Test Salesforce connection.

    Verifies that credentials are configured correctly.
    """
    click.echo()
    click.echo("Testing Salesforce Connection")
    click.echo("=" * 50)

    env_path = Path(".env")
    if not env_path.exists():
        click.echo("No .env file found. Run 'sf setup' first.")
        sys.exit(1)

    click.echo(f"Config: {env_path.resolve()}")
    click.echo()

    try:
        from .api import SalesforceAPI

        click.echo("Connecting...", nl=False)
        api = SalesforceAPI()
        api.connect()
        click.echo(" OK")

        click.echo()
        click.echo(f"Instance: {api.instance_url}")

        # Quick test query
        click.echo("Testing query...", nl=False)
        list(api.query_all_iter("SELECT COUNT() FROM Account"))
        click.echo(" OK")

        click.echo()
        click.echo("Connection successful! Ready to export.")
        click.echo("Run 'sf dump' to start exporting.")

    except Exception as e:
        click.echo(" FAILED")
        click.echo()
        click.echo(f"Error: {e}")
        click.echo()
        click.echo("Check your credentials in .env and try again.")
        sys.exit(1)


@cli.command()
def usage() -> None:
    """
    Show Salesforce API usage and limits.

    Displays your current API request usage against daily limits.
    Useful to check before running a large export.
    """
    click.echo()
    click.echo("Salesforce API Usage")
    click.echo("=" * 50)

    env_path = Path(".env")
    if not env_path.exists():
        click.echo("No .env file found. Run 'sf setup' first.")
        sys.exit(1)

    try:
        from .api import SalesforceAPI

        click.echo("Connecting...", nl=False)
        api = SalesforceAPI()
        api.connect()
        click.echo(" OK")
        click.echo()

        # Get limits
        try:
            limits = api.get_limits()
        except RateLimitError:
            click.echo()
            click.echo("Status: LIMIT REACHED")
            click.echo()
            click.echo("Cannot query usage - API limit exceeded.")
            click.echo("The limit resets on a rolling 24-hour window.")
            click.echo("Try again in 2-4 hours.")
            click.echo()
            sys.exit(1)

        # Daily API requests
        daily = limits.get("DailyApiRequests", {})
        used = daily.get("Max", 0) - daily.get("Remaining", 0)
        max_limit = daily.get("Max", 0)
        remaining = daily.get("Remaining", 0)

        if max_limit > 0:
            pct_used = (used / max_limit) * 100
            pct_remaining = (remaining / max_limit) * 100

            click.echo("Daily API Requests (rolling 24-hour window):")
            click.echo(f"  Used:      {used:>10,} ({pct_used:.1f}%)")
            click.echo(f"  Remaining: {remaining:>10,} ({pct_remaining:.1f}%)")
            click.echo(f"  Limit:     {max_limit:>10,}")
            click.echo()

            # Visual bar
            bar_width = 40
            filled = int((used / max_limit) * bar_width)
            bar = BAR_FILLED * filled + BAR_EMPTY * (bar_width - filled)
            click.echo(f"  [{bar}] {pct_used:.0f}%")
            click.echo()

            # Status message
            if pct_used >= 100:
                click.echo("  Status: LIMIT REACHED - wait 2-4 hours to retry")
            elif pct_used >= 90:
                click.echo("  Status: WARNING - approaching limit")
            elif pct_used >= 75:
                click.echo("  Status: Moderate usage")
            else:
                click.echo("  Status: OK - plenty of capacity")
        else:
            click.echo("Could not retrieve API limits.")

        click.echo()

    except RateLimitError:
        click.echo()
        click.echo("Status: LIMIT REACHED")
        click.echo()
        click.echo("Cannot connect - API limit exceeded.")
        click.echo("The limit resets on a rolling 24-hour window.")
        click.echo("Try again in 2-4 hours.")
        click.echo()
        sys.exit(1)
    except Exception as e:
        click.echo(" FAILED")
        click.echo()
        click.echo(f"Error: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for the sf command."""
    cli()


if __name__ == "__main__":
    main()
