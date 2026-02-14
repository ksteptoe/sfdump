from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path

import click

_logger = logging.getLogger(__name__)


def _count_files_in_dir(dir_path: Path) -> int:
    """Count actual files (non-dirs) under a bucket-style directory (e.g. files/XX/...)."""
    if not dir_path.is_dir():
        return 0
    count = 0
    for child in dir_path.iterdir():
        if child.is_dir():
            for fp in child.iterdir():
                if not fp.is_dir():
                    count += 1
        elif child.is_file():
            count += 1
    return count


def _count_csv_rows(csv_path: Path) -> int:
    """Count data rows in a CSV (excludes header). Returns 0 if file missing/empty."""
    if not csv_path.exists():
        return 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # skip header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _fmt(n: int) -> str:
    """Format integer with thousands separator."""
    return f"{n:,}"


def _check_structure(export_root: Path) -> None:
    """Check 1: directory structure."""
    click.echo("\nStructure")
    for name in ("csv", "links", "meta"):
        d = export_root / name
        status = "OK" if d.is_dir() else "MISSING"
        click.echo(f"  {name + '/':<18}{status}")

    for name in ("files", "files_legacy"):
        d = export_root / name
        if d.is_dir():
            n = _count_files_in_dir(d)
            click.echo(f"  {name + '/':<18}{_fmt(n)} files")
        else:
            click.echo(f"  {name + '/':<18}not present")


def _check_metadata_coverage(export_root: Path) -> None:
    """Check 3: metadata CSV row counts vs files on disk."""
    click.echo("\nMetadata coverage")
    links_dir = export_root / "links"

    for csv_name, disk_dir in [
        ("attachments.csv", "files_legacy"),
        ("content_versions.csv", "files"),
    ]:
        csv_path = links_dir / csv_name
        rows = _count_csv_rows(csv_path)
        disk_count = _count_files_in_dir(export_root / disk_dir)

        if not csv_path.exists():
            click.echo(f"  {csv_name:<26}not found")
            continue

        if disk_count == 0:
            status = "OK"
        elif rows >= disk_count:
            status = "OK"
        else:
            status = "INCOMPLETE"

        click.echo(
            f"  {csv_name:<26}{_fmt(rows)} rows  ({_fmt(disk_count)} files on disk)  {status}"
        )


def _check_index(export_root: Path) -> tuple[int, int, int]:
    """Check 4: master_documents_index.csv path health.

    Returns (total, missing_path, path_not_on_disk).
    """
    click.echo("\nDocuments index (master_documents_index.csv)")
    index_path = export_root / "meta" / "master_documents_index.csv"

    if not index_path.exists():
        click.echo("  File not found — run 'sf dump docs-index' first.")
        return 0, 0, 0

    total = 0
    with_path = 0
    missing_path = 0
    path_not_on_disk = 0

    with index_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            lp = (row.get("local_path") or "").strip()
            if not lp:
                missing_path += 1
            else:
                with_path += 1
                if not (export_root / lp).exists():
                    path_not_on_disk += 1

    click.echo(f"  Total rows:         {_fmt(total)}")
    click.echo(f"  With local_path:    {_fmt(with_path)}")

    if missing_path > 0:
        click.echo(f"  Missing local_path: {_fmt(missing_path):<12} NEEDS REBUILD")
    else:
        click.echo(f"  Missing local_path: {_fmt(missing_path)}")

    if path_not_on_disk > 0:
        click.echo(f"  Paths not on disk:  {_fmt(path_not_on_disk):<12} WARN")
    else:
        click.echo(f"  Paths not on disk:  {_fmt(path_not_on_disk):<12} OK")

    return total, missing_path, path_not_on_disk


def _check_database(export_root: Path) -> tuple[int, int, int]:
    """Check 5: sfdata.db record_documents path health.

    Returns (total, missing_path, path_not_on_disk).
    """
    click.echo("\nDatabase (sfdata.db)")
    db_path = export_root / "meta" / "sfdata.db"

    if not db_path.exists():
        click.echo("  Database not found — run 'sf dump build-db' first.")
        return 0, 0, 0

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='record_documents'")
        if not cur.fetchone():
            click.echo("  record_documents table not found.")
            return 0, 0, 0

        cur.execute("SELECT COUNT(*) FROM record_documents")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM record_documents WHERE path IS NULL OR TRIM(path) = ''")
        missing_path = cur.fetchone()[0]
        with_path = total - missing_path

        # Check paths on disk
        path_not_on_disk = 0
        cur.execute("SELECT path FROM record_documents WHERE path IS NOT NULL AND TRIM(path) != ''")
        for (p,) in cur.fetchall():
            if not (export_root / p).exists():
                path_not_on_disk += 1

        click.echo(f"  record_documents:   {_fmt(total)} rows")
        click.echo(f"  With path:          {_fmt(with_path)}")

        if missing_path > 0:
            click.echo(f"  Missing path:       {_fmt(missing_path):<12} WARN")

        if path_not_on_disk > 0:
            click.echo(f"  Paths not on disk:  {_fmt(path_not_on_disk):<12} WARN")
        else:
            click.echo(f"  Paths not on disk:  {_fmt(path_not_on_disk):<12} OK")

    finally:
        conn.close()

    return total, missing_path, path_not_on_disk


@click.command(name="check-export")
@click.option(
    "--export-root",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Export root directory (contains csv/, links/, meta/).",
)
@click.option("--fix", is_flag=True, default=False, help="Rebuild indexes to fix path issues.")
@click.option("-v", "--verbose", count=True)
def check_export_cmd(export_root: Path, fix: bool, verbose: int) -> None:
    """Check the integrity of an export and optionally fix index issues."""
    export_root = export_root.resolve()
    click.echo(f"Export: {export_root}")

    # 1. Directory structure
    _check_structure(export_root)

    # 2–3. Metadata coverage
    _check_metadata_coverage(export_root)

    # 4. Index path health
    idx_total, idx_missing, idx_bad = _check_index(export_root)

    # 5. Database health
    db_total, db_missing, db_bad = _check_database(export_root)

    needs_fix = idx_missing > 0 or idx_bad > 0 or db_missing > 0 or db_bad > 0

    if fix and needs_fix:
        click.echo("\n--- Rebuilding ---")

        # Rebuild master_documents_index.csv
        from .command_docs_index import _build_master_index

        click.echo("Rebuilding master_documents_index.csv ...")
        _build_master_index(export_root)
        click.echo("Done.")

        # Rebuild record_documents table
        db_path = export_root / "meta" / "sfdata.db"
        if db_path.exists():
            from .indexing.build_record_documents import build_record_documents

            click.echo("Rebuilding record_documents table ...")
            build_record_documents(db_path, export_root)
            click.echo("Done.")

        # Re-run checks to show "after" numbers
        click.echo("\n--- After fix ---")
        _check_index(export_root)
        _check_database(export_root)
    elif fix and not needs_fix:
        click.echo("\nNo issues found — nothing to fix.")
    elif needs_fix:
        click.echo("\nRun with --fix to rebuild the documents index and database.")
