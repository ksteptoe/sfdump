"""CLI command for listing records from the viewer DB."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from sfdump.viewer import list_records


@click.command(name="list-records")
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
        "Path to the SQLite database file to inspect. "
        "If omitted, --export-dir must be given and the DB is assumed at <export-dir>/meta/sfdata.db."
    ),
)
@click.option(
    "--object",
    "api_name",
    required=True,
    help="Salesforce API name of the object to list (e.g. Account, Opportunity).",
)
@click.option(
    "--where",
    "where_clause",
    required=False,
    help=("Optional SQL WHERE clause fragment (without 'WHERE'), " "e.g. \"Name LIKE '%Acme%'\"."),
)
@click.option(
    "--order-by",
    "order_by",
    required=False,
    help="Optional column name to order by (simple identifier only).",
)
@click.option(
    "--limit",
    "limit",
    type=int,
    default=20,
    show_default=True,
    help="Maximum number of records to show.",
)
def list_records_command(
    export_dir: Optional[Path],
    db_path: Optional[Path],
    api_name: str,
    where_clause: Optional[str],
    order_by: Optional[str],
    limit: int,
) -> None:
    """List records for an object in the viewer SQLite DB."""
    if db_path is None:
        if export_dir is None:
            raise click.ClickException("Either --db or --export-dir must be provided")
        db_path = export_dir / "meta" / "sfdata.db"

    try:
        result = list_records(
            db_path=db_path,
            api_name=api_name,
            where=where_clause,
            limit=limit,
            order_by=order_by,
        )
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    rows = result.rows
    if not rows:
        click.echo("No records found.")
        return

    click.echo(f"Object:   {result.sf_object.api_name}")
    click.echo(f"DB:       {db_path}")
    click.echo(f"Returned: {len(rows)} record(s)")
    click.echo("")

    # Decide which columns to show
    first = rows[0]
    columns = []
    for col in ("Id", "Name"):
        if col in first:
            columns.append(col)
    for extra in ("Email", "Title", "StageName", "Amount"):
        if extra in first and extra not in columns:
            columns.append(extra)
    if len(columns) < 2:
        for k in first.keys():
            if k not in columns:
                columns.append(k)
            if len(columns) >= 4:
                break

    # Header
    click.echo(" | ".join(columns))
    click.echo("-" * 80)
    for row in rows:
        values = [str(row.get(c, "")) for c in columns]
        click.echo(" | ".join(values))
