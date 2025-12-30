from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

import streamlit as st


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]  # (cid, name, type, notnull, dflt_value, pk)


def _pick_first(cols: set[str], candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None


def list_record_documents(
    *,
    db_path: Path,
    object_type: str,
    record_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Read per-record document rows from the SQLite table `record_documents`.

    This is defensive against schema drift. We look for plausible column names:
      - object: object_type | record_api | record_type | api_name
      - record: record_id | linked_id | parent_id
      - path: path | local_path | attachment_path | content_path
    """
    p = Path(db_path)
    if not p.exists():
        st.warning(f"DB not found: {p}")
        return []

    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='record_documents'")
        if cur.fetchone() is None:
            return []

        cols_list = _table_columns(conn, "record_documents")
        cols = set(cols_list)

        obj_col = _pick_first(
            cols, ["object_type", "record_api", "record_type", "api_name", "object_api"]
        )
        rid_col = _pick_first(cols, ["record_id", "linked_id", "parent_id", "entity_id"])
        path_col = _pick_first(cols, ["path", "local_path", "attachment_path", "content_path"])

        if not obj_col or not rid_col:
            # Can't filter sanely; return empty rather than confusing data.
            return []

        select_sql = ", ".join([f'"{c}"' for c in cols_list])
        sql = (
            f'SELECT {select_sql} FROM "record_documents" '
            f'WHERE "{obj_col}"=? AND "{rid_col}"=? LIMIT ?'
        )
        cur.execute(sql, (object_type, record_id, int(limit)))
        rows = [dict(r) for r in cur.fetchall()]

        # Normalize to the keys the UI expects
        for r in rows:
            if "path" not in r:
                r["path"] = r.get(path_col or "", "") if path_col else ""
        return rows

    finally:
        conn.close()


def load_master_documents_index(export_root: Path):
    """
    Load EXPORT_ROOT/meta/master_documents_index.csv into a DataFrame.

    Returns pandas.DataFrame or None if not found.
    """
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except Exception:
        st.error("pandas is required to load the master documents index.")
        return None

    root = Path(export_root)
    p = root / "meta" / "master_documents_index.csv"
    if not p.exists():
        return None

    df = pd.read_csv(p, dtype=str).fillna("")

    # Normalize common columns (keep original too)
    cols_lower = {c.lower(): c for c in df.columns}

    def _ensure(name: str, aliases: list[str]) -> None:
        if name in df.columns:
            return
        for a in aliases:
            if a in df.columns:
                df[name] = df[a]
                return
        for a in aliases:
            if a.lower() in cols_lower:
                df[name] = df[cols_lower[a.lower()]]
                return

    _ensure("record_id", ["record_id", "linkedentityid", "linked_entity_id"])
    _ensure("object_type", ["object_type", "record_api", "api_name"])
    _ensure("local_path", ["local_path", "path", "attachment_path", "content_path"])
    _ensure("file_name", ["file_name", "title", "name"])
    _ensure("file_extension", ["file_extension", "ext", "extension"])
    _ensure("file_source", ["file_source", "source"])

    return df
