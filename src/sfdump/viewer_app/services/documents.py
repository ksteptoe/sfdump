from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from sfdump.viewer_app.services.paths import resolve_export_path


def _table_cols(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]


def _pick_col(cols: list[str], candidates: list[str]) -> Optional[str]:
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in cols:
            return cand
        if cand.lower() in low:
            return low[cand.lower()]
    return None


def list_record_documents(
    *,
    db_path: Path,
    record_id: str,
    object_type: Optional[str] = None,
    api_name: Optional[str] = None,
    record_api: Optional[str] = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """
    Query the SQLite table "record_documents" for a given record.
    Works even if your schema uses object_type vs record_api, etc.
    """
    effective_api = object_type or api_name or record_api

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

        cols = _table_cols(cur, "record_documents")
        rec_id_col = _pick_col(
            cols, ["record_id", "RecordId", "linked_entity_id", "LinkedEntityId"]
        )
        obj_col = _pick_col(cols, ["object_type", "record_api", "record_type", "api_name"])

        if rec_id_col is None:
            # can't filter sanely
            sql = 'SELECT * FROM "record_documents" LIMIT ?'
            cur.execute(sql, (int(limit),))
            return [dict(r) for r in cur.fetchall()]

        where = [f'"{rec_id_col}" = ?']
        params: list[Any] = [record_id]

        if effective_api and obj_col:
            where.append(f'"{obj_col}" = ?')
            params.append(effective_api)

        sql = f'SELECT * FROM "record_documents" WHERE {" AND ".join(where)} LIMIT ?'
        params.append(int(limit))
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_master_documents_index(export_root: Path) -> Optional[pd.DataFrame]:
    """
    Load export_root/meta/master_documents_index.csv and normalize columns
    so db_app can rely on:
      record_id, object_type, record_name, file_name, file_extension, file_source, local_path
    """
    export_root = Path(export_root)
    p = export_root / "meta" / "master_documents_index.csv"
    if not p.exists():
        return None

    df = pd.read_csv(p, dtype=str).fillna("")

    # Column normalization (case-insensitive)
    cols_l = {c.lower(): c for c in df.columns}

    def col(*names: str) -> Optional[str]:
        for n in names:
            if n in df.columns:
                return n
            if n.lower() in cols_l:
                return cols_l[n.lower()]
        return None

    record_id_c = col("record_id", "RecordId", "LinkedEntityId", "linked_entity_id")
    object_c = col("object_type", "ObjectType", "record_api", "api_name", "RecordType")
    record_name_c = col("record_name", "RecordName", "parent_name", "ParentName", "name")
    file_name_c = col("file_name", "FileName", "title", "Title", "DocumentTitle", "document_title")
    ext_c = col("file_extension", "FileExtension", "ext", "Extension")
    src_c = col("file_source", "FileSource", "source", "Source")
    path_c = col("local_path", "LocalPath", "path", "Path", "rel_path", "RelPath", "relative_path")

    out = pd.DataFrame()
    out["record_id"] = df[record_id_c] if record_id_c else ""
    out["object_type"] = df[object_c] if object_c else ""
    out["record_name"] = df[record_name_c] if record_name_c else ""
    out["file_name"] = df[file_name_c] if file_name_c else ""
    out["file_extension"] = df[ext_c] if ext_c else ""
    out["file_source"] = df[src_c] if src_c else ""
    out["local_path"] = df[path_c] if path_c else ""

    # If local_path looks like an absolute path, keep it. If it's relative, keep relative.
    # (db_app will resolve it via resolve_export_path)
    out = out.fillna("")

    return out


def resolve_document_path(export_root: Path, local_path: str) -> Path:
    """
    Convenience for turning a docs index local_path into a full filesystem path.
    """
    return resolve_export_path(Path(export_root), local_path)
