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
