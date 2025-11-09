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
    # strips forbidden characters and trims
    assert sanitize_filename("  Project Plan / v1  ") == "Project Plan  v1"
    assert sanitize_filename("Budget&Forecast*?.xlsx") == "BudgetForecast.xlsx"
    # empty/whitespace string → empty result (caller provides fallback)
    assert sanitize_filename("   ") == ""


def test_sha256_of_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    # known sha256('abc')
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
