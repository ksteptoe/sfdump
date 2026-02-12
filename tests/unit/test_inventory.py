"""Unit tests for the inventory system."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from sfdump.inventory import (
    CategoryStatus,
    InventoryManager,
    InventoryResult,
    _count_csv_rows,
    _count_files_fast,
    _result_to_dict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def export_root(tmp_path: Path) -> Path:
    """Create a minimal export directory structure."""
    (tmp_path / "csv").mkdir()
    (tmp_path / "links").mkdir()
    (tmp_path / "meta").mkdir()
    (tmp_path / "files").mkdir()
    (tmp_path / "files_legacy").mkdir()
    return tmp_path


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    """Helper to write a CSV file."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def _create_dummy_csv(directory: Path, name: str, rows: int = 5) -> Path:
    """Create a dummy CSV with an Id column and N rows."""
    path = directory / f"{name}.csv"
    _write_csv(path, ["Id", "Name"], [[f"id_{i}", f"name_{i}"] for i in range(rows)])
    return path


def _create_dummy_file(directory: Path, name: str, size: int = 100) -> Path:
    """Create a dummy binary file."""
    path = directory / name
    path.write_bytes(b"x" * size)
    return path


def _create_sqlite_db(path: Path, tables: dict[str, int]) -> None:
    """Create a SQLite database with specified tables and row counts."""
    conn = sqlite3.connect(str(path))
    for table_name, row_count in tables.items():
        conn.execute(f'CREATE TABLE "{table_name}" (id TEXT)')
        for i in range(row_count):
            conn.execute(f'INSERT INTO "{table_name}" (id) VALUES (?)', (f"id_{i}",))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestCountCsvRows:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        assert _count_csv_rows(tmp_path / "nope.csv") == 0

    def test_empty_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        _write_csv(path, ["Id"], [])
        assert _count_csv_rows(path) == 0

    def test_csv_with_rows(self, tmp_path: Path) -> None:
        path = tmp_path / "data.csv"
        _write_csv(path, ["Id", "Name"], [["1", "a"], ["2", "b"], ["3", "c"]])
        assert _count_csv_rows(path) == 3


class TestCountFilesFast:
    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        count, size = _count_files_fast(tmp_path / "nope")
        assert count == 0
        assert size == 0

    def test_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        count, size = _count_files_fast(d)
        assert count == 0
        assert size == 0

    def test_flat_files(self, tmp_path: Path) -> None:
        d = tmp_path / "files"
        d.mkdir()
        (d / "a.bin").write_bytes(b"hello")
        (d / "b.bin").write_bytes(b"world!")
        count, size = _count_files_fast(d)
        assert count == 2
        assert size == 11

    def test_nested_files(self, tmp_path: Path) -> None:
        d = tmp_path / "files"
        d.mkdir()
        sub = d / "sub"
        sub.mkdir()
        (d / "a.bin").write_bytes(b"aaa")
        (sub / "b.bin").write_bytes(b"bb")
        count, size = _count_files_fast(d)
        assert count == 2
        assert size == 5


# ---------------------------------------------------------------------------
# CSV Objects check
# ---------------------------------------------------------------------------


class TestCheckCsvObjects:
    def test_all_present(self, export_root: Path) -> None:
        from sfdump.orchestrator import ESSENTIAL_OBJECTS

        for obj in ESSENTIAL_OBJECTS:
            _create_dummy_csv(export_root / "csv", obj)

        mgr = InventoryManager(export_root)
        cat = mgr._check_csv_objects()
        assert cat.status == CategoryStatus.COMPLETE
        assert cat.found_count >= len(ESSENTIAL_OBJECTS)
        assert cat.missing_objects == []

    def test_some_missing(self, export_root: Path) -> None:
        _create_dummy_csv(export_root / "csv", "Account")
        _create_dummy_csv(export_root / "csv", "Contact")

        mgr = InventoryManager(export_root)
        cat = mgr._check_csv_objects()
        assert cat.status == CategoryStatus.INCOMPLETE
        assert cat.found_count == 2
        assert len(cat.missing_objects) > 0

    def test_extra_objects_ok(self, export_root: Path) -> None:
        from sfdump.orchestrator import ESSENTIAL_OBJECTS

        for obj in ESSENTIAL_OBJECTS:
            _create_dummy_csv(export_root / "csv", obj)
        _create_dummy_csv(export_root / "csv", "CustomExtra__c")

        mgr = InventoryManager(export_root)
        cat = mgr._check_csv_objects()
        assert cat.status == CategoryStatus.COMPLETE
        assert "CustomExtra__c" in cat.extra_objects

    def test_no_csv_dir(self, tmp_path: Path) -> None:
        mgr = InventoryManager(tmp_path)
        cat = mgr._check_csv_objects()
        assert cat.status == CategoryStatus.NOT_CHECKED


# ---------------------------------------------------------------------------
# Attachments check
# ---------------------------------------------------------------------------


class TestCheckAttachments:
    def test_no_metadata(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        cat = mgr._check_attachments()
        assert cat.status == CategoryStatus.NOT_CHECKED

    def test_all_present(self, export_root: Path) -> None:
        # Create attachments metadata
        _write_csv(
            export_root / "links" / "attachments.csv",
            ["Id", "Name", "path", "sha256"],
            [
                ["att1", "file1.txt", "files_legacy/file1.txt", "abc"],
                ["att2", "file2.txt", "files_legacy/file2.txt", "def"],
            ],
        )
        # Create actual files
        _create_dummy_file(export_root / "files_legacy", "file1.txt")
        _create_dummy_file(export_root / "files_legacy", "file2.txt")

        mgr = InventoryManager(export_root)
        cat = mgr._check_attachments()
        assert cat.expected == 2
        assert cat.actual == 2
        assert cat.status == CategoryStatus.COMPLETE

    def test_missing_files(self, export_root: Path) -> None:
        _write_csv(
            export_root / "links" / "attachments.csv",
            ["Id", "Name", "path", "sha256"],
            [
                ["att1", "file1.txt", "files_legacy/file1.txt", "abc"],
                ["att2", "file2.txt", "files_legacy/file2.txt", "def"],
                ["att3", "file3.txt", "files_legacy/file3.txt", "ghi"],
            ],
        )
        # Only 1 of 3 files present
        _create_dummy_file(export_root / "files_legacy", "file1.txt")

        mgr = InventoryManager(export_root)
        cat = mgr._check_attachments()
        assert cat.expected == 3
        assert cat.actual == 1
        assert cat.missing == 2
        assert cat.status == CategoryStatus.INCOMPLETE

    def test_uses_verify_csv_when_present(self, export_root: Path) -> None:
        _write_csv(
            export_root / "links" / "attachments.csv",
            ["Id", "Name", "path", "sha256"],
            [["att1", "f1", "p1", "s1"]] * 10,
        )
        # Create missing CSV with 3 entries (verify output)
        _write_csv(
            export_root / "links" / "attachments_missing.csv",
            ["Id", "verify_error"],
            [["att2", "file-not-found"]] * 3,
        )

        mgr = InventoryManager(export_root)
        cat = mgr._check_attachments()
        assert cat.verified is True
        assert cat.missing == 3
        assert cat.status == CategoryStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# ContentVersions check
# ---------------------------------------------------------------------------


class TestCheckContentVersions:
    def test_no_metadata(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        cat = mgr._check_content_versions()
        assert cat.status == CategoryStatus.NOT_CHECKED

    def test_complete(self, export_root: Path) -> None:
        _write_csv(
            export_root / "links" / "content_versions.csv",
            ["Id", "Title", "path", "sha256"],
            [["cv1", "doc1", "files/doc1.pdf", "abc"]],
        )
        _create_dummy_file(export_root / "files", "doc1.pdf")

        mgr = InventoryManager(export_root)
        cat = mgr._check_content_versions()
        assert cat.expected == 1
        assert cat.actual == 1
        assert cat.status == CategoryStatus.COMPLETE


# ---------------------------------------------------------------------------
# Invoice PDFs check
# ---------------------------------------------------------------------------


class TestCheckInvoices:
    def test_no_invoice_csv(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        cat = mgr._check_invoices()
        assert cat.status == CategoryStatus.NOT_APPLICABLE

    def test_all_downloaded(self, export_root: Path) -> None:
        # Create invoice CSV with 3 Complete invoices
        _write_csv(
            export_root / "csv" / "c2g__codaInvoice__c.csv",
            ["Id", "Name", "c2g__InvoiceStatus__c"],
            [
                ["inv1", "SIN001001", "Complete"],
                ["inv2", "SIN001002", "Complete"],
                ["inv3", "SIN001003", "Discarded"],
            ],
        )
        # Create 2 PDFs (only 2 Complete expected)
        inv_dir = export_root / "invoices"
        inv_dir.mkdir()
        (inv_dir / "SIN001001.pdf").write_bytes(b"%PDF-fake")
        (inv_dir / "SIN001002.pdf").write_bytes(b"%PDF-fake")

        mgr = InventoryManager(export_root)
        cat = mgr._check_invoices()
        assert cat.expected == 2
        assert cat.actual == 2
        assert cat.missing == 0
        assert cat.status == CategoryStatus.COMPLETE

    def test_missing_pdfs(self, export_root: Path) -> None:
        _write_csv(
            export_root / "csv" / "c2g__codaInvoice__c.csv",
            ["Id", "Name", "c2g__InvoiceStatus__c"],
            [
                ["inv1", "SIN001001", "Complete"],
                ["inv2", "SIN001002", "Complete"],
            ],
        )
        inv_dir = export_root / "invoices"
        inv_dir.mkdir()
        (inv_dir / "SIN001001.pdf").write_bytes(b"%PDF-fake")

        mgr = InventoryManager(export_root)
        cat = mgr._check_invoices()
        assert cat.expected == 2
        assert cat.actual == 1
        assert cat.missing == 1
        assert cat.status == CategoryStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# Indexes check
# ---------------------------------------------------------------------------


class TestCheckIndexes:
    def test_no_links_dir(self, tmp_path: Path) -> None:
        mgr = InventoryManager(tmp_path)
        cat = mgr._check_indexes()
        assert cat.status == CategoryStatus.NOT_CHECKED

    def test_complete_indexes(self, export_root: Path) -> None:
        # Create some index files
        _write_csv(
            export_root / "links" / "Account_files_index.csv",
            ["record_id", "file_name", "path"],
            [["acc1", "doc.pdf", "files/doc.pdf"]],
        )
        # Create master index with all paths
        _write_csv(
            export_root / "meta" / "master_documents_index.csv",
            ["file_name", "local_path"],
            [["doc.pdf", "files/doc.pdf"], ["img.png", "files/img.png"]],
        )

        mgr = InventoryManager(export_root)
        cat = mgr._check_indexes()
        assert cat.files_index_count == 1
        assert cat.master_index_rows == 2
        assert cat.master_rows_with_path == 2
        assert cat.master_rows_missing_path == 0
        assert cat.status == CategoryStatus.COMPLETE

    def test_missing_paths_warning(self, export_root: Path) -> None:
        _write_csv(
            export_root / "links" / "Opp_files_index.csv",
            ["record_id", "file_name", "path"],
            [["opp1", "doc.pdf", "files/doc.pdf"]],
        )
        _write_csv(
            export_root / "meta" / "master_documents_index.csv",
            ["file_name", "local_path"],
            [["doc.pdf", "files/doc.pdf"], ["missing.pdf", ""]],
        )

        mgr = InventoryManager(export_root)
        cat = mgr._check_indexes()
        assert cat.master_rows_missing_path == 1
        assert cat.status == CategoryStatus.WARNING


# ---------------------------------------------------------------------------
# Database check
# ---------------------------------------------------------------------------


class TestCheckDatabase:
    def test_no_db(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        cat = mgr._check_database()
        assert cat.status == CategoryStatus.INCOMPLETE
        assert cat.db_exists is False

    def test_valid_db(self, export_root: Path) -> None:
        db_path = export_root / "meta" / "sfdata.db"
        _create_sqlite_db(db_path, {"Account": 10, "Contact": 5})

        mgr = InventoryManager(export_root)
        cat = mgr._check_database()
        assert cat.db_exists is True
        assert cat.table_count == 2
        assert cat.total_rows == 15
        assert cat.status == CategoryStatus.COMPLETE


# ---------------------------------------------------------------------------
# Full inventory run
# ---------------------------------------------------------------------------


class TestInventoryRun:
    def test_empty_export(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        result = mgr.run()
        assert result.duration_seconds >= 0
        assert result.export_root == str(export_root.resolve())

    def test_complete_export(self, export_root: Path) -> None:
        from sfdump.orchestrator import ESSENTIAL_OBJECTS

        # CSVs
        for obj in ESSENTIAL_OBJECTS:
            _create_dummy_csv(export_root / "csv", obj)

        # Attachments metadata + files
        _write_csv(
            export_root / "links" / "attachments.csv",
            ["Id", "Name", "path", "sha256"],
            [["a1", "f1", "files_legacy/f1", "s1"]],
        )
        _create_dummy_file(export_root / "files_legacy", "f1")

        # ContentVersions metadata + files
        _write_csv(
            export_root / "links" / "content_versions.csv",
            ["Id", "Title", "path", "sha256"],
            [["cv1", "d1", "files/d1", "s1"]],
        )
        _create_dummy_file(export_root / "files", "d1")

        # Master index (all with paths)
        _write_csv(
            export_root / "meta" / "master_documents_index.csv",
            ["file_name", "local_path"],
            [["f1", "files_legacy/f1"]],
        )

        # Database
        _create_sqlite_db(
            export_root / "meta" / "sfdata.db",
            {"Account": 5},
        )

        mgr = InventoryManager(export_root)
        result = mgr.run()
        assert result.csv_objects.status == CategoryStatus.COMPLETE
        assert result.attachments.status == CategoryStatus.COMPLETE
        assert result.content_versions.status == CategoryStatus.COMPLETE
        assert result.database.status == CategoryStatus.COMPLETE

    def test_overall_incomplete(self, export_root: Path) -> None:
        """If any category is INCOMPLETE, overall is INCOMPLETE."""
        # Only create a partial setup
        _write_csv(
            export_root / "links" / "attachments.csv",
            ["Id", "Name", "path", "sha256"],
            [["a1", "f1", "p1", "s1"], ["a2", "f2", "p2", "s2"]],
        )
        # No actual files → INCOMPLETE

        mgr = InventoryManager(export_root)
        result = mgr.run()
        assert result.attachments.status == CategoryStatus.INCOMPLETE
        assert result.overall_status == CategoryStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# Manifest write + serialisation
# ---------------------------------------------------------------------------


class TestManifest:
    def test_write_manifest(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        result = mgr.run()
        path = mgr.write_manifest(result)

        assert path.exists()
        assert path.name == "inventory.json"
        assert path.parent.name == "meta"

        data = json.loads(path.read_text())
        assert "overall_status" in data
        assert "csv_objects" in data
        assert "attachments" in data
        assert "duration_seconds" in data

    def test_result_to_dict_serialises_enums(self) -> None:
        result = InventoryResult()
        result.overall_status = CategoryStatus.COMPLETE
        result.csv_objects.status = CategoryStatus.INCOMPLETE

        data = _result_to_dict(result)
        assert data["overall_status"] == "COMPLETE"
        assert data["csv_objects"]["status"] == "INCOMPLETE"

    def test_manifest_is_valid_json(self, export_root: Path) -> None:
        mgr = InventoryManager(export_root)
        result = mgr.run()
        path = mgr.write_manifest(result)

        # Should be parseable
        data = json.loads(path.read_text())
        # Should round-trip
        json.dumps(data, indent=2)
