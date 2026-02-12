"""Tests for build_record_documents — specifically the path-from-row feature."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from sfdump.indexing.build_record_documents import build_record_documents


@pytest.fixture()
def export_root(tmp_path: Path) -> Path:
    """Create a minimal export directory with links/."""
    links = tmp_path / "links"
    links.mkdir()
    meta = tmp_path / "meta"
    meta.mkdir()
    return tmp_path


def _write_files_index(links_dir: Path, rows: list[dict]) -> None:
    """Write a files_index CSV with the given rows."""
    if not rows:
        return
    path = links_dir / "test_files_index.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _query_record_documents(db_path: Path) -> list[dict]:
    """Read all rows from record_documents table."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM record_documents").fetchall()
    conn.close()
    return [dict(r) for r in rows]


class TestPathFromRow:
    def test_inline_path_used_directly(self, export_root: Path):
        """When a files_index row includes a path column, it should be used."""
        _write_files_index(
            export_root / "links",
            [
                {
                    "object_type": "c2g__codaInvoice__c",
                    "record_id": "a1J000001",
                    "record_name": "SIN001001",
                    "file_source": "InvoicePDF",
                    "file_id": "a1J000001",
                    "file_link_id": "",
                    "file_name": "SIN001001.pdf",
                    "file_extension": "pdf",
                    "path": "invoices/SIN001001.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": "12345",
                },
            ],
        )

        db_path = export_root / "meta" / "test.db"
        build_record_documents(db_path, export_root)

        rows = _query_record_documents(db_path)
        assert len(rows) == 1
        assert rows[0]["path"] == "invoices/SIN001001.pdf"
        assert rows[0]["content_type"] == "application/pdf"
        assert rows[0]["size_bytes"] == 12345
        assert rows[0]["file_source"] == "InvoicePDF"

    def test_empty_path_falls_through(self, export_root: Path):
        """When the path column is empty, it should fall through to lookup."""
        _write_files_index(
            export_root / "links",
            [
                {
                    "object_type": "c2g__codaInvoice__c",
                    "record_id": "a1J000002",
                    "record_name": "SIN001002",
                    "file_source": "InvoicePDF",
                    "file_id": "a1J000002",
                    "file_link_id": "",
                    "file_name": "SIN001002.pdf",
                    "file_extension": "pdf",
                    "path": "",
                    "content_type": "application/pdf",
                    "size_bytes": "",
                },
            ],
        )

        db_path = export_root / "meta" / "test.db"
        build_record_documents(db_path, export_root)

        rows = _query_record_documents(db_path)
        assert len(rows) == 1
        # Path should be None since there's no attachment/content_version match
        assert rows[0]["path"] is None
        # File name and extension should still be set
        assert rows[0]["file_name"] == "SIN001002.pdf"
        assert rows[0]["record_name"] == "SIN001002"
