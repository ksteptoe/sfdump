from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from sfdump.files import (
    dump_attachments,
    estimate_attachments,
    estimate_content_versions,
)

# ---------------------------------------------------------------------------
# Dummy API helpers
# ---------------------------------------------------------------------------


class DummyAPIEstimate:
    """Minimal API for estimate_* functions."""

    def __init__(self, records: List[Dict[str, Any]]) -> None:
        self._records = records
        self.queries: List[str] = []

    def query_all_iter(self, soql: str) -> Iterable[Dict[str, Any]]:
        self.queries.append(soql)
        for r in self._records:
            yield r


class DummyAPIAttachments:
    """Minimal API for dump_attachments.

    Implements:
      - api_version
      - query_all_iter(soql)
      - download_path_to_file(rel, target)
    """

    def __init__(self) -> None:
        self.api_version = "v60.0"
        self.queries: List[str] = []
        self.download_calls: List[tuple[str, str]] = []

    def query_all_iter(self, soql: str) -> Iterable[Dict[str, Any]]:
        self.queries.append(soql)
        # Single legacy Attachment record with attributes and extra noise.
        yield {
            "attributes": {
                "type": "Attachment",
                "url": "/services/data/v60.0/sobjects/Attachment/ATT1",
            },
            "Id": "ATT1",
            "ParentId": "PARENT1",
            "Name": "Contract.txt",
            "BodyLength": 3,
            "ContentType": "text/plain",
            "Extra__c": "ignored",
        }

    def download_path_to_file(self, rel: str, target: str) -> int:
        """Pretend to download and write exactly 3 bytes."""
        from pathlib import Path as _Path

        self.download_calls.append((rel, target))
        _Path(target).parent.mkdir(parents=True, exist_ok=True)
        _Path(target).write_bytes(b"abc")
        return 3


# ---------------------------------------------------------------------------
# estimate_* tests
# ---------------------------------------------------------------------------


def test_estimate_content_versions_aggregates_bytes_and_count() -> None:
    """estimate_content_versions should sum ContentSize and count records."""
    records = [
        {"Id": "CV1", "ContentSize": 10},
        {"Id": "CV2", "ContentSize": "5"},  # string, but castable to int
        {"Id": "CV3"},  # missing size -> treated as 0
    ]
    api = DummyAPIEstimate(records)

    res = estimate_content_versions(api)

    # 10 + 5 + 0 = 15 bytes, 3 records
    assert res["kind"] == "content_version (estimate)"
    assert res["count"] == 3
    assert res["bytes"] == 15
    assert res["root"] == "(estimate only)"

    # SOQL should contain the IsLatest filter
    assert len(api.queries) == 1
    soql = api.queries[0]
    assert "FROM ContentVersion" in soql
    assert "IsLatest = true" in soql


def test_estimate_attachments_aggregates_bytes_and_count() -> None:
    """estimate_attachments should sum BodyLength and count records."""
    records = [
        {"Id": "A1", "BodyLength": 100},
        {"Id": "A2", "BodyLength": "50"},
        {"Id": "A3"},  # treated as 0
    ]
    api = DummyAPIEstimate(records)

    res = estimate_attachments(api)

    # 100 + 50 + 0 = 150 bytes, 3 records
    assert res["kind"] == "attachment (estimate)"
    assert res["count"] == 3
    assert res["bytes"] == 150
    assert res["root"] == "(estimate only)"

    assert len(api.queries) == 1
    soql = api.queries[0]
    assert "FROM Attachment" in soql


# ---------------------------------------------------------------------------
# dump_attachments tests
# ---------------------------------------------------------------------------


def test_dump_attachments_downloads_and_writes_metadata(tmp_path: Path, monkeypatch) -> None:
    """dump_attachments should download attachments and write metadata via write_csv.

    We patch:
      - tqdm.tqdm to a no-op wrapper, to avoid progress bar behaviour.
      - write_csv to capture rows/fieldnames instead of touching the real filesystem.
      - sha256_of_file to a constant, to avoid depending on actual hashing.
    """
    from sfdump import files as files_mod

    api = DummyAPIAttachments()

    # Make tqdm a simple passthrough for deterministic iteration
    def fake_tqdm(iterable, *args, **kwargs):
        return iterable

    monkeypatch.setattr(files_mod, "tqdm", fake_tqdm, raising=True)

    # Capture what write_csv is called with
    captured: Dict[str, Any] = {}

    def fake_write_csv(path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
        captured["path"] = path
        captured["rows"] = rows
        captured["fieldnames"] = fieldnames

    monkeypatch.setattr(files_mod, "write_csv", fake_write_csv, raising=True)

    # Make sha256_of_file return a constant
    monkeypatch.setattr(files_mod, "sha256_of_file", lambda p: "HASH123", raising=True)

    out_dir = tmp_path / "export"
    res = dump_attachments(api, str(out_dir))

    # Validate high-level result dict
    assert res["kind"] == "attachment"
    assert res["count"] == 1
    assert res["bytes"] == 3
    assert "files_legacy" in str(res["root"])

    # Ensure we issued an Attachment query with the expected base SOQL
    assert len(api.queries) == 1
    soql = api.queries[0]
    assert "FROM Attachment" in soql
    assert "WHERE" not in soql  # no filter used in this test

    # We should have downloaded once, against the Attachment Body path
    assert len(api.download_calls) == 1
    rel, target = api.download_calls[0]
    assert "/sobjects/Attachment/ATT1/Body" in rel
    assert "files_legacy" in target

    # Check that our fake write_csv was called and that the metadata row looks sane
    assert captured["path"].endswith("attachments.csv")
    rows = captured["rows"]
    assert len(rows) == 1
    row = rows[0]

    # Row should contain the original fields plus path and sha256
    assert row["Id"] == "ATT1"
    assert row["ParentId"] == "PARENT1"
    assert row["Name"] == "Contract.txt"
    assert row["ContentType"] == "text/plain"
    assert row["path"]  # non-empty relative path
    assert row["sha256"] == "HASH123"

    # Internal SF 'attributes' key should have been removed
    assert "attributes" not in row
    # Other extra fields (like Extra__c) are allowed to pass through as metadata

    # Fieldnames should include the augmented fields
    fieldnames = captured["fieldnames"]
    for key in ("Id", "ParentId", "Name", "BodyLength", "ContentType", "path", "sha256"):
        assert key in fieldnames
