from __future__ import annotations

import csv
from pathlib import Path

from sfdump.command_files import build_files_index


class DummyAPI:
    """Minimal SalesforceAPI stand-in for build_files_index tests.

    Implements only iter_query() and returns synthetic data for:
      - Opportunity records
      - Attachment records
      - ContentDocumentLink records
    """

    def __init__(self) -> None:
        self.queries: list[str] = []

    def iter_query(self, soql: str):
        self.queries.append(soql)

        # 1) Parent records: Opportunity
        if soql.startswith("SELECT Id, Name FROM Opportunity"):
            return iter(
                [
                    {"Id": "OPP1", "Name": "Big Deal"},
                ]
            )

        # 2) Legacy Attachments for those parents
        if "FROM Attachment" in soql:
            return iter(
                [
                    {
                        "Id": "ATT1",
                        "Name": "Contract.pdf",
                        "ParentId": "OPP1",
                    }
                ]
            )

        # 3) Files (ContentDocumentLink + nested ContentDocument)
        if "FROM ContentDocumentLink" in soql:
            return iter(
                [
                    {
                        "Id": "CDL1",
                        "ContentDocumentId": "CD1",
                        "LinkedEntityId": "OPP1",
                        "ContentDocument": {
                            "Title": "Specs",
                            "FileExtension": "pdf",
                        },
                    }
                ]
            )

        # Fallback: no rows
        return iter([])


def _read_index_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_build_files_index_writes_attachment_and_file_rows(tmp_path: Path) -> None:
    """build_files_index should produce one Attachment and one File row for the parent.

    Scenario:
      - One Opportunity (OPP1 / "Big Deal")
      - One Attachment (ATT1 / Contract.pdf) with ParentId = OPP1
      - One File (ContentDocument CD1 / Specs.pdf) linked via ContentDocumentLink
    """
    out_dir = tmp_path / "out"
    api = DummyAPI()

    # Exercise the normal path: both Attachments and Files included
    build_files_index(
        api=api,
        index_object="Opportunity",
        out_dir=str(out_dir),
        include_content=True,
        include_attachments=True,
        max_batch_size=200,
    )

    csv_path = out_dir / "links" / "Opportunity_files_index.csv"
    assert csv_path.exists()

    rows = _read_index_csv(csv_path)
    # We expect exactly two rows: one Attachment, one File
    assert len(rows) == 2

    # Turn into a mapping of (file_source -> row) for easy assertions
    by_source = {row["file_source"]: row for row in rows}

    # Attachment row
    att = by_source["Attachment"]
    assert att["object_type"] == "Opportunity"
    assert att["record_id"] == "OPP1"
    assert att["record_name"] == "Big Deal"
    assert att["file_id"] == "ATT1"
    assert att["file_link_id"] == ""  # not applicable for legacy Attachment
    assert att["file_name"] == "Contract.pdf"
    assert att["file_extension"] == "pdf"

    # File (ContentDocument) row
    fil = by_source["File"]
    assert fil["object_type"] == "Opportunity"
    assert fil["record_id"] == "OPP1"
    assert fil["record_name"] == "Big Deal"
    assert fil["file_id"] == "CD1"
    assert fil["file_link_id"] == "CDL1"
    assert fil["file_name"] == "Specs"
    assert fil["file_extension"] == "pdf"

    # Sanity check that build_files_index actually issued multiple queries
    assert any("FROM Attachment" in q for q in api.queries)
    assert any("FROM ContentDocumentLink" in q for q in api.queries)
