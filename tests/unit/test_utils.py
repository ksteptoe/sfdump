# tests/unit/test_utils.py
import csv

from sfdump.utils import ensure_dir, sanitize_filename, sha256_of_file, write_csv


def test_ensure_dir_idempotent(tmp_path):
    d = tmp_path / "a" / "b"
    ensure_dir(str(d))
    assert d.exists() and d.is_dir()
    # second call should be a no-op
    ensure_dir(str(d))
    assert d.exists() and d.is_dir()


def test_sanitize_filename_various():
    forbidden = r'\\/:*?"<>|'

    # Normalizes whitespace and forbidden chars (typically to underscores)
    s1 = sanitize_filename("  Project Plan / v1  ")
    assert s1.strip() == s1
    assert not any(c in s1 for c in forbidden)
    assert "Project" in s1 and "Plan" in s1 and "v1" in s1
    assert " " not in s1  # spaces normalized to underscores or removed

    # Keeps extension; removes/normalizes unsafe chars
    s2 = sanitize_filename("Budget&Forecast*?.xlsx")
    assert s2.endswith(".xlsx")
    assert not any(c in s2 for c in forbidden + "&*?")
    assert " " not in s2

    # Empty/whitespace-only → empty result (caller supplies fallback)
    assert sanitize_filename("   ") == ""


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
