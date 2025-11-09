import csv
from pathlib import Path

from sfdump import files as files_mod


class EmptyAPI:
    api_version = "v59.0"

    def query_all_iter(self, soql: str):
        up = soql.upper()
        if "FROM CONTENTVERSION" in up:
            return iter([])
        if "FROM CONTENTDOCUMENTLINK" in up:
            return iter([])
        if "FROM ATTACHMENT" in up:
            return iter([])
        return iter([])

    def download_path_to_file(self, rel: str, target: str):
        raise AssertionError("Should not be called for empty sets")


def _read_csv_rows(path: str):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_dump_content_versions_empty(tmp_path):
    api = EmptyAPI()
    res = files_mod.dump_content_versions(api, str(tmp_path))
    assert res["kind"] == "content_version"
    assert res["count"] == 0
    assert res["bytes"] == 0
    assert Path(res["meta_csv"]).exists()
    assert Path(res["links_csv"]).exists()

    # Both CSVs should be empty or header-only
    meta_rows = _read_csv_rows(res["meta_csv"])
    link_rows = _read_csv_rows(res["links_csv"])
    assert isinstance(meta_rows, list) and isinstance(link_rows, list)
    assert len(meta_rows) in (0, 1)
    assert len(link_rows) in (0, 1)


def test_dump_attachments_empty(tmp_path):
    api = EmptyAPI()
    res = files_mod.dump_attachments(api, str(tmp_path))
    assert res["kind"] == "attachment"
    assert res["count"] == 0
    assert res["bytes"] == 0
    assert Path(res["meta_csv"]).exists()
    meta_rows = _read_csv_rows(res["meta_csv"])
    assert len(meta_rows) in (0, 1)


def test__safe_target_shards_into_two_letter_dir(tmp_path):
    target = files_mod._safe_target(str(tmp_path), "My Report.pdf")
    parts = Path(target).parts
    shard, fname = parts[-2], parts[-1]
    assert len(shard) == 2 and shard.islower()
    assert fname.lower().endswith(".pdf")
