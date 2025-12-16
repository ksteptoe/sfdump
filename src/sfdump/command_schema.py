# src/sfdump/command_schema.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

import click


def _auto_exports_dir(user_dir: Path | None) -> Path:
    """
    Determine the exports directory.

    Rules:
    - If user_dir is provided, use it.
    - Else, if current directory has CSV files, use current directory.
    - Else, look under ./exports for subdirs named 'export-*' that contain
      a 'csv' subdir with CSV files, and pick the latest by name.
    """
    if user_dir is not None:
        return user_dir

    cwd = Path.cwd()

    # 1) If running inside a CSV directory (current dir has *.csv), use that.
    if any(cwd.glob("*.csv")):
        return cwd

    exports_root = cwd / "exports"
    if exports_root.is_dir():
        # Look for exports/export-YYYY.../csv that actually contain CSVs
        candidates: list[Path] = []
        for child in exports_root.iterdir():
            if not child.is_dir() or not child.name.startswith("export-"):
                continue
            csv_dir = child / "csv"
            if csv_dir.is_dir() and any(csv_dir.glob("*.csv")):
                candidates.append(csv_dir)

        if candidates:
            candidates.sort(key=lambda p: p.parent.name)
            chosen = candidates[-1]
            click.secho(
                "WARNING: No --exports-dir provided and no CSV files in the "
                "current directory.\n"
                f"         Auto-selected latest export directory: {chosen}",
                fg="yellow",
                err=True,
            )
            return chosen

    raise click.ClickException(
        "Could not determine exports directory.\n"
        "Either run this command from a directory containing CSV files, or "
        "explicitly provide --exports-dir."
    )


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


def _sample_ids(csv_path: Path, max_samples: int) -> list[str]:
    """Sample up to max_samples non-empty Id values from a CSV."""
    header = _read_header(csv_path)
    try:
        id_index = header.index("Id")
    except ValueError as exc:
        raise click.ClickException(f"CSV {csv_path} has no 'Id' column") from exc

    samples: list[str] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        # skip header
        next(reader, None)
        for row in reader:
            if id_index >= len(row):
                continue
            value = row[id_index].strip()
            if not value:
                continue
            samples.append(value)
            if len(samples) >= max_samples:
                break

    if not samples:
        raise click.ClickException(f"No non-empty Id values found in {csv_path}")

    return samples


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
    default=None,
    show_default=False,
    help=(
        "Directory where object CSV files are stored. "
        "If omitted, uses the current directory if it contains CSV files, "
        "otherwise auto-detects the latest export under ./exports/export-*/csv."
    ),
)
def columns_cmd(csv_or_object: str, exports_dir: Path | None) -> None:
    """
    List the column headings of a CSV.

    CSV_OR_OBJECT can be:
    - a path to a CSV file (e.g. exports/Account.csv), or
    - a Salesforce object name (e.g. Account -> <exports-dir>/Account.csv).
    """
    resolved_dir = _auto_exports_dir(exports_dir)
    csv_path = _resolve_csv_path(csv_or_object, resolved_dir)
    _list_columns(csv_path)


# ---------------------------------------------------------------------------
# 2) list: list all CSVs + column counts
# ---------------------------------------------------------------------------
@schema_cmd.command("list")
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    show_default=False,
    help=(
        "Directory where object CSV files are stored. "
        "If omitted, uses the current directory if it contains CSV files, "
        "otherwise auto-detects the latest export under ./exports/export-*/csv."
    ),
)
def list_cmd(exports_dir: Path | None) -> None:
    """
    List all exported CSV files and their column counts.
    """
    resolved_dir = _auto_exports_dir(exports_dir)
    csv_files = list(_iter_csv_files(resolved_dir))
    if not csv_files:
        click.echo(f"No CSV files found in {resolved_dir}")
        return

    click.echo(f"Found {len(csv_files)} CSV files in {resolved_dir}")
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
    default=None,
    show_default=False,
    help=(
        "Directory where object CSV files are stored. "
        "If omitted, uses the current directory if it contains CSV files, "
        "otherwise auto-detects the latest export under ./exports/export-*/csv."
    ),
)
def inspect_cmd(csv_or_object: str, exports_dir: Path | None) -> None:
    """
    Inspect an object/CSV and highlight Id / lookup-like columns.

    CSV_OR_OBJECT can be a CSV path or object name.
    """
    resolved_dir = _auto_exports_dir(exports_dir)
    csv_path = _resolve_csv_path(csv_or_object, resolved_dir)
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
    default=None,
    show_default=False,
    help=(
        "Directory where object CSV files are stored. "
        "If omitted, uses the current directory if it contains CSV files, "
        "otherwise auto-detects the latest export under ./exports/export-*/csv."
    ),
)
def refs_cmd(target: str, exports_dir: Path | None) -> None:
    """
    Show which CSVs appear to reference a given object via *Id columns.

    TARGET can be a CSV path or an object name. We infer the object name from
    the CSV filename (e.g. 'Account.csv' -> 'Account') and then look for
    columns like '<ObjectName>Id' or ending with '<ObjectName>Id'.
    """
    resolved_dir = _auto_exports_dir(exports_dir)
    target_csv = _resolve_csv_path(target, resolved_dir)
    target_object = target_csv.stem  # e.g. 'Account' from 'Account.csv'
    suffix = f"{target_object}Id"

    csv_files = list(_iter_csv_files(resolved_dir))
    if not csv_files:
        click.echo(f"No CSV files found in {resolved_dir}")
        return

    references: Dict[Path, List[str]] = {}

    for path in csv_files:
        header = _read_header(path)
        matches = [col for col in header if col == suffix or col.endswith(suffix)]
        if matches:
            references[path] = matches

    click.echo(
        f"Searching for references to '{target_object}' "
        f"(columns matching '*{suffix}') in {resolved_dir}"
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


# ---------------------------------------------------------------------------
# 5) find-id: search for a specific Id value across CSVs
# ---------------------------------------------------------------------------


@schema_cmd.command("find-id")
@click.argument("csv_or_object", metavar="OBJECT_OR_CSV")
@click.argument("object_id", metavar="OBJECT_ID", required=False)
@click.option(
    "-d",
    "--exports-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    show_default=False,
    help=(
        "Directory where object CSV files are stored. "
        "If omitted, uses the current directory if it contains CSV files, "
        "otherwise auto-detects the latest export under ./exports/export-*/csv."
    ),
)
@click.option(
    "--all-columns",
    is_flag=True,
    help="Search all columns (not just Id/*Id columns).",
)
@click.option(
    "--include-self",
    is_flag=True,
    help="Also search the OBJECT's own CSV file (not just other objects).",
)
@click.option(
    "--sample-size",
    type=int,
    default=100,
    show_default=True,
    help="When OBJECT_ID is omitted, sample this many Ids from the object CSV.",
)
@click.option(
    "--min-matches",
    type=int,
    default=3,
    show_default=True,
    help=(
        "When OBJECT_ID is omitted, require at least this many distinct Ids in "
        "a column to treat it as a likely foreign key."
    ),
)
def find_id_cmd(
    csv_or_object: str,
    object_id: str | None,
    exports_dir: Path | None,
    all_columns: bool,
    include_self: bool,
    sample_size: int,
    min_matches: int,
) -> None:
    """
    Search for OBJECT_ID across CSVs or infer FK columns for an object.

    Modes:

      1) OBJECT_OR_CSV + OBJECT_ID:
         Search for that specific Id value across CSVs and show all matches.

         Example:
           sfdump schema find-id Opportunity 0065g00000ABC123

      2) OBJECT_OR_CSV only (OBJECT_ID omitted):
         Sample Ids from the object CSV and infer likely foreign key columns
         in other CSVs based on where those Ids appear.

         Example:
           sfdump schema find-id Opportunity
    """
    # Resolve exports dir (this is where your None was coming from before)
    resolved_dir = _auto_exports_dir(exports_dir)

    # Resolve the main object CSV
    target_csv = _resolve_csv_path(csv_or_object, resolved_dir)

    # Collect CSVs to search
    csv_files = list(_iter_csv_files(resolved_dir))
    if not include_self:
        # Exclude the target CSV from the search unless explicitly included
        try:
            target_resolved = target_csv.resolve()
            csv_files = [p for p in csv_files if p.resolve() != target_resolved]
        except OSError:
            csv_files = [p for p in csv_files if p != target_csv]

    if not csv_files:
        click.echo(f"No CSV files found in {resolved_dir}")
        return

    # ------------------------------------------------------------------
    # Mode 1: explicit OBJECT_ID -> row-level search (old behaviour)
    # ------------------------------------------------------------------
    if object_id is not None:
        mode_desc = "all columns" if all_columns else "Id/*Id columns only"
        click.echo(
            f"Searching for OBJECT_ID='{object_id}' in {len(csv_files)} CSV files "
            f"under {resolved_dir} ({mode_desc})"
        )
        click.echo()

        matches: dict[Path, list[tuple[int, int, str]]] = {}

        for path in csv_files:
            header = _read_header(path)

            if all_columns:
                search_cols = list(range(len(header)))
            else:
                search_cols = [
                    idx for idx, name in enumerate(header) if name == "Id" or name.endswith("Id")
                ]
                if not search_cols:
                    continue

            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row_idx, row in enumerate(reader, start=2):
                    for col_idx in search_cols:
                        if col_idx >= len(row):
                            continue
                        if row[col_idx] == object_id:
                            matches.setdefault(path, []).append((row_idx, col_idx, header[col_idx]))

        if not matches:
            click.echo("No matches found.")
            return

        click.echo("Matches:")
        click.echo()

        for path in sorted(matches.keys(), key=lambda p: p.name.lower()):
            click.echo(f"{path.name}:")
            for row_idx, col_idx, col_name in matches[path]:
                click.echo(f"  row {row_idx:6d}, col {col_idx:3d} ({col_name})")
            click.echo()
        return

    # ------------------------------------------------------------------
    # Mode 2: OBJECT_ID omitted -> infer FK columns via sampling
    # ------------------------------------------------------------------
    click.echo(
        f"No OBJECT_ID provided – inferring likely foreign key columns for "
        f"{target_csv.name} by sampling up to {sample_size} Ids."
    )

    sample_ids = _sample_ids(target_csv, sample_size)
    id_set = set(sample_ids)

    click.echo(
        f"Sampled {len(sample_ids)} distinct Ids from {target_csv.name}. "
        f"Scanning {len(csv_files)} CSV files..."
    )
    click.echo()

    # Path -> column name -> set of matched Ids
    fk_matches: dict[Path, dict[str, set[str]]] = {}

    for path in csv_files:
        header = _read_header(path)

        if all_columns:
            search_cols = list(range(len(header)))
        else:
            search_cols = [
                idx for idx, name in enumerate(header) if name == "Id" or name.endswith("Id")
            ]
            if not search_cols:
                continue

        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                for col_idx in search_cols:
                    if col_idx >= len(row):
                        continue
                    val = row[col_idx]
                    if val in id_set:
                        col_name = header[col_idx]
                        fk_matches.setdefault(path, {}).setdefault(col_name, set()).add(val)

    # Summarise FK candidates: require >= min_matches distinct Ids
    any_found = False
    click.echo(
        f"Columns with at least {min_matches} distinct matching Ids "
        f"are treated as likely foreign keys."
    )
    click.echo()

    for path in sorted(fk_matches.keys(), key=lambda p: p.name.lower()):
        col_map = fk_matches[path]
        strong_cols = {
            col_name: ids for col_name, ids in col_map.items() if len(ids) >= min_matches
        }
        if not strong_cols:
            continue

        any_found = True
        click.echo(f"{path.name}:")
        for col_name, ids in sorted(strong_cols.items()):
            click.echo(f"  - {col_name}: {len(ids)} distinct Ids")
        click.echo()

    if not any_found:
        click.echo(
            "No strong FK candidates found. Try increasing --sample-size or "
            "lowering --min-matches, or use --all-columns."
        )
