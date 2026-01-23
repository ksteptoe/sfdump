"""
Simplified CLI for SF data export and viewing.

This module provides the `sf` command with two simple subcommands:
- sf dump  - Export all data from Salesforce
- sf view  - Browse exported data in web viewer

For advanced options, use the full `sfdump` command.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .orchestrator import find_latest_export, launch_viewer, run_full_export


@click.group()
@click.version_option(package_name="sfdump")
def cli() -> None:
    """
    SF - Simple Salesforce Data Export & Viewer

    Export your Salesforce data and browse it offline.

    \b
    Quick start:
      sf dump     # Export everything from Salesforce
      sf view     # Browse your exported data

    For advanced options, use 'sfdump' instead.
    """
    pass


@cli.command()
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
def dump(retry: bool, verbose: bool) -> None:
    """
    Export all data from Salesforce.

    Downloads files (Attachments, Documents) and data (Accounts,
    Opportunities, Invoices, etc.) to ./exports/export-YYYY-MM-DD.

    \b
    Examples:
      sf dump           # Standard export
      sf dump --retry   # Export and retry any failed downloads
      sf dump -v        # Verbose output showing each object
    """
    try:
        result = run_full_export(
            retry=retry,
            verbose=verbose,
        )

        if not result.success:
            click.echo(f"Export failed: {result.error}", err=True)
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\nExport cancelled.")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
        file_count = sum(1 for _ in files_dir.rglob("*") if _.is_file()) if files_dir.exists() else 0
        csv_count = sum(1 for _ in csv_dir.glob("*.csv")) if csv_dir.exists() else 0
        has_db = db_path.exists()

        status_icon = "[ready]" if has_db else "[no db]"

        click.echo(f"\n  {export_path.name} {status_icon}")
        click.echo(f"    Path:    {export_path}")
        click.echo(f"    Files:   {file_count:,}")
        click.echo(f"    Objects: {csv_count}")

    latest = find_latest_export()
    if latest:
        click.echo()
        click.echo(f"Latest: {latest.name}")
        click.echo("Run 'sf view' to browse.")
    click.echo()


def main() -> None:
    """Entry point for the sf command."""
    cli()


if __name__ == "__main__":
    main()
