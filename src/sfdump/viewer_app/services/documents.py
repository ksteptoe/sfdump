from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def list_record_documents(db_path: Path, object_type: str, record_id: str) -> list[dict[str, Any]]:
    """
    Return documents for a given (object_type, record_id) from the viewer DB table `record_documents`.

    Expected columns (from your build-db/docs-index pipeline):
      object_type, record_id, record_name,
      file_source, file_id, file_link_id,
      file_name, file_extension,
      path, content_type, size_bytes, sha256
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              object_type, record_id, record_name,
              file_source, file_id, file_link_id,
              file_name, file_extension,
              path, content_type, size_bytes, sha256
            FROM record_documents
            WHERE object_type = ? AND record_id = ?
            ORDER BY lower(file_extension), file_name
            """,
            (object_type, record_id),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_master_documents_index(export_root: Path):
    """
    Load meta/master_documents_index.csv (built by `sfdump docs-index`).
    Returns pandas.DataFrame or None if pandas is unavailable or file missing/unreadable.
    """
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except Exception:
        return None

    path = export_root / "meta" / "master_documents_index.csv"
    if not path.exists():
        return None

    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return None


def enrich_documents_with_local_path(
    export_root: Path, docs: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Fill missing doc local paths by looking up meta/master_documents_index.csv.

    Some DB rows (record_documents) can have blank path/local_path even if the file was
    downloaded later. This function enriches those rows from the master index.
    """
    if not docs:
        return docs

    try:
        pass  # type: ignore[import-not-found]
    except Exception:
        return docs

    df = load_master_documents_index(export_root)
    if df is None or df.empty:
        return docs

    # The index may contain either local_path or path
    path_col = (
        "local_path" if "local_path" in df.columns else ("path" if "path" in df.columns else None)
    )
    if path_col is None or "file_id" not in df.columns:
        return docs

    # Map file_id -> local path (first non-empty wins)
    subset = df[["file_id", path_col]].copy()
    subset = subset[(subset["file_id"].astype(str) != "") & (subset[path_col].astype(str) != "")]
    id_to_path: dict[str, str] = {}
    for fid, lp in zip(
        subset["file_id"].astype(str).tolist(), subset[path_col].astype(str).tolist(), strict=False
    ):
        if fid and lp and fid not in id_to_path:
            id_to_path[fid] = lp

    if not id_to_path:
        return docs

    out: list[dict[str, object]] = []
    for d in docs:
        dd = dict(d)
        fid = str(dd.get("file_id") or "")
        # viewer uses 'path' when opening; keep both for clarity
        has_path = bool(str(dd.get("path") or "").strip())
        has_local = bool(str(dd.get("local_path") or "").strip())
        if fid and (not has_path and not has_local):
            lp = id_to_path.get(fid, "")
            if lp:
                dd["local_path"] = lp
                dd["path"] = lp
        out.append(dd)

    return out
