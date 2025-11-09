import csv
import os
from pathlib import Path

from sfdump import files as files_mod


class DummyAPI:
    api_version = "v59.0"

    def __init__(self):
        self._calls = []

    def query_all_iter(self, soql: str):
        self._calls.append(("query", soql))
        soql_up = soql.upper()
        if "FROM CONTENTVERSION" in soql_up:
            # Two content versions (latest)
            return iter(
                [
                    {
                        "attributes": {"type": "ContentVersion"},
                        "Id": "068CV001",
                        "ContentDocumentId": "069DOC111",
                        "Title": "Project Plan / v1",  # sanitization path
                        "FileType": "PDF",
                        "ContentSize": 1234,
                        "VersionNumber": 1,
                    },
                    {
                        "attributes": {"type": "ContentVersion"},
                        "Id": "068CV002",
                        "ContentDocumentId": "069DOC222",
                        "Title": "Budget&Forecast",  # sanitization path
                        "FileType": "XLSX",
                        "ContentSize": 4567,
                        "VersionNumber": 3,
                    },
                ]
            )
        if "FROM CONTENTDOCUMENTLINK" in soql_up:
            return iter(
                [
                    {
                        "attributes": {},
                        "ContentDocumentId": "069DOC111",
                        "LinkedEntityId": "001ACC1",
                        "ShareType": "V",
                        "Visibility": "AllUsers",
                    },
                    {
                        "attributes": {},
                        "ContentDocumentId": "069DOC222",
                        "LinkedEntityId": "006OPP9",
                        "ShareType": "C",
                        "Visibility": "InternalUsers",
                    },
                ]
            )
        if "FROM ATTACHMENT" in soql_up:
            return iter(
                [
                    {
                        "attributes": {},
                        "Id": "00PATT1",
                        "ParentId": "001ACC1",
                        "Name": "contract?.pdf",
                        "BodyLength": 99,
                        "ContentType": "application/pdf",
                    },
                    {
                        "attributes": {},
                        "Id": "00PATT2",
                        "ParentId": "006OPP9",
                        "Name": "note.txt",
                        "BodyLength": 10,
                        "ContentType": "text/plain",
                    },
                ]
            )
        return iter([])

    def download_path_to_file(self, rel: str, target: str) -> int:
        # emulate binary write; ensure directory exists
        Path(os.path.dirname(target)).mkdir(parents=True, exist_ok=True)
        payload = b"dummy-bytes-for-" + rel.encode("utf-8")
        with open(target, "wb") as f:
            f.write(payload)
        return len(payload)


def _read_csv(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_dump_content_versions(tmp_path):
    api = DummyAPI()
    out_dir = tmp_path / "out_cv"
    res = files_mod.dump_content_versions(api, str(out_dir), where="Title LIKE '%Budget%'")
    # basic return contract
    assert res["kind"] == "content_version"
    assert res["count"] == 2
    assert res["bytes"] > 0
    assert Path(res["meta_csv"]).exists()
    assert Path(res["links_csv"]).exists()
    assert Path(res["root"]).exists()

    # metadata CSV should have paths and sha256 for both rows (even if order varies)
    meta_rows = _read_csv(res["meta_csv"])
    assert len(meta_rows) == 2
    assert all("path" in r and "sha256" in r for r in meta_rows)
    # files actually written on disk
    for r in meta_rows:
        if r["path"]:
            assert Path(out_dir, r["path"]).exists()

    # links CSV should contain our two ContentDocumentLink rows
    link_rows = _read_csv(res["links_csv"])
    assert {r["ContentDocumentId"] for r in link_rows} == {"069DOC111", "069DOC222"}


def test_dump_attachments(tmp_path):
    api = DummyAPI()
    out_dir = tmp_path / "out_att"
    res = files_mod.dump_attachments(api, str(out_dir))
    assert res["kind"] == "attachment"
    assert res["links_csv"] is None
    assert res["count"] == 2
    assert res["bytes"] > 0
    assert Path(res["meta_csv"]).exists()
    assert Path(res["root"]).exists()

    # metadata CSV should list both attachments with paths & sha256
    meta_rows = _read_csv(res["meta_csv"])
    assert len(meta_rows) == 2
    for r in meta_rows:
        assert "path" in r and "sha256" in r
        if r["path"]:
            assert Path(out_dir, r["path"]).exists()
