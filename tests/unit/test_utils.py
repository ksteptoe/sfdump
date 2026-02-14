# tests/unit/test_utils.py
import csv
from pathlib import Path

from sfdump.utils import ensure_dir, find_file_on_disk, sanitize_filename, sha256_of_file, write_csv


def test_ensure_dir_idempotent(tmp_path):
    d = tmp_path / "a" / "b"
    ensure_dir(str(d))
    assert d.exists() and d.is_dir()
    # second call should be a no-op
    ensure_dir(str(d))
    assert d.exists() and d.is_dir()


def test_sanitize_filename_various():
    forbidden = r'\\/:*?"<>|'

    # Normalizes whitespace and slashes; removes only OS-forbidden chars
    s1 = sanitize_filename("  Project Plan / v1  ")
    assert s1.strip() == s1
    assert not any(c in s1 for c in forbidden)
    # spaces normalized (typically underscores) and words preserved
    assert " " not in s1
    assert "Project" in s1 and "Plan" in s1 and "v1" in s1

    # Keeps extension; may keep symbols like & depending on implementation
    s2 = sanitize_filename("Budget&Forecast*?.xlsx")
    assert s2.endswith(".xlsx")
    assert not any(c in s2 for c in forbidden)
    assert " " not in s2
    # base name still non-empty before extension
    assert s2[:-5]

    # Whitespace-only → implementation fallback string
    assert sanitize_filename("   ") == "file"


def test_sha256_of_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    # Known sha256('abc')
    assert (
        sha256_of_file(str(p)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_write_csv_creates_and_orders_headers(tmp_path):
    rows = [{"b": 2, "a": 1}, {"a": 3, "b": 4, "c": 5}]
    f = tmp_path / "out.csv"
    write_csv(str(f), rows, fieldnames=["a", "b", "c"])
    assert f.exists()
    with open(f, newline="", encoding="utf-8") as fh:
        r = list(csv.DictReader(fh))
    assert r == [{"a": "1", "b": "2", "c": ""}, {"a": "3", "b": "4", "c": "5"}]


class TestFindFileOnDisk:
    def test_finds_content_version_file(self, tmp_path: Path):
        """Finds a ContentVersion file under files/<shard>/<id>_*."""
        fdir = tmp_path / "files" / "do"
        fdir.mkdir(parents=True)
        (fdir / "DOC123_Proposal.docx").write_bytes(b"data")

        result = find_file_on_disk(tmp_path, "DOC123", "File")
        assert result == "files/do/DOC123_Proposal.docx"

    def test_finds_attachment_file(self, tmp_path: Path):
        """Finds an Attachment file under files_legacy/<shard>/<id>_*."""
        fdir = tmp_path / "files_legacy" / "at"
        fdir.mkdir(parents=True)
        (fdir / "ATT99_Contract.pdf").write_bytes(b"data")

        result = find_file_on_disk(tmp_path, "ATT99", "Attachment")
        assert result == "files_legacy/at/ATT99_Contract.pdf"

    def test_returns_empty_when_no_match(self, tmp_path: Path):
        """Returns empty string when no file is found on disk."""
        (tmp_path / "files" / "do").mkdir(parents=True)
        assert find_file_on_disk(tmp_path, "DOC999", "File") == ""

    def test_returns_empty_when_multiple_matches(self, tmp_path: Path):
        """Returns empty string when multiple files match (ambiguous)."""
        fdir = tmp_path / "files" / "do"
        fdir.mkdir(parents=True)
        (fdir / "DOC1_v1.pdf").write_bytes(b"a")
        (fdir / "DOC1_v2.pdf").write_bytes(b"b")

        assert find_file_on_disk(tmp_path, "DOC1", "File") == ""

    def test_returns_empty_for_empty_file_id(self, tmp_path: Path):
        assert find_file_on_disk(tmp_path, "", "File") == ""

    def test_returns_empty_when_shard_dir_missing(self, tmp_path: Path):
        """Returns empty string when the shard directory doesn't exist."""
        assert find_file_on_disk(tmp_path, "DOC1", "File") == ""
