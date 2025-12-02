"""CLI command for viewing a record and its children from the viewer DB."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from sfdump.viewer import get_record_with_children


@click.command(name="view-record")
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
    help="Salesforce API name of the parent object (e.g. Account, Opportunity).",
)
@click.option(
    "--id",
    "record_id",
    required=True,
    help="Id of the parent record to view.",
)
@click.option(
    "--max-children",
    "max_children",
    type=int,
    default=20,
    show_default=True,
    help="Maximum number of child records to show per relationship.",
)
def view_record_command(
    export_dir: Optional[Path],
    db_path: Optional[Path],
    api_name: str,
    record_id: str,
    max_children: int,
) -> None:
    """Display a record and its direct children based on known relationships."""
    if db_path is None:
        if export_dir is None:
            raise click.ClickException("Either --db or --export-dir must be provided")
        db_path = export_dir / "meta" / "sfdata.db"

    try:
        result = get_record_with_children(
            db_path=db_path,
            api_name=api_name,
            record_id=record_id,
            max_children_per_rel=max_children,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    parent = result.parent
    click.echo(f"DB:      {db_path}")
    click.echo(f"Object:  {parent.sf_object.api_name}")
    click.echo(f"Record:  {parent.data.get(parent.sf_object.id_field, record_id)}")
    click.echo("Fields:")
    # Sorted keys for stable output
    for key in sorted(parent.data.keys()):
        click.echo(f"  {key}: {parent.data[key]}")

    if not result.children:
        click.echo("")
        click.echo("No child records found for this object.")
        return

    click.echo("")
    click.echo("Children:")
    for collection in result.children:
        rel = collection.relationship
        child_obj = collection.sf_object
        click.echo(
            f"- {child_obj.api_name} via {rel.child_field} "
            f"(relationship: {rel.name}, {len(collection.records)} record(s))"
        )
        for rec in collection.records:
            summary_parts = []
            if "Id" in rec:
                summary_parts.append(f"Id={rec['Id']}")
            if "Name" in rec:
                summary_parts.append(f"Name={rec['Name']}")
            if not summary_parts:
                # Fallback: first few fields
                for k in list(rec.keys())[:3]:
                    summary_parts.append(f"{k}={rec[k]}")
            click.echo("    - " + ", ".join(summary_parts))
