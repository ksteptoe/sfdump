from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class DocumentRow:
    file_extension: str
    file_source: str
    file_name: str
    local_path: str
    object_type: str
    record_id: str
    record_name: str


def list_record_documents(
    *,
    db_path: Path,
    object_type: str,
    record_id: str,
    limit: int = 500,
) -> list[dict[str, str]]:
    """
    Return rows from record_documents filtered by (object_type, record_id).
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute('PRAGMA table_info("record_documents")')
        cols = [r[1] for r in cur.fetchall()]

        required = {"object_type", "record_id"}
        if not required.issubset(set(cols)):
            # Schema mismatch – caller can handle empty result.
            return []

        select_cols = [
            "file_extension",
            "file_source",
            "file_name",
            "local_path",
            "object_type",
            "record_id",
            "record_name",
        ]
        select_cols = [c for c in select_cols if c in cols]
        select_sql = ", ".join([f'"{c}"' for c in select_cols])

        sql = (
            f'SELECT {select_sql} FROM "record_documents" '
            "WHERE object_type=? AND record_id=? LIMIT ?"
        )
        cur.execute(sql, (object_type, record_id, int(limit)))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_master_documents_index(export_root: Path) -> Optional[pd.DataFrame]:
    """
    Load meta/master_documents_index.csv, returning a normalized DataFrame.

    Expected normalized columns:
      - record_id, object_type, record_name, file_name, file_extension, file_source, local_path
    """
    p = export_root / "meta" / "master_documents_index.csv"
    if not p.exists():
        return None

    df = pd.read_csv(p, dtype=str).fillna("")

    # Normalize column names to expected ones
    cols = {c.lower(): c for c in df.columns}

    def _pick(*names: str) -> str | None:
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    mapping = {
        "record_id": _pick("record_id", "recordid"),
        "object_type": _pick("object_type", "objecttype"),
        "record_name": _pick("record_name", "recordname", "name"),
        "file_name": _pick("file_name", "filename"),
        "file_extension": _pick("file_extension", "fileextension", "ext"),
        "file_source": _pick("file_source", "filesource", "source"),
        "local_path": _pick("local_path", "localpath", "path"),
    }

    # If already correct, just ensure required cols exist
    out = pd.DataFrame()
    for k, src in mapping.items():
        out[k] = df[src] if src else ""

    return out.fillna("")
