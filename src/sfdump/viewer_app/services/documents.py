from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from sfdump.viewer_app.services.paths import resolve_export_path


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]


def _first_present(cols: list[str], candidates: list[str]) -> Optional[str]:
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in low:
            return low[cand.lower()]
    return None


def list_record_documents(
    *,
    db_path: Path,
    object_type: str,
    record_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return document rows for a given record.

    The underlying DB schema has changed across versions; we detect columns at runtime.

    Returns list of dict rows, with at least:
      - path (best-effort local file path column)
      - file_name / file_extension / content_type when present
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # Ensure table exists
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ("record_documents",),
        )
        if cur.fetchone() is None:
            return []

        cols = _table_columns(cur, "record_documents")

        # Column candidates across versions
        api_col = _first_present(cols, ["object_type", "record_api", "record_type", "api_name"])
        rid_col = _first_present(cols, ["record_id", "linked_record_id", "parent_id", "entity_id"])
        path_col = _first_present(
            cols, ["path", "local_path", "file_path", "attachment_path", "content_path"]
        )

        # If we can't filter in SQL, we’ll fetch and filter in Python.
        select_cols = cols[:]  # select all; table is typically not huge
        select_sql = ", ".join([f'"{c}"' for c in select_cols])

        if api_col and rid_col:
            sql = (
                f'SELECT {select_sql} FROM "record_documents" '
                f'WHERE "{api_col}"=? AND "{rid_col}"=? '
                f"LIMIT ?"
            )
            cur.execute(sql, (object_type, record_id, int(limit)))
            rows = [dict(r) for r in cur.fetchall()]
        else:
            sql = f'SELECT {select_sql} FROM "record_documents" LIMIT ?'
            cur.execute(sql, (int(max(limit, 2000)),))
            rows = [dict(r) for r in cur.fetchall()]

            def _match(r: dict[str, Any]) -> bool:
                ok_api = True
                ok_id = True
                if api_col:
                    ok_api = str(r.get(api_col, "") or "") == object_type
                if rid_col:
                    ok_id = str(r.get(rid_col, "") or "") == record_id
                return ok_api and ok_id

            rows = [r for r in rows if _match(r)][: int(limit)]

        # Normalize a few keys so the UI can rely on "path"
        out: list[dict[str, Any]] = []
        for r in rows:
            rr = dict(r)
            if "path" not in rr:
                if path_col:
                    rr["path"] = rr.get(path_col, "")
                else:
                    rr["path"] = ""
            out.append(rr)

        return out

    finally:
        conn.close()


def load_master_documents_index(export_root: Path) -> Optional[pd.DataFrame]:
    """
    Load meta/master_documents_index.csv.

    Returns a DataFrame with normalized column names expected by the UI:
      - local_path
      - record_id
      - object_type
      - file_name
      - file_extension
      - file_source
    """
    export_root = Path(export_root)
    p = export_root / "meta" / "master_documents_index.csv"
    if not p.exists():
        return None

    # Read as strings for safety
    df = pd.read_csv(p, dtype=str).fillna("")

    # Normalize column names to expected ones
    cols = {c.lower(): c for c in df.columns}

    def _col(*names: str) -> Optional[str]:
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    # Rename to canonical names if needed
    ren: dict[str, str] = {}

    c_local = _col("local_path", "path", "file_path", "attachment_path", "content_path")
    if c_local and c_local != "local_path":
        ren[c_local] = "local_path"

    c_rid = _col("record_id", "linked_record_id", "parent_id", "entity_id")
    if c_rid and c_rid != "record_id":
        ren[c_rid] = "record_id"

    c_obj = _col("object_type", "record_api", "record_type", "api_name")
    if c_obj and c_obj != "object_type":
        ren[c_obj] = "object_type"

    c_fn = _col("file_name", "filename", "name")
    if c_fn and c_fn != "file_name":
        ren[c_fn] = "file_name"

    c_ext = _col("file_extension", "extension", "ext")
    if c_ext and c_ext != "file_extension":
        ren[c_ext] = "file_extension"

    c_src = _col("file_source", "source")
    if c_src and c_src != "file_source":
        ren[c_src] = "file_source"

    if ren:
        df = df.rename(columns=ren)

    # Ensure the key columns exist
    for needed in [
        "local_path",
        "record_id",
        "object_type",
        "file_name",
        "file_extension",
        "file_source",
    ]:
        if needed not in df.columns:
            df[needed] = ""

    return df


def resolve_index_row_to_file(export_root: Path, row: dict[str, Any]) -> Optional[Path]:
    """
    Given a master index row, resolve to a real file path if possible.
    """
    export_root = Path(export_root)
    lp = str(row.get("local_path", "") or "").strip()
    if not lp:
        return None
    return resolve_export_path(export_root, lp)
