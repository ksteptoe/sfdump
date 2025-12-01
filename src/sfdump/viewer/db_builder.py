"""SQLite database builder for offline Salesforce exports.

This module turns a directory of CSV exports into a single SQLite database,
using the object and relationship metadata defined in ``sfdump.indexing`` and
the SQLite-oriented schema helpers in ``sfdump.viewer.sqlite_schema``.

It does *not* define any CLI; callers are expected to invoke
``build_sqlite_from_export`` directly. A future Click command can wrap this
without changing the core logic.
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
    export_dir: Path, obj: SFObject, table_cfg: SqliteTableConfig
) -> Optional[Path]:
    """Best-effort resolution of the CSV file for a given object.

    We try a small set of conventional filenames. If none exist, return None.
    This keeps the builder robust to differences in export naming without
    hard-wiring a single convention.

    Candidates (in order):
    - <table_name>.csv              e.g. content_version.csv
    - <table_name>s.csv             e.g. content_versions.csv
    - <api_name>.csv                e.g. ContentVersion.csv
    - <api_name_lower>.csv          e.g. contentversion.csv
    """
    candidates = [
        export_dir / f"{table_cfg.table_name}.csv",
        export_dir / f"{table_cfg.table_name}s.csv",
        export_dir / f"{obj.api_name}.csv",
        export_dir / f"{obj.api_name.lower()}.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


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
        Directory containing CSV files for exported Salesforce objects.
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

        # Load each object's CSV into its own table
        for obj in objects:
            table_cfg = table_configs.get(obj.api_name)
            if table_cfg is None:
                continue

            csv_path = _find_csv_for_object(export_dir, obj, table_cfg)
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

        # Create indexes based on relationships
        for idx in index_configs:
            cols_sql = ", ".join(f'"{c}"' for c in idx.columns)
            unique_sql = "UNIQUE " if idx.unique else ""
            create_idx_sql = (
                f'CREATE {unique_sql}INDEX IF NOT EXISTS "{idx.name}" '
                f'ON "{idx.table}" ({cols_sql})'
            )
            log.info("Ensuring index %s on %s(%s)", idx.name, idx.table, cols_sql)
            cur.execute(create_idx_sql)

        conn.commit()
    finally:
        conn.close()

    log.info("SQLite database built successfully at %s", db_path)
    return db_path
