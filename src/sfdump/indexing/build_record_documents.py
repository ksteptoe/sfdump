from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DDL = """
CREATE TABLE IF NOT EXISTS record_documents (
  object_type      TEXT NOT NULL,
  record_id        TEXT NOT NULL,
  record_name      TEXT,
  file_source      TEXT NOT NULL,   -- Attachment | File
  file_id          TEXT NOT NULL,
  file_link_id     TEXT,
  file_name        TEXT,
  file_extension   TEXT,
  path             TEXT,            -- relative path under EXPORT_ROOT (as stored in links csv)
  sha256           TEXT,
  content_type     TEXT,
  size_bytes       INTEGER,
  PRIMARY KEY (object_type, record_id, file_source, file_id)
);

CREATE INDEX IF NOT EXISTS idx_record_documents_record
  ON record_documents(record_id);

CREATE INDEX IF NOT EXISTS idx_record_documents_object
  ON record_documents(object_type);

CREATE INDEX IF NOT EXISTS idx_record_documents_file
  ON record_documents(file_id);
"""


def _read_csv_map_by_id(csv_path: Path) -> Dict[str, Dict[str, str]]:
    """Read a CSV and return {Id: rowdict} if it has an Id column."""
    if not csv_path.exists():
        return {}

    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or "Id" not in r.fieldnames:
            return {}
        out: Dict[str, Dict[str, str]] = {}
        for row in r:
            rid = (row.get("Id") or "").strip()
            if rid:
                out[rid] = row
        return out


def _iter_files_index_rows(links_dir: Path) -> Iterable[Dict[str, str]]:
    """Yield rows from every *_files_index.csv under links/."""
    if not links_dir.exists():
        return []
    for p in sorted(links_dir.glob("*_files_index.csv")):
        with p.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                yield row


def _read_master_index_by_file_id(master_index_path: Path) -> Dict[str, Dict[str, str]]:
    """Read master_documents_index.csv and return {file_id: rowdict}."""
    if not master_index_path.exists():
        return {}

    with master_index_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        out: Dict[str, Dict[str, str]] = {}
        for row in r:
            # file_id could be attachment_id or content_document_id depending on source
            file_id = (row.get("file_id") or "").strip()
            if file_id:
                out[file_id] = row
        return out


def build_record_documents(db_path: Path, export_root: Path) -> None:
    """
    Build a single table that maps:
      (object_type, record_id) -> on-disk document path (Attachment/File)

    Sources:
      links/*_files_index.csv
      links/attachments.csv
      links/content_versions.csv  (if present)
      meta/master_documents_index.csv (fallback for paths)
    """
    links_dir = export_root / "links"
    meta_dir = export_root / "meta"

    attachments = _read_csv_map_by_id(links_dir / "attachments.csv")
    versions = _read_csv_map_by_id(links_dir / "content_versions.csv")
    master_index = _read_master_index_by_file_id(meta_dir / "master_documents_index.csv")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.executescript(DDL)

        # simplest + deterministic: rebuild every time
        cur.execute("DELETE FROM record_documents")

        rows: List[tuple[Any, ...]] = []

        for r in _iter_files_index_rows(links_dir):
            object_type = (r.get("object_type") or "").strip()
            record_id = (r.get("record_id") or "").strip()
            record_name = (r.get("record_name") or "").strip() or None

            file_source = (r.get("file_source") or "").strip()
            file_id = (r.get("file_id") or "").strip()
            file_link_id = (r.get("file_link_id") or "").strip() or None
            file_name = (r.get("file_name") or "").strip() or None
            file_extension = (r.get("file_extension") or "").strip() or None

            if not object_type or not record_id or not file_source or not file_id:
                continue

            path: Optional[str] = None
            sha256: Optional[str] = None
            content_type: Optional[str] = None
            size_bytes: Optional[int] = None

            # Check if the files_index row itself carries path metadata
            # (used by sources like InvoicePDF that aren't in attachments/content_versions)
            row_path = (r.get("path") or "").strip()
            if row_path:
                path = row_path
                content_type = (r.get("content_type") or "").strip() or None
                sb = (r.get("size_bytes") or "").strip()
                if sb and sb.isdigit():
                    size_bytes = int(sb)
            elif file_source.lower() == "attachment":
                a = attachments.get(file_id, {})
                # your attachments.csv uses "path" (not "local_path")
                path = (a.get("path") or a.get("local_path") or "").strip() or None
                sha256 = (a.get("sha256") or "").strip() or None
                content_type = (a.get("ContentType") or a.get("content_type") or "").strip() or None
                bl = (a.get("BodyLength") or a.get("body_length") or "").strip()
                if bl.isdigit():
                    size_bytes = int(bl)
            else:
                v = versions.get(file_id, {})
                path = (v.get("path") or v.get("local_path") or "").strip() or None
                sha256 = (v.get("sha256") or "").strip() or None
                content_type = (v.get("FileType") or v.get("content_type") or "").strip() or None
                cs = (v.get("ContentSize") or v.get("content_size") or "").strip()
                if cs.isdigit():
                    size_bytes = int(cs)

            # Fallback to master_documents_index.csv if path not found
            if not path:
                m = master_index.get(file_id, {})
                path = (m.get("local_path") or m.get("path") or "").strip() or None
                # Also try to get other metadata from master index if still missing
                if not sha256:
                    sha256 = (m.get("sha256") or "").strip() or None
                if not content_type:
                    content_type = (m.get("content_type") or "").strip() or None
                if not size_bytes:
                    sb = (m.get("size_bytes") or "").strip()
                    if sb.isdigit():
                        size_bytes = int(sb)

            rows.append(
                (
                    object_type,
                    record_id,
                    record_name,
                    file_source,
                    file_id,
                    file_link_id,
                    file_name,
                    file_extension,
                    path,
                    sha256,
                    content_type,
                    size_bytes,
                )
            )

        cur.executemany(
            """
            INSERT OR REPLACE INTO record_documents (
              object_type, record_id, record_name,
              file_source, file_id, file_link_id,
              file_name, file_extension,
              path, sha256, content_type, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        conn.commit()
    finally:
        conn.close()
