# tests/unit/test_manifest_write_and_scan.py
from __future__ import annotations

import csv
import json
from pathlib import Path

from sfdump.manifest import (
    FilesExport,
    Manifest,
    ObjectExport,
    _count_csv_rows,
    _rel_if,
    _sum_dir_bytes,
    scan_files,
    scan_objects,
    write_manifest,
)


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def test_count_csv_rows_and_missing(tmp_path):
    # header + 2 data rows → expect 2
    p = tmp_path / "data.csv"
    _write_csv(p, ["Id", "Name"], [["1", "A"], ["2", "B"]])
    assert _count_csv_rows(str(p)) == 2

    # missing file → 0
    assert _count_csv_rows(str(tmp_path / "missing.csv")) == 0


def test_sum_dir_bytes(tmp_path):
    root = tmp_path / "files"
    (root / "a").mkdir(parents=True, exist_ok=True)
    (root / "a" / "one.bin").write_bytes(b"abcd")  # 4
    (root / "a" / "two.bin").write_bytes(b"xyz")  # 3
    (root / "b").mkdir()
    (root / "b" / "three.bin").write_bytes(b"hello")  # 5
    # total = 12
    assert _sum_dir_bytes(str(root)) == 12


def test_scan_objects(tmp_path):
    csv_root = tmp_path / "csv"
    csv_root.mkdir()
    # valid CSVs
    _write_csv(csv_root / "Account.csv", ["Id", "Name"], [["1", "Acme"], ["2", "Beta"]])
    _write_csv(csv_root / "Contact.csv", ["Id"], [["3"], ["4"], ["5"]])
    # non-csv should be ignored
    (csv_root / "notes.txt").write_text("ignore")

    objs = scan_objects(str(csv_root))
    # deterministic ordering by filename
    names = [o.name for o in objs]
    assert names == ["Account", "Contact"]
    rows_by_name = {o.name: o.rows for o in objs}
    assert rows_by_name["Account"] == 2
    assert rows_by_name["Contact"] == 3
    # paths are absolute here (scan_* returns absolute paths as written)
    assert all(Path(o.csv).is_file() for o in objs)

    # non-existent root → empty list
    assert scan_objects(str(tmp_path / "does_not_exist")) == []


def test_scan_files_contentversion_and_attachments(tmp_path):
    out_dir = tmp_path / "out"
    links = out_dir / "links"
    files_cv = out_dir / "files"
    files_legacy = out_dir / "files_legacy"

    # Prepare ContentVersion metadata + links + actual binary payloads
    _write_csv(
        links / "content_versions.csv",
        [
            "Id",
            "ContentDocumentId",
            "Title",
            "FileType",
            "ContentSize",
            "VersionNumber",
            "path",
            "sha256",
        ],
        [["068x", "069a", "Doc1", "PDF", "10", "1", "files/ab/069a_Doc1.pdf", "deadbeef"]],
    )
    _write_csv(
        links / "content_document_links.csv",
        ["ContentDocumentId", "LinkedEntityId", "ShareType", "Visibility"],
        [["069a", "001ACC", "V", "AllUsers"]],
    )
    (files_cv / "ab").mkdir(parents=True, exist_ok=True)
    (files_cv / "ab" / "069a_Doc1.pdf").write_bytes(b"123456")  # 6 bytes → bytes sum > 0

    # Prepare Attachments metadata + legacy files
    _write_csv(
        links / "attachments.csv",
        ["Id", "ParentId", "Name", "BodyLength", "ContentType", "path", "sha256"],
        [["00P1", "001ACC", "att.txt", "3", "text/plain", "files_legacy/aa/00P1_att.txt", "bead"]],
    )
    (files_legacy / "aa").mkdir(parents=True, exist_ok=True)
    (files_legacy / "aa" / "00P1_att.txt").write_text("abc")  # 3 bytes

    results = scan_files(str(out_dir))
    # We expect two entries: content_version and attachment
    kinds = {f.kind for f in results}
    assert kinds == {"content_version", "attachment"}

    cv = next(f for f in results if f.kind == "content_version")
    assert cv.count == 1
    assert cv.links_csv and Path(cv.links_csv).is_file()
    assert cv.bytes > 0
    assert Path(cv.meta_csv).is_file()
    assert Path(cv.root).is_dir()

    att = next(f for f in results if f.kind == "attachment")
    assert att.count == 1
    assert att.links_csv is None  # by design for attachments
    assert att.bytes > 0
    assert Path(att.meta_csv).is_file()
    assert Path(att.root).is_dir()


def test_write_manifest_makes_paths_relative(tmp_path):
    # Build absolute paths first
    base = tmp_path / "export_root"
    csv_root = base / "csv"
    files_root = base / "files"
    links_dir = base / "links"
    csv_root.mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)
    links_dir.mkdir(parents=True, exist_ok=True)

    obj = ObjectExport(name="Account", csv=str(csv_root / "Account.csv"), rows=2)
    fil = FilesExport(
        kind="content_version",
        meta_csv=str(links_dir / "content_versions.csv"),
        links_csv=str(links_dir / "content_document_links.csv"),
        count=1,
        bytes=123,
        root=str(files_root),
    )
    mf = Manifest(
        generated_utc="2025-11-09T12:00:00Z",
        org_id="ORGID",
        username="user@example.com",
        instance_url="https://example.my.salesforce.com",
        api_version="v59.0",
        csv_root=str(csv_root),
        files=[fil],
        objects=[obj],
    )

    out_manifest = base / "manifest.json"
    write_manifest(str(out_manifest), mf)

    # Validate JSON and that paths are now relative to `base` (normalize for Windows)
    payload = json.loads(out_manifest.read_text(encoding="utf-8"))

    def norm(p):
        return str(p).replace("\\", "/")

    assert norm(payload["csv_root"]) == "csv"
    assert norm(payload["files"][0]["meta_csv"]) == "links/content_versions.csv"
    assert norm(payload["files"][0]["links_csv"]) == "links/content_document_links.csv"
    assert norm(payload["files"][0]["root"]) == "files"
    assert norm(payload["objects"][0]["csv"]) == "csv/Account.csv"


def test_rel_if_helper(tmp_path):
    base = tmp_path / "x"
    base.mkdir()
    abs_file = tmp_path / "x" / "y" / "file.txt"
    abs_file.parent.mkdir(parents=True, exist_ok=True)
    abs_file.write_text("ok", encoding="utf-8")

    # None → None
    assert _rel_if(None, str(base)) is None
    # Absolute → relative (normalize for Windows)
    rel = _rel_if(str(abs_file), str(base))
    assert rel.replace("\\", "/").endswith("y/file.txt")
