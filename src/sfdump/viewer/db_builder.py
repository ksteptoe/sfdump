"""SQLite database builder for offline Salesforce exports.

This module turns a directory of CSV exports into a single SQLite database,
using the object and relationship metadata defined in ``sfdump.indexing`` and
the SQLite-oriented schema helpers in ``sfdump.viewer.sqlite_schema``.

It does *not* define any CLI; callers are expected to invoke
``build_sqlite_from_export`` directly. A Click command wraps this in
``sfdump.command_build_db``.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from sfdump.indexing import SFObject, iter_objects

from .sqlite_schema import (
    SqliteIndexConfig,
    SqliteTableConfig,
    default_index_configs,
    default_table_configs,
)

LOG = logging.getLogger(__name__)


def _find_csv_for_object(
    export_root: Path, obj: SFObject, table_cfg: SqliteTableConfig
) -> Optional[Path]:
    """Best-effort resolution of the CSV file for a given object.

    We try a small set of conventional filenames relative to ``export_root``.
    If none exist, return None. This keeps the builder robust to differences
    in export naming without hard-wiring a single convention.

    Candidates (in order):
    - <table_name>.csv              e.g. content_version.csv
    - <table_name>s.csv             e.g. content_versions.csv
    - <api_name>.csv                e.g. ContentVersion.csv
    - <api_name_lower>.csv          e.g. contentversion.csv
    """
    candidates = [
        export_root / f"{table_cfg.table_name}.csv",
        export_root / f"{table_cfg.table_name}s.csv",
        export_root / f"{obj.api_name}.csv",
        export_root / f"{obj.api_name.lower()}.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _detect_csv_root(export_dir: Path, log: logging.Logger) -> Path:
    """Detect the root directory that contains object CSV files.

    We expect an sfdump export to look like one of:

    - <export_dir>/csv                 (preferred layout)
    - <export_dir>/files/objects       (legacy full export layout)
    - <export_dir>/objects             (object-only export)

    If none of these directories exist, or they exist but contain no *.csv
    files, we raise a ValueError with a helpful message instead of silently
    creating an empty SQLite database.
    """
    candidates = [
        export_dir / "csv",
        export_dir / "files" / "objects",
        export_dir / "objects",
    ]

    csv_root: Optional[Path] = None
    for root in candidates:
        if root.is_dir():
            csv_root = root
            break

    if csv_root is None:
        raise ValueError(
            f"Could not find a CSV root under {export_dir}. "
            "Looked for 'csv', 'files/objects', or 'objects' directories. "
            "This export may not include object CSVs."
        )

    # Ensure there is at least one CSV file
    if not any(csv_root.glob("*.csv")):
        raise ValueError(
            f"No CSV files found in {csv_root}. "
            "This export appears to contain no object CSVs; "
            "run 'sfdump csv' or choose an export that includes object data."
        )

    log.info("Using %s as CSV root for SQLite build", csv_root)
    return csv_root


def build_sqlite_from_export(
    export_dir: Path | str,
    db_path: Path | str,
    *,
    overwrite: bool = False,
    objects: Iterable[SFObject] | None = None,
    index_configs: Iterable[SqliteIndexConfig] | None = None,
    logger: Optional[logging.Logger] = None,
) -> Path:
    """Build a SQLite database from a directory of CSV exports.

    Parameters
    ----------
    export_dir:
        Root export directory (e.g. ``exports/export-2025-11-30``). Object
        CSVs are expected to live under a subdirectory such as ``csv``,
        ``files/objects``, or ``objects``.
    db_path:
        Path to the SQLite database file to create.
    overwrite:
        If True and db_path already exists, it will be deleted first.
        If False and db_path exists, a FileExistsError is raised.
    objects:
        Optional subset of SFObject definitions to load. If None, all objects
        from ``iter_objects()`` are used.
    index_configs:
        Optional sequence of SqliteIndexConfig. If None, defaults derived from
        known relationships via ``default_index_configs()`` are used.
    logger:
        Optional logger to use; if None, uses this module's LOG.

    Returns
    -------
    Path
        The path to the created SQLite database.
    """
    log = logger or LOG

    export_dir = Path(export_dir)
    db_path = Path(db_path)

    if not export_dir.is_dir():
        raise ValueError(f"export_dir {export_dir} is not a directory")

    # Decide where to look for object CSVs and make sure it has data.
    csv_root = _detect_csv_root(export_dir, log)

    # Ensure the parent directory for the SQLite file exists
    if db_path.parent and not db_path.parent.exists():
        log.info("Creating parent directory for SQLite database at %s", db_path.parent)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        if overwrite:
            log.info("Removing existing SQLite database at %s", db_path)
            db_path.unlink()
        else:
            raise FileExistsError(f"SQLite database already exists at {db_path}")

    if objects is None:
        objects = list(iter_objects())

    table_configs = default_table_configs(objects)
    if index_configs is None:
        index_configs = default_index_configs()

    log.info("Creating SQLite database at %s", db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        created_tables: set[str] = set()

        # Load each object's CSV into its own table
        for obj in objects:
            table_cfg = table_configs.get(obj.api_name)
            if table_cfg is None:
                continue

            csv_path = _find_csv_for_object(csv_root, obj, table_cfg)
            if csv_path is None:
                log.info("No CSV found for %s (%s); skipping", obj.api_name, table_cfg.table_name)
                continue

            log.info("Loading %s from %s", obj.api_name, csv_path)

            with csv_path.open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    log.warning("CSV %s for %s is empty; skipping", csv_path, obj.api_name)
                    continue

                # Build CREATE TABLE: all columns as TEXT, with an optional PRIMARY KEY
                columns_sql_parts = []
                for col in header:
                    col_def = f'"{col}" TEXT'
                    if col == table_cfg.pk_column:
                        col_def = f'"{col}" TEXT PRIMARY KEY'
                    columns_sql_parts.append(col_def)

                columns_sql = ", ".join(columns_sql_parts)
                create_sql = f'CREATE TABLE "{table_cfg.table_name}" ({columns_sql})'
                cur.execute(create_sql)
                created_tables.add(table_cfg.table_name)

                # Prepare INSERT statement
                col_list_sql = ", ".join(f'"{c}"' for c in header)
                placeholders = ", ".join("?" for _ in header)
                insert_sql = (
                    f'INSERT INTO "{table_cfg.table_name}" ({col_list_sql}) VALUES ({placeholders})'
                )

                for row in reader:
                    # Be tolerant of short/long rows by padding/truncating
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[: len(header)]
                    cur.execute(insert_sql, row)

        # Create indexes based on relationships, but only for tables we actually created
        for idx in index_configs:
            if idx.table not in created_tables:
                log.info(
                    "Skipping index %s because table %s does not exist",
                    idx.name,
                    idx.table,
                )
                continue

            cols_sql = ", ".join(f'"{c}"' for c in idx.columns)
            unique_sql = "UNIQUE " if idx.unique else ""
            create_idx_sql = (
                f'CREATE {unique_sql}INDEX IF NOT EXISTS "{idx.name}" ON "{idx.table}" ({cols_sql})'
            )
            log.info("Ensuring index %s on %s(%s)", idx.name, idx.table, cols_sql)
            cur.execute(create_idx_sql)

        conn.commit()
    finally:
        conn.close()

    log.info("SQLite database built successfully at %s", db_path)
    return db_path
