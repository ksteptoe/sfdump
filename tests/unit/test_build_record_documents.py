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


class TestContentDocumentIdKey:
    def test_content_version_looked_up_by_content_document_id(self, export_root: Path):
        """content_versions.csv is keyed by ContentDocumentId, not Id."""
        links = export_root / "links"
        _write_files_index(
            links,
            [
                {
                    "object_type": "Opportunity",
                    "record_id": "OPP1",
                    "record_name": "Deal",
                    "file_source": "File",
                    "file_id": "069DOCID",
                    "file_link_id": "CDL1",
                    "file_name": "Proposal.docx",
                    "file_extension": "docx",
                },
            ],
        )
        # content_versions.csv has Id (ContentVersionId) and ContentDocumentId
        cv_path = links / "content_versions.csv"
        with cv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f, fieldnames=["Id", "ContentDocumentId", "path", "FileType", "ContentSize"]
            )
            w.writeheader()
            w.writerow(
                {
                    "Id": "068VERID",
                    "ContentDocumentId": "069DOCID",
                    "path": "files/06/069DOCID_Proposal.docx",
                    "FileType": "DOCX",
                    "ContentSize": "5000",
                }
            )

        db_path = export_root / "meta" / "test.db"
        build_record_documents(db_path, export_root)

        rows = _query_record_documents(db_path)
        assert len(rows) == 1
        assert rows[0]["path"] == "files/06/069DOCID_Proposal.docx"
        assert rows[0]["content_type"] == "DOCX"
        assert rows[0]["size_bytes"] == 5000


class TestDiskScanFallback:
    def test_finds_file_on_disk_when_csv_empty(self, export_root: Path):
        """Disk-scan fallback finds ContentVersion files on disk."""
        _write_files_index(
            export_root / "links",
            [
                {
                    "object_type": "Opportunity",
                    "record_id": "OPP1",
                    "record_name": "Deal",
                    "file_source": "File",
                    "file_id": "DOC123",
                    "file_link_id": "CDL1",
                    "file_name": "Proposal.docx",
                    "file_extension": "docx",
                },
            ],
        )
        # No content_versions.csv, no master index

        # Create the file on disk
        fdir = export_root / "files" / "do"
        fdir.mkdir(parents=True)
        (fdir / "DOC123_Proposal.docx").write_bytes(b"content")

        db_path = export_root / "meta" / "test.db"
        build_record_documents(db_path, export_root)

        rows = _query_record_documents(db_path)
        assert len(rows) == 1
        assert rows[0]["path"] == "files/do/DOC123_Proposal.docx"

    def test_finds_attachment_on_disk_when_csv_empty(self, export_root: Path):
        """Disk-scan fallback finds Attachment files on disk."""
        _write_files_index(
            export_root / "links",
            [
                {
                    "object_type": "Opportunity",
                    "record_id": "OPP1",
                    "record_name": "Deal",
                    "file_source": "Attachment",
                    "file_id": "ATT99",
                    "file_link_id": "",
                    "file_name": "Contract.pdf",
                    "file_extension": "pdf",
                },
            ],
        )

        # Create the file on disk
        fdir = export_root / "files_legacy" / "at"
        fdir.mkdir(parents=True)
        (fdir / "ATT99_Contract.pdf").write_bytes(b"content")

        db_path = export_root / "meta" / "test.db"
        build_record_documents(db_path, export_root)

        rows = _query_record_documents(db_path)
        assert len(rows) == 1
        assert rows[0]["path"] == "files_legacy/at/ATT99_Contract.pdf"
