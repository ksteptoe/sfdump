from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def enrich_contentdocument_links_with_title(db_path: Path, df: Any):
    """
    For ContentDocumentLink rows, add a 'DocumentTitle' column by looking up
    ContentDocument.Title from the 'content_document' table in the viewer DB.

    If anything goes wrong (no table, etc.), this falls back silently.
    """
    # Defensive: if the column isn't there, nothing to do
    if not hasattr(df, "columns") or "ContentDocumentId" not in df.columns:
        return df

    # Collect distinct non-empty IDs
    doc_ids = {str(x) for x in df["ContentDocumentId"] if x}
    if not doc_ids:
        return df

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            placeholders = ", ".join("?" for _ in doc_ids)
            sql = f'SELECT "Id", "Title" FROM "content_document" WHERE Id IN ({placeholders})'
            cur.execute(sql, list(doc_ids))
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        # If the table doesn't exist or query fails, just return the original df
        return df

    id_to_title = {row[0]: row[1] for row in rows}

    df = df.copy()
    df["DocumentTitle"] = df["ContentDocumentId"].map(id_to_title)
    return df
