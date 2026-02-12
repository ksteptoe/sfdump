"""Unit tests for command_sins — invoice PDF bulk download."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sfdump.command_sins import (
    InvoiceRecord,
    _download_one,
    _write_metadata,
    build_invoice_pdf_index,
    download_invoice_pdfs,
    read_invoices,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def invoice_csv(tmp_path: Path) -> Path:
    """Create a minimal invoice CSV with mixed statuses."""
    csv_path = tmp_path / "c2g__codaInvoice__c.csv"
    rows = [
        {
            "Id": "a1J000001",
            "Name": "SIN001001",
            "c2g__InvoiceStatus__c": "Complete",
        },
        {
            "Id": "a1J000002",
            "Name": "SIN001002",
            "c2g__InvoiceStatus__c": "Complete",
        },
        {
            "Id": "a1J000003",
            "Name": "SIN001003",
            "c2g__InvoiceStatus__c": "Discarded",
        },
        {
            "Id": "a1J000004",
            "Name": "SIN001004",
            "c2g__InvoiceStatus__c": "In Progress",
        },
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Id", "Name", "c2g__InvoiceStatus__c"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture()
def out_dir(tmp_path: Path) -> Path:
    d = tmp_path / "invoices"
    d.mkdir()
    return d


FAKE_PDF = b"%PDF-1.4 fake content"


# ---------------------------------------------------------------------------
# read_invoices
# ---------------------------------------------------------------------------


class TestReadInvoices:
    def test_filters_complete(self, invoice_csv: Path):
        result = read_invoices(invoice_csv, "Complete")
        assert len(result) == 2
        assert all(inv.status == "Complete" for inv in result)

    def test_filters_discarded(self, invoice_csv: Path):
        result = read_invoices(invoice_csv, "Discarded")
        assert len(result) == 1
        assert result[0].name == "SIN001003"

    def test_no_filter_returns_all(self, invoice_csv: Path):
        result = read_invoices(invoice_csv, "")
        assert len(result) == 4

    def test_names_and_ids(self, invoice_csv: Path):
        result = read_invoices(invoice_csv, "Complete")
        assert result[0].id == "a1J000001"
        assert result[0].name == "SIN001001"
        assert result[1].id == "a1J000002"
        assert result[1].name == "SIN001002"


# ---------------------------------------------------------------------------
# _download_one
# ---------------------------------------------------------------------------


class TestDownloadOne:
    def test_successful_download(self, out_dir: Path):
        session = MagicMock()
        resp = MagicMock()
        resp.content = FAKE_PDF
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        inv = InvoiceRecord(id="a1J000001", name="SIN001001", status="Complete")
        result = _download_one(session, "https://example.my.salesforce.com", inv, out_dir)

        assert result.success
        assert not result.skipped
        assert result.size == len(FAKE_PDF)
        assert (out_dir / "SIN001001.pdf").read_bytes() == FAKE_PDF

    def test_skips_existing(self, out_dir: Path):
        # Pre-create the PDF
        pdf_path = out_dir / "SIN001001.pdf"
        pdf_path.write_bytes(FAKE_PDF)

        session = MagicMock()
        inv = InvoiceRecord(id="a1J000001", name="SIN001001", status="Complete")
        result = _download_one(session, "https://example.my.salesforce.com", inv, out_dir)

        assert result.success
        assert result.skipped
        session.get.assert_not_called()

    def test_force_redownloads(self, out_dir: Path):
        # Pre-create the PDF
        pdf_path = out_dir / "SIN001001.pdf"
        pdf_path.write_bytes(b"%PDF-old")

        session = MagicMock()
        resp = MagicMock()
        resp.content = FAKE_PDF
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        inv = InvoiceRecord(id="a1J000001", name="SIN001001", status="Complete")
        result = _download_one(
            session, "https://example.my.salesforce.com", inv, out_dir, force=True
        )

        assert result.success
        assert not result.skipped
        assert pdf_path.read_bytes() == FAKE_PDF

    def test_rejects_non_pdf(self, out_dir: Path):
        session = MagicMock()
        resp = MagicMock()
        resp.content = b"<html>Error</html>"
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        inv = InvoiceRecord(id="a1J000001", name="SIN001001", status="Complete")
        result = _download_one(session, "https://example.my.salesforce.com", inv, out_dir)

        assert not result.success
        assert "not a PDF" in result.error

    def test_handles_request_error(self, out_dir: Path):
        session = MagicMock()
        import requests

        session.get.side_effect = requests.ConnectionError("timeout")

        inv = InvoiceRecord(id="a1J000001", name="SIN001001", status="Complete")
        result = _download_one(session, "https://example.my.salesforce.com", inv, out_dir)

        assert not result.success
        assert "timeout" in result.error


# ---------------------------------------------------------------------------
# _write_metadata
# ---------------------------------------------------------------------------


class TestWriteMetadata:
    def test_writes_csv(self, out_dir: Path):
        invoices = [
            InvoiceRecord(id="a1J1", name="SIN001", status="Complete"),
            InvoiceRecord(id="a1J2", name="SIN002", status="Complete"),
        ]
        # Simulate SIN001 downloaded, SIN002 failed
        (out_dir / "SIN001.pdf").write_bytes(FAKE_PDF)
        failed = [(invoices[1], "connection error")]

        _write_metadata(out_dir, invoices, failed)

        meta_path = out_dir / "invoice_pdfs_metadata.csv"
        assert meta_path.exists()
        with open(meta_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["DownloadStatus"] == "ok"
        assert rows[1]["DownloadStatus"] == "failed"


# ---------------------------------------------------------------------------
# download_invoice_pdfs (integration-style with mocked HTTP)
# ---------------------------------------------------------------------------


class TestDownloadInvoicePdfs:
    @patch("sfdump.command_sins.requests.Session")
    def test_downloads_all(self, mock_session_cls, invoice_csv: Path, out_dir: Path):
        session = MagicMock()
        mock_session_cls.return_value = session
        resp = MagicMock()
        resp.content = FAKE_PDF
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        downloaded, skipped, failed = download_invoice_pdfs(
            csv_path=invoice_csv,
            out_dir=out_dir,
            token="fake-token",
            instance_url="https://example.my.salesforce.com",
            status_filter="Complete",
            workers=1,
        )

        assert downloaded == 2
        assert skipped == 0
        assert failed == 0
        assert (out_dir / "SIN001001.pdf").exists()
        assert (out_dir / "SIN001002.pdf").exists()
        assert (out_dir / "invoice_pdfs_metadata.csv").exists()

    @patch("sfdump.command_sins.requests.Session")
    def test_resumes_skips_existing(self, mock_session_cls, invoice_csv: Path, out_dir: Path):
        # Pre-create one PDF
        (out_dir / "SIN001001.pdf").write_bytes(FAKE_PDF)

        session = MagicMock()
        mock_session_cls.return_value = session
        resp = MagicMock()
        resp.content = FAKE_PDF
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        downloaded, skipped, failed = download_invoice_pdfs(
            csv_path=invoice_csv,
            out_dir=out_dir,
            token="fake-token",
            instance_url="https://example.my.salesforce.com",
            workers=1,
        )

        assert downloaded == 1
        assert skipped == 1
        assert failed == 0

    @patch("sfdump.command_sins.requests.Session")
    def test_no_invoices_found(self, mock_session_cls, invoice_csv: Path, out_dir: Path):
        downloaded, skipped, failed = download_invoice_pdfs(
            csv_path=invoice_csv,
            out_dir=out_dir,
            token="fake-token",
            instance_url="https://example.my.salesforce.com",
            status_filter="Nonexistent",
            workers=1,
        )

        assert downloaded == 0
        assert skipped == 0
        assert failed == 0


# ---------------------------------------------------------------------------
# build_invoice_pdf_index
# ---------------------------------------------------------------------------


class TestBuildInvoicePdfIndex:
    def test_creates_index_with_all_invoices(self, tmp_path: Path, invoice_csv: Path):
        """Index should have a row for every Complete invoice."""
        invoices_dir = tmp_path / "invoices"
        invoices_dir.mkdir()
        export_root = tmp_path

        count = build_invoice_pdf_index(invoice_csv, invoices_dir, export_root)
        assert count == 2  # 2 Complete invoices

        index_path = tmp_path / "links" / "c2g__codaInvoice__c_invoice_pdfs_files_index.csv"
        assert index_path.exists()
        with open(index_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["record_name"] == "SIN001001"
        assert rows[0]["file_source"] == "InvoicePDF"
        assert rows[0]["file_name"] == "SIN001001.pdf"
        assert rows[0]["file_extension"] == "pdf"

    def test_path_populated_for_downloaded_pdfs(self, tmp_path: Path, invoice_csv: Path):
        """Downloaded PDFs should have a relative path; missing ones should not."""
        invoices_dir = tmp_path / "invoices"
        invoices_dir.mkdir()
        (invoices_dir / "SIN001001.pdf").write_bytes(FAKE_PDF)
        # SIN001002.pdf intentionally not created
        export_root = tmp_path

        build_invoice_pdf_index(invoice_csv, invoices_dir, export_root)

        index_path = tmp_path / "links" / "c2g__codaInvoice__c_invoice_pdfs_files_index.csv"
        with open(index_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # First invoice has a PDF on disk
        assert rows[0]["path"] == "invoices/SIN001001.pdf"
        assert rows[0]["size_bytes"] == str(len(FAKE_PDF))

        # Second invoice has no PDF — path and size should be empty
        assert rows[1]["path"] == ""
        assert rows[1]["size_bytes"] == ""

    def test_empty_csv(self, tmp_path: Path):
        """No matching invoices should return 0 and not create an index."""
        csv_path = tmp_path / "empty.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Id", "Name", "c2g__InvoiceStatus__c"])
        invoices_dir = tmp_path / "invoices"
        invoices_dir.mkdir()

        count = build_invoice_pdf_index(csv_path, invoices_dir, tmp_path)
        assert count == 0
