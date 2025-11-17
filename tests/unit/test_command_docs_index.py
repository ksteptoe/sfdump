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
    links_dir = export_root / "files" / "links"

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
    out_path = _build_master_index(export_root)

    assert out_path == export_root / "meta" / "master_documents_index.csv"
    assert out_path.exists()

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
    links_dir = export_root / "files" / "links"

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
