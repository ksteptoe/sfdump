from __future__ import annotations

import sqlite3
from pathlib import Path

from sfdump.viewer import build_sqlite_from_export


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.write_text(
        "\n".join(
            [
                ",".join(header),
                *[",".join(row) for row in rows],
            ]
        ),
        encoding="utf-8",
    )


def test_build_sqlite_from_export_creates_tables_and_rows(tmp_path: Path) -> None:
    # Arrange: create a tiny fake export directory with a couple of objects.
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Account.csv
    _write_csv(
        export_dir / "Account.csv",
        header=["Id", "Name"],
        rows=[
            ["001A", "Acme Corp"],
            ["001B", "Beta Ltd"],
        ],
    )

    # ContentDocument.csv (to exercise file-related objects)
    _write_csv(
        export_dir / "ContentDocument.csv",
        header=["Id", "Title"],
        rows=[
            ["069X", "Spec.pdf"],
        ],
    )

    # Act: build the SQLite database
    db_path = tmp_path / "sfdata.db"
    result = build_sqlite_from_export(export_dir, db_path)

    assert result == db_path
    assert db_path.is_file()

    # Assert: open the DB and check tables and row counts
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        # Check that the expected tables exist
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('account', 'content_document')"
        )
        tables = {name for (name,) in cur.fetchall()}
        assert "account" in tables
        assert "content_document" in tables

        # Check row counts
        cur.execute("SELECT COUNT(*) FROM account")
        (account_count,) = cur.fetchone()
        assert account_count == 2

        cur.execute("SELECT COUNT(*) FROM content_document")
        (doc_count,) = cur.fetchone()
        assert doc_count == 1

        # Check that at least one index exists (we don't depend on exact names)
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        index_names = [name for (name,) in cur.fetchall()]
        assert index_names, "Expected at least one index to be created"
    finally:
        conn.close()
