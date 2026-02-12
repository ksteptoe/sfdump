# tests/unit/test_command_docs_index.py
from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from sfdump.cli import cli
from sfdump.command_docs_index import _build_master_index


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Utility to write a tiny CSV from a list of dicts."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    import csv

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def test_build_master_index_happy_path(tmp_path: Path) -> None:
    """_build_master_index creates a single-row master index with enrichment.

    Scenario:
      - One Opportunity with one Attachment.
      - Attachment is linked via *_files_index.csv and attachments.csv.
      - Account and Opportunity CSVs provide basic business context.
    """
    export_root = tmp_path / "export-2025-11-16"
    csv_dir = export_root / "csv"
    links_dir = export_root / "links"

    # 1) Per-object index: Opportunity_files_index.csv
    _write_csv(
        links_dir / "Opportunity_files_index.csv",
        [
            {
                "object_type": "Opportunity",
                "record_id": "OPP1",
                "record_name": "Big Deal",
                "file_source": "Attachment",
                "file_id": "ATT1",
                "file_link_id": "",
                "file_name": "Contract.pdf",
                "file_extension": "pdf",
            }
        ],
    )

    # 2) Attachments metadata
    _write_csv(
        links_dir / "attachments.csv",
        [
            {
                "Id": "ATT1",
                "local_path": "files/Attachment/ATT1_Contract.pdf",
            }
        ],
    )

    # 3) Content metadata can be empty in this test
    _write_csv(links_dir / "content_versions.csv", [])

    # 4) Opportunity CSV
    _write_csv(
        csv_dir / "Opportunity.csv",
        [
            {
                "Id": "OPP1",
                "Name": "Big Deal",
                "StageName": "Closed Won",
                "Amount": "100000",
                "CloseDate": "2025-11-15",
                "AccountId": "ACC1",
            }
        ],
    )

    # 5) Account CSV
    _write_csv(
        csv_dir / "Account.csv",
        [
            {
                "Id": "ACC1",
                "Name": "MegaCorp",
            }
        ],
    )

    # --- run builder ---
    out_path, docs_with_path, docs_missing_path = _build_master_index(export_root)

    assert out_path == export_root / "meta" / "master_documents_index.csv"
    assert out_path.exists()
    assert docs_with_path == 1  # One document with a valid path
    assert docs_missing_path == 0  # No missing documents

    df = pd.read_csv(out_path, dtype=str).fillna("")

    # One row as per our synthetic data
    assert len(df) == 1

    row = df.iloc[0]

    # Core fields from index + attachments
    assert row["file_source"] == "Attachment"
    assert row["file_name"] == "Contract.pdf"
    assert row["file_extension"] == "pdf"
    assert row["local_path"] == "files/Attachment/ATT1_Contract.pdf"
    assert row["object_type"] == "Opportunity"
    assert row["record_id"] == "OPP1"
    assert row["record_name"] == "Big Deal"

    # Enriched fields from Opportunity / Account
    assert row.get("opp_name", "") == "Big Deal"
    assert row.get("opp_stage", "") == "Closed Won"
    assert row.get("opp_amount", "") == "100000"
    assert row.get("opp_close_date", "") == "2025-11-15"
    assert row.get("account_name", "") == "MegaCorp"


def test_docs_index_cli_builds_master_index(tmp_path: Path) -> None:
    """CLI 'sfdump docs-index' builds master_documents_index.csv in EXPORT_ROOT."""
    export_root = tmp_path / "export-2025-11-16"
    csv_dir = export_root / "csv"
    links_dir = export_root / "links"

    # Minimal data: just enough to produce one row
    _write_csv(
        links_dir / "Opportunity_files_index.csv",
        [
            {
                "object_type": "Opportunity",
                "record_id": "OPP1",
                "record_name": "Big Deal",
                "file_source": "Attachment",
                "file_id": "ATT1",
                "file_link_id": "",
                "file_name": "Contract.pdf",
                "file_extension": "pdf",
            }
        ],
    )
    _write_csv(
        links_dir / "attachments.csv",
        [
            {
                "Id": "ATT1",
                "local_path": "files/Attachment/ATT1_Contract.pdf",
            }
        ],
    )
    _write_csv(links_dir / "content_versions.csv", [])
    _write_csv(
        csv_dir / "Opportunity.csv",
        [
            {
                "Id": "OPP1",
                "Name": "Big Deal",
            }
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["docs-index", "--export-root", str(export_root)],
    )

    assert result.exit_code == 0, result.output
    master_path = export_root / "meta" / "master_documents_index.csv"
    assert master_path.exists()

    df = pd.read_csv(master_path, dtype=str).fillna("")
    assert len(df) == 1
    assert df.loc[0, "file_name"] == "Contract.pdf"


def test_build_master_index_detects_missing_files(tmp_path: Path) -> None:
    """_build_master_index returns counts of documents with/without local paths.

    This tests the validation that detects incomplete exports where documents
    are indexed but the actual files were not downloaded (e.g., due to chunking).
    """
    export_root = tmp_path / "export-test"
    links_dir = export_root / "links"

    # Create an index with 3 files: 1 Attachment with path, 2 Files without paths
    _write_csv(
        links_dir / "Opportunity_files_index.csv",
        [
            # Attachment with a valid path
            {
                "object_type": "Opportunity",
                "record_id": "OPP1",
                "record_name": "Deal 1",
                "file_source": "Attachment",
                "file_id": "ATT1",
                "file_link_id": "",
                "file_name": "Contract.pdf",
                "file_extension": "pdf",
            },
            # File (ContentVersion) - will have no path because content_versions.csv
            # doesn't have this ContentDocumentId
            {
                "object_type": "Opportunity",
                "record_id": "OPP1",
                "record_name": "Deal 1",
                "file_source": "File",
                "file_id": "DOC1",
                "file_link_id": "CDL1",
                "file_name": "Proposal.docx",
                "file_extension": "docx",
            },
            # Another File without a matching content_versions entry
            {
                "object_type": "Opportunity",
                "record_id": "OPP2",
                "record_name": "Deal 2",
                "file_source": "File",
                "file_id": "DOC2",
                "file_link_id": "CDL2",
                "file_name": "Report.xlsx",
                "file_extension": "xlsx",
            },
        ],
    )

    # Attachments metadata with valid path
    _write_csv(
        links_dir / "attachments.csv",
        [
            {
                "Id": "ATT1",
                "local_path": "files_legacy/00/ATT1_Contract.pdf",
            }
        ],
    )

    # Content versions CSV is empty - simulating incomplete export
    # where ContentVersions were not downloaded
    _write_csv(links_dir / "content_versions.csv", [])

    # Run builder
    out_path, docs_with_path, docs_missing_path = _build_master_index(export_root)

    assert out_path.exists()
    assert docs_with_path == 1  # Only the Attachment has a path
    assert docs_missing_path == 2  # The two Files have no paths

    # Verify the CSV content
    df = pd.read_csv(out_path, dtype=str).fillna("")
    assert len(df) == 3

    # Check that the attachment has a path
    att_row = df[df["file_source"] == "Attachment"].iloc[0]
    assert att_row["local_path"] != ""
    assert "ATT1_Contract.pdf" in att_row["local_path"]

    # Check that the Files have empty paths
    file_rows = df[df["file_source"] == "File"]
    assert len(file_rows) == 2
    for _, row in file_rows.iterrows():
        assert row["local_path"] == ""


def test_build_master_index_includes_invoice_pdfs(tmp_path: Path) -> None:
    """InvoicePDF entries appear in master index with Opp/Account enrichment."""
    export_root = tmp_path / "export"
    csv_dir = export_root / "csv"
    links_dir = export_root / "links"

    # Invoice PDF files_index (produced by build_invoice_pdf_index)
    _write_csv(
        links_dir / "c2g__codaInvoice__c_invoice_pdfs_files_index.csv",
        [
            {
                "object_type": "c2g__codaInvoice__c",
                "record_id": "INV1",
                "record_name": "SIN001001",
                "file_source": "InvoicePDF",
                "file_id": "INV1",
                "file_link_id": "",
                "file_name": "SIN001001.pdf",
                "file_extension": "pdf",
                "path": "invoices/SIN001001.pdf",
                "content_type": "application/pdf",
                "size_bytes": "12345",
            },
            {
                "object_type": "c2g__codaInvoice__c",
                "record_id": "INV2",
                "record_name": "SIN001002",
                "file_source": "InvoicePDF",
                "file_id": "INV2",
                "file_link_id": "",
                "file_name": "SIN001002.pdf",
                "file_extension": "pdf",
                "path": "",
                "content_type": "application/pdf",
                "size_bytes": "",
            },
        ],
    )

    # Empty attachment/content metadata (invoices don't use them)
    _write_csv(links_dir / "attachments.csv", [])
    _write_csv(links_dir / "content_versions.csv", [])

    # Invoice CSV with FK to Opportunity and Account
    _write_csv(
        csv_dir / "c2g__codaInvoice__c.csv",
        [
            {
                "Id": "INV1",
                "Name": "SIN001001",
                "c2g__InvoiceStatus__c": "Complete",
                "c2g__Opportunity__c": "OPP1",
                "c2g__Account__c": "ACC1",
            },
            {
                "Id": "INV2",
                "Name": "SIN001002",
                "c2g__InvoiceStatus__c": "Complete",
                "c2g__Opportunity__c": "OPP1",
                "c2g__Account__c": "ACC1",
            },
        ],
    )

    # Opportunity CSV
    _write_csv(
        csv_dir / "Opportunity.csv",
        [
            {
                "Id": "OPP1",
                "Name": "Big Deal",
                "AccountId": "ACC1",
            }
        ],
    )

    # Account CSV
    _write_csv(
        csv_dir / "Account.csv",
        [
            {
                "Id": "ACC1",
                "Name": "MegaCorp",
            }
        ],
    )

    out_path, docs_with_path, docs_missing_path = _build_master_index(export_root)

    assert out_path.exists()
    assert docs_with_path == 1  # SIN001001 has a path
    assert docs_missing_path == 1  # SIN001002 has no path

    df = pd.read_csv(out_path, dtype=str).fillna("")
    assert len(df) == 2

    # Both should be InvoicePDF source
    assert list(df["file_source"]) == ["InvoicePDF", "InvoicePDF"]

    # Check first invoice has local_path, second does not
    row1 = df[df["record_name"] == "SIN001001"].iloc[0]
    row2 = df[df["record_name"] == "SIN001002"].iloc[0]
    assert row1["local_path"] == "invoices/SIN001001.pdf"
    assert row2["local_path"] == ""

    # Enrichment: both should have opp_name and account_name
    assert row1.get("opp_name", "") == "Big Deal"
    assert row1.get("account_name", "") == "MegaCorp"
    assert row2.get("opp_name", "") == "Big Deal"
    assert row2.get("account_name", "") == "MegaCorp"


def test_docs_index_cli_warns_on_missing_files(tmp_path: Path) -> None:
    """CLI shows warning when documents are missing local files."""
    export_root = tmp_path / "export-test"
    links_dir = export_root / "links"
    csv_dir = export_root / "csv"

    # Create index with files that have no content_versions match
    _write_csv(
        links_dir / "Opportunity_files_index.csv",
        [
            {
                "object_type": "Opportunity",
                "record_id": "OPP1",
                "record_name": "Deal",
                "file_source": "File",
                "file_id": "DOC1",
                "file_link_id": "CDL1",
                "file_name": "Missing.pdf",
                "file_extension": "pdf",
            },
        ],
    )
    _write_csv(links_dir / "attachments.csv", [])
    _write_csv(links_dir / "content_versions.csv", [])
    csv_dir.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["docs-index", "--export-root", str(export_root)],
    )

    assert result.exit_code == 0, result.output
    assert "Not yet downloaded: 1" in result.output
    assert "File: 0/1 downloaded" in result.output
