"""Helpers for inspecting SQLite viewer databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class TableInfo:
    """Summary information about a table in the SQLite database."""

    name: str
    row_count: int


@dataclass(frozen=True)
class DbOverview:
    """High-level overview of a SQLite viewer database."""

    path: Path
    tables: List[TableInfo]
    index_count: int


def inspect_sqlite_db(db_path: Path | str) -> DbOverview:
    """Inspect a SQLite viewer database and return a summary.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.

    Returns
    -------
    DbOverview

    Raises
    ------
    FileNotFoundError
        If the db_path does not exist.
    ValueError
        If the path exists but is not a file.
    """
    path = Path(db_path)

    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found at {path}")
    if not path.is_file():
        raise ValueError(f"SQLite database path {path} is not a file")

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()

        # List tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [name for (name,) in cur.fetchall()]

        tables: List[TableInfo] = []
        for name in table_names:
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            (row_count,) = cur.fetchone()
            tables.append(TableInfo(name=name, row_count=row_count))

        # Count indexes
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
        (index_count,) = cur.fetchone()

    finally:
        conn.close()

    return DbOverview(path=path, tables=tables, index_count=index_count)
