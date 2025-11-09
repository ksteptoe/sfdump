import csv

from sfdump import files as files_mod


class ErrAPI:
    api_version = "v59.0"

    def __init__(self):
        self.calls = []

    def query_all_iter(self, soql: str):
        self.calls.append(soql)
        soql_up = soql.upper()
        if "FROM CONTENTVERSION" in soql_up:
            return iter(
                [
                    {
                        "attributes": {},
                        "Id": "068X",
                        "ContentDocumentId": "069ERR",
                        "Title": "bad",
                        "FileType": "PDF",
                    }
                ]
            )
        if "FROM CONTENTDOCUMENTLINK" in soql_up:
            return iter([])  # exercise empty links CSV creation
        if "FROM ATTACHMENT" in soql_up:
            return iter(
                [
                    {
                        "attributes": {},
                        "Id": "00PERR",
                        "ParentId": "001A",
                        "Name": "oops.txt",
                        "BodyLength": 1,
                        "ContentType": "text/plain",
                    }
                ]
            )
        return iter([])

    def download_path_to_file(self, rel: str, target: str):
        # simulate a failure for the first download to hit exception path
        raise RuntimeError("boom")


def _read_csv(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_dump_content_versions_with_download_error(tmp_path):
    api = ErrAPI()
    res = files_mod.dump_content_versions(api, str(tmp_path))
    # meta should exist with a row marking download_error and blank path/sha
    meta = _read_csv(res["meta_csv"])
    assert len(meta) == 1
    assert meta[0].get("download_error") == "boom"
    assert meta[0]["path"] == ""
    assert meta[0]["sha256"] == ""
    # links.csv should exist but be empty (headers only)
    with open(res["links_csv"], encoding="utf-8") as fh:
        content = fh.read()
    assert content.strip() == "" or content.startswith("ContentDocumentId")


def test_dump_attachments_with_download_error(tmp_path):
    api = ErrAPI()
    res = files_mod.dump_attachments(api, str(tmp_path))
    meta = _read_csv(res["meta_csv"])
    assert len(meta) == 1
    assert meta[0].get("download_error") == "boom"
    assert meta[0]["path"] == ""
    assert meta[0]["sha256"] == ""
