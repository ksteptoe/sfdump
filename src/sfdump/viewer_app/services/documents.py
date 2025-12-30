from __future__ import annotations

import mimetypes
import sqlite3
from pathlib import Path
from typing import Any, Optional


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]  # (cid, name, type, notnull, dflt_value, pk)


def _guess_mime(file_name: str) -> str:
    mime, _ = mimetypes.guess_type(file_name)
    return mime or "application/octet-stream"


def list_record_documents(
    *,
    db_path: Path,
    record_id: str,
    object_type: Optional[str] = None,
    record_api: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return per-record documents from the SQLite `record_documents` table.

    This function is deliberately schema-flexible because you’ve had at least
    two layouts in-flight:

    Newer CSV header you pasted:
      file_source,file_name,file_extension,local_path,object_type,record_name,record_id,...

    Older layout (previous iterations):
      file_source,file_id,file_name,file_extension,path,content_type,record_api,record_id,...

    We normalize output so callers can rely on:
      - file_name
      - file_extension
      - file_source
      - record_id
      - object_type (if present)
      - local_path (if present)
      - path (alias: whichever local-ish path column exists)
      - content_type (best-effort)
    """
    rid = (record_id or "").strip()
    if not rid:
        return []

    effective_api = (object_type or record_api or "").strip()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if not _table_exists(cur, "record_documents"):
            return []

        cols = _table_columns(cur, "record_documents")

        # Which columns identify the owning record?
        api_col = None
        if "object_type" in cols:
            api_col = "object_type"
        elif "record_api" in cols:
            api_col = "record_api"

        # Which column contains the local file path?
        path_col = None
        for c in ("local_path", "path", "attachment_path", "content_path"):
            if c in cols:
                path_col = c
                break

        # Build SELECT list (keep it small but useful)
        wanted = [
            "file_source",
            "file_id",
            "file_link_id",
            "file_name",
            "file_extension",
            "content_type",
            "record_id",
            "record_name",
            "account_id",
            "account_name",
            "opp_id",
            "opp_name",
            "opp_stage",
            "opp_amount",
            "opp_close_date",
            "content_document_id",
            "attachment_id",
            "index_source_file",
        ]
        if api_col:
            wanted.append(api_col)
        if path_col:
            wanted.append(path_col)

        select_cols = [c for c in wanted if c in cols]
        if not select_cols:
            # fallback: select everything (worst-case)
            select_sql = "*"
        else:
            select_sql = ", ".join([f'"{c}"' for c in select_cols])

        where = ['"record_id"=?']
        params: list[Any] = [rid]

        if api_col and effective_api:
            where.append(f'"{api_col}"=?')
            params.append(effective_api)

        sql = f'SELECT {select_sql} FROM "record_documents" WHERE {" AND ".join(where)} LIMIT ?'
        params.append(int(limit))

        cur.execute(sql, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    # Normalize schema differences
    out: list[dict[str, Any]] = []
    for r in rows:
        file_name = (r.get("file_name") or "").strip()
        file_ext = (r.get("file_extension") or "").strip()
        ct = (r.get("content_type") or "").strip()

        if not ct:
            # infer from filename/ext
            guess_name = file_name or f"file{file_ext or ''}"
            ct = _guess_mime(guess_name)

        # normalize api key name
        if "object_type" not in r and "record_api" in r:
            r["object_type"] = r.get("record_api")

        # normalize path/local_path
        pval = ""
        for k in ("local_path", "path", "attachment_path", "content_path"):
            if k in r and r.get(k):
                pval = str(r.get(k))
                break

        # Provide both keys so old/new call sites work
        if "local_path" not in r:
            r["local_path"] = pval
        r["path"] = pval

        r["content_type"] = ct
        out.append(r)

    return out


def load_master_documents_index(export_root: Path) -> Optional["Any"]:
    """
    Load meta/master_documents_index.csv as a pandas DataFrame.
    Returns None if missing or unreadable.
    """
    p = Path(export_root) / "meta" / "master_documents_index.csv"
    if not p.exists():
        return None

    try:
        import pandas as pd  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        df = pd.read_csv(p, dtype=str).fillna("")
    except Exception:
        # Don’t crash the UI — just return None.
        return None

    # Normalize column names to the ones the UI expects
    cols_lower = {c.lower(): c for c in df.columns}

    def _ensure(name: str, *aliases: str) -> None:
        if name in df.columns:
            return
        for a in aliases:
            if a in df.columns:
                df[name] = df[a]
                return
            if a.lower() in cols_lower:
                df[name] = df[cols_lower[a.lower()]]
                return
        df[name] = ""

    _ensure("local_path", "path", "attachment_path", "content_path")
    _ensure("object_type", "record_api")
    _ensure("record_id")
    _ensure("record_name")
    _ensure("file_name")
    _ensure("file_extension")
    _ensure("file_source")
    _ensure("content_type")

    return df
