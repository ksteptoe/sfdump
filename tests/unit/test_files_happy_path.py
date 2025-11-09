from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from sfdump import files as files_mod


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class _APIHappy:
    api_version = "v59.0"

    def __init__(self):
        self._cv = [
            {
                "Id": "068A",
                "ContentDocumentId": "069D",
                "Title": "Report 2025",
                "FileType": "PDF",
                "ContentSize": 6,
                "VersionNumber": 1,
                "attributes": {"type": "ContentVersion"},
            }
        ]
        self._att = [
            {
                "Id": "00P1",
                "ParentId": "001ACC",
                "Name": "legacy.txt",
                "BodyLength": 3,
                "ContentType": "text/plain",
                "attributes": {"type": "Attachment"},
            }
        ]

    def query_all_iter(self, soql: str):
        up = soql.upper()
        if "FROM CONTENTVERSION" in up:
            for r in self._cv:
                yield dict(r)
        elif "FROM CONTENTDOCUMENTLINK" in up:
            yield {
                "ContentDocumentId": "069D",
                "LinkedEntityId": "001ACC",
                "ShareType": "V",
                "Visibility": "AllUsers",
            }
        elif "FROM ATTACHMENT" in up:
            for r in self._att:
                yield dict(r)
        else:
            return iter(())

    def download_path_to_file(self, rel: str, target: str):
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        if "ContentVersion" in rel:
            data = b"123456"  # 6 bytes
        else:
            data = b"abc"  # 3 bytes
        p.write_bytes(data)
        return len(data)


def _read_csv_dicts(path: str):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_dump_content_versions_nonempty(tmp_path):
    api = _APIHappy()
    out_dir = tmp_path / "exp"

    res = files_mod.dump_content_versions(api, str(out_dir), where=None, max_workers=4)
    assert res["kind"] == "content_version"
    assert res["count"] == 1
    assert res["bytes"] == 6
    assert Path(res["root"]).is_dir()

    rows = _read_csv_dicts(res["meta_csv"])
    assert len(rows) == 1
    r = rows[0]
    assert r["path"].replace("\\", "/").startswith("files/")
    assert r["sha256"] == _sha256_bytes(b"123456")

    links = _read_csv_dicts(res["links_csv"])
    assert len(links) == 1
    assert links[0]["ContentDocumentId"] == "069D"


def test_dump_attachments_nonempty(tmp_path):
    api = _APIHappy()
    out_dir = tmp_path / "exp2"

    res = files_mod.dump_attachments(api, str(out_dir), where=None, max_workers=2)
    assert res["kind"] == "attachment"
    assert res["count"] == 1
    assert res["bytes"] == 3
    assert Path(res["root"]).is_dir()

    rows = _read_csv_dicts(res["meta_csv"])
    assert len(rows) == 1
    r = rows[0]
    assert r["path"].replace("\\", "/").startswith("files_legacy/")
    assert r["sha256"] == _sha256_bytes(b"abc")
