from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import click

from sfdump.indexing import OBJECTS, RELATIONSHIPS
from sfdump.viewer import inspect_sqlite_db


def _inspect_relationships(db_path: Path) -> list[str]:
    """Return human-readable lines describing relationship health for this DB.

    For each SFRelationship we check:
      - does the parent table exist (if parent != "*")?
      - does the child table exist?
      - does the child_field column exist on the child table?

    We don't look at data, only schema.
    """
    db_path = Path(db_path)

    if not db_path.exists():
        return ["(DB file does not exist; cannot inspect relationships)"]

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        # Discover tables present in this DB
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {name for (name,) in cur.fetchall()}

        lines: list[str] = []

        for rel in RELATIONSHIPS:
            parent_name = rel.parent
            child_name = rel.child

            parent_obj = OBJECTS.get(parent_name) if parent_name != "*" else None
            child_obj = OBJECTS.get(child_name)

            parent_table = parent_obj.table_name if parent_obj is not None else "*"
            child_table = (
                child_obj.table_name if child_obj is not None else f"(unknown:{child_name})"
            )

            status_parts: list[str] = []

            # Parent table existence (skip polymorphic parent="*")
            if parent_obj is not None:
                if parent_table in table_names:
                    status_parts.append("parent:OK")
                else:
                    status_parts.append(f"parent:MISSING_TABLE({parent_table})")
            else:
                status_parts.append("parent:polymorphic(*)")

            # Child table existence
            if child_obj is None:
                status_parts.append("child:UNKNOWN_OBJECT")
                # No point checking columns if we don't know the table name
                lines.append(
                    f"- {rel.name}: {parent_name} -> {child_name}.{rel.child_field} "
                    f"[{' | '.join(status_parts)}]"
                )
                continue

            if child_table not in table_names:
                status_parts.append(f"child:MISSING_TABLE({child_table})")
                lines.append(
                    f"- {rel.name}: {parent_name} -> {child_name}.{rel.child_field} "
                    f"[{' | '.join(status_parts)}]"
                )
                continue

            status_parts.append("child:OK")

            # Check child_field exists as a column on the child table
            cur.execute(f"PRAGMA table_info('{child_table}')")
            cols = {col_name for (_, col_name, *_rest) in cur.fetchall()}

            if rel.child_field in cols:
                status_parts.append("child_field:OK")
            else:
                status_parts.append(f"child_field:MISSING({rel.child_field})")

            lines.append(
                f"- {rel.name}: {parent_name}({parent_table}.Id) -> "
                f"{child_name}({child_table}.{rel.child_field}) "
                f"[{' | '.join(status_parts)}]"
            )

        return lines
    finally:
        conn.close()


@click.command(name="db-info")
@click.option(
    "-d",
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
        "If omitted, export-dir must be given and the DB is assumed at <export-dir>/meta/sfdata.db."
    ),
)
def db_info_command(export_dir: Optional[Path], db_path: Optional[Path]) -> None:
    """Show a summary of tables, row counts and relationship health in a SQLite viewer database."""
    if db_path is None:
        if export_dir is None:
            raise click.ClickException("Either --db or --export-dir must be provided")
        db_path = export_dir / "meta" / "sfdata.db"

    try:
        overview = inspect_sqlite_db(db_path)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"SQLite DB: {overview.path}")
    click.echo(f"Indexes:   {overview.index_count}")
    click.echo("")
    if not overview.tables:
        click.echo("No tables found.")
        return

    click.echo("Tables:")
    for t in overview.tables:
        click.echo(f"  - {t.name}: {t.row_count} rows")

    click.echo("")
    click.echo("Relationships:")
    rel_lines = _inspect_relationships(db_path)
    if not rel_lines:
        click.echo("  (no relationships defined in schema)")
    else:
        for line in rel_lines:
            click.echo(f"  {line}")
