# src/sfdump/command_schema.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

import click


def _resolve_csv_path(csv_or_object: str, exports_dir: Path) -> Path:
    """
    Resolve a CSV file from either:
    - an explicit path, or
    - a Salesforce object name + exports_dir (e.g. 'Account' -> exports/Account.csv)
    """
    as_path = Path(csv_or_object)
    if as_path.is_file():
        return as_path

    candidate = exports_dir / f"{csv_or_object}.csv"
    if candidate.is_file():
        return candidate

    raise click.ClickException(
        f"Could not find CSV for '{csv_or_object}'. "
        f"Tried '{as_path}' and '{candidate}'. "
        "Specify a full path or a known object name."
    )


def _read_header(csv_path: Path) -> list[str]:
    """Read and return the header row of a CSV file."""
    if not csv_path.exists():
        raise click.ClickException(f"File not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            # Use `from exc` or `from None` to satisfy Ruff B904
            raise click.ClickException(f"File is empty: {csv_path}") from exc

    return header


def _iter_csv_files(exports_dir: Path) -> Iterable[Path]:
    """Yield all .csv files in exports_dir, sorted by name."""
    if not exports_dir.exists():
        raise click.ClickException(f"Exports directory not found: {exports_dir}")
    return sorted(exports_dir.glob("*.csv"))


def _list_columns(csv_path: Path) -> None:
    """Print the column names and their index from the first row of a CSV."""
    header = _read_header(csv_path)

    click.echo(f"File: {csv_path}")
    click.echo(f"Number of columns: {len(header)}")
    click.echo()

    for idx, name in enumerate(header):
        click.echo(f"{idx:3d}: {name}")


@click.group(help="Tools for exploring exported CSV schema and relationships.")
def schema_cmd() -> None:
    """CLI group for schema-related commands."""
    pass


# ---------------------------------------------------------------------------
# 1) columns: list headers for one CSV/object
# ---------------------------------------------------------------------------


@schema_cmd.command("columns")
@click.argument("csv_or_object", metavar="CSV_OR_OBJECT")
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("exports"),
    show_default=True,
    help="Directory where object CSV files are stored.",
)
def columns_cmd(csv_or_object: str, exports_dir: Path) -> None:
    """
    List the column headings of a CSV.

    CSV_OR_OBJECT can be:
    - a path to a CSV file (e.g. exports/Account.csv), or
    - a Salesforce object name (e.g. Account -> <exports-dir>/Account.csv).
    """
    csv_path = _resolve_csv_path(csv_or_object, exports_dir)
    _list_columns(csv_path)


# ---------------------------------------------------------------------------
# 2) list: list all CSVs + column counts
# ---------------------------------------------------------------------------


@schema_cmd.command("list")
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("exports"),
    show_default=True,
    help="Directory where object CSV files are stored.",
)
def list_cmd(exports_dir: Path) -> None:
    """
    List all exported CSV files and their column counts.
    """
    csv_files = list(_iter_csv_files(exports_dir))
    if not csv_files:
        click.echo(f"No CSV files found in {exports_dir}")
        return

    click.echo(f"Found {len(csv_files)} CSV files in {exports_dir}")
    click.echo()

    for path in csv_files:
        try:
            header = _read_header(path)
            col_count = len(header)
        except click.ClickException as exc:
            # If a file is empty or unreadable, still show it but note the error
            click.echo(f"{path.name:<40} ERROR: {exc}")
            continue

        click.echo(f"{path.name:<40} cols={col_count:3d}")


# ---------------------------------------------------------------------------
# 3) inspect: show Id / lookup-ish columns separately
# ---------------------------------------------------------------------------


@schema_cmd.command("inspect")
@click.argument("csv_or_object", metavar="CSV_OR_OBJECT")
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("exports"),
    show_default=True,
    help="Directory where object CSV files are stored.",
)
def inspect_cmd(csv_or_object: str, exports_dir: Path) -> None:
    """
    Inspect an object/CSV and highlight Id / lookup-like columns.

    CSV_OR_OBJECT can be a CSV path or object name.
    """
    csv_path = _resolve_csv_path(csv_or_object, exports_dir)
    header = _read_header(csv_path)

    pk_cols: List[str] = []
    lookup_cols: List[str] = []
    other_cols: List[str] = []

    for name in header:
        if name == "Id":
            pk_cols.append(name)
        elif name.endswith("Id") and name != "Id":
            lookup_cols.append(name)
        else:
            other_cols.append(name)

    click.echo(f"File: {csv_path}")
    click.echo(f"Total columns: {len(header)}")
    click.echo()

    click.echo("Primary key columns (exact 'Id'):")
    if pk_cols:
        for c in pk_cols:
            click.echo(f"  - {c}")
    else:
        click.echo("  (none)")
    click.echo()

    click.echo("Likely lookup / foreign key columns (ending with 'Id'):")
    if lookup_cols:
        for c in lookup_cols:
            click.echo(f"  - {c}")
    else:
        click.echo("  (none)")
    click.echo()

    click.echo("Other columns:")
    if other_cols:
        for c in other_cols:
            click.echo(f"  - {c}")
    else:
        click.echo("  (none)")


# ---------------------------------------------------------------------------
# 4) refs: find which CSVs reference a given object via *Id columns
# ---------------------------------------------------------------------------


@schema_cmd.command("refs")
@click.argument("target", metavar="OBJECT_OR_CSV")
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("exports"),
    show_default=True,
    help="Directory where object CSV files are stored.",
)
def refs_cmd(target: str, exports_dir: Path) -> None:
    """
    Show which CSVs appear to reference a given object via *Id columns.

    TARGET can be a CSV path or an object name. We infer the object name from
    the CSV filename (e.g. 'Account.csv' -> 'Account') and then look for
    columns like '<ObjectName>Id' or ending in '<ObjectName>Id'.
    """
    target_csv = _resolve_csv_path(target, exports_dir)
    target_object = target_csv.stem  # e.g. 'Account' from 'Account.csv'
    suffix = f"{target_object}Id"

    csv_files = list(_iter_csv_files(exports_dir))
    if not csv_files:
        click.echo(f"No CSV files found in {exports_dir}")
        return

    references: Dict[Path, List[str]] = {}

    for path in csv_files:
        header = _read_header(path)
        matches = [col for col in header if col == suffix or col.endswith(suffix)]
        if matches:
            references[path] = matches

    click.echo(
        f"Searching for references to '{target_object}' "
        f"(columns matching '*{suffix}') in {exports_dir}"
    )
    click.echo()

    if not references:
        click.echo("No referencing columns found.")
        return

    for path, cols in sorted(references.items(), key=lambda kv: kv[0].name.lower()):
        click.echo(f"{path.name}:")
        for col in cols:
            click.echo(f"  - {col}")
        click.echo()
