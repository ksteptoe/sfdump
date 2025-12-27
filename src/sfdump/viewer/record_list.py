"""Helpers for listing records from the viewer SQLite DB."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sfdump.indexing import SFObject

from .record_viewer import _resolve_object  # reuse object resolution


@dataclass(frozen=True)
class ListResult:
    """Result of listing records for a given object."""

    sf_object: SFObject
    rows: List[Dict[str, Any]]


_VALID_ORDER_BY = re.compile(r"^[A-Za-z0-9_]+$")


def _regexp(pattern: str, value: Any) -> int:
    """SQLite REGEXP implementation using Python's re.search.

    Returns 1 if the value matches the pattern, else 0.
    Invalid regex patterns are treated as 'no match'.
    """
    if value is None:
        return 0
    text = str(value)
    try:
        return 1 if re.search(pattern, text) else 0
    except re.error:
        # Invalid regex → treat as no match rather than blowing up the query
        return 0


def list_records(
    db_path: Path | str,
    api_name: str,
    *,
    where: Optional[str] = None,
    limit: int = 50,
    order_by: Optional[str] = None,
) -> ListResult:
    """List records for an object from the viewer SQLite DB.

    Parameters
    ----------
    db_path:
        Path to the SQLite database built via build_sqlite_from_export.
    api_name:
        Salesforce API name for the object (e.g. "Account").
    where:
        Optional SQL WHERE clause fragment (without the 'WHERE' keyword),
        e.g. "Name LIKE '%Acme%'". This is passed directly to SQLite.
    limit:
        Maximum number of rows to return.
    order_by:
        Optional column name to order by. If provided, it must be a simple
        identifier (letters, digits, underscore) to avoid SQL injection.

    Returns
    -------
    ListResult
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found at {path}")
    if not path.is_file():
        raise ValueError(f"SQLite database path {path} is not a file")

    sf_obj = _resolve_object(api_name)

    sql = f'SELECT * FROM "{sf_obj.table_name}"'
    if where:
        sql += f" WHERE {where}"

    if order_by:
        if not _VALID_ORDER_BY.match(order_by):
            raise ValueError(f"Invalid order_by column name: {order_by!r}")
        sql += f' ORDER BY "{order_by}"'

    sql += f" LIMIT {int(limit)}"

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # Register REGEXP for this connection so WHERE ... REGEXP ... works
    conn.create_function("REGEXP", 2, _regexp)

    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    return ListResult(sf_object=sf_obj, rows=rows)
