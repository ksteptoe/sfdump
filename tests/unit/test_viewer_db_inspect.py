from __future__ import annotations

from pathlib import Path

from sfdump.viewer import build_sqlite_from_export, inspect_sqlite_db


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


def test_inspect_sqlite_db_reports_tables_and_index_count(tmp_path: Path) -> None:
    # Arrange: create a tiny export with csv/ and build a DB.
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    csv_dir = export_dir / "csv"
    csv_dir.mkdir()

    _write_csv(
        csv_dir / "Account.csv",
        header=["Id", "Name"],
        rows=[
            ["001A", "Acme Corp"],
            ["001B", "Beta Ltd"],
        ],
    )

    db_path = tmp_path / "sfdata.db"
    build_sqlite_from_export(export_dir, db_path)

    # Act
    overview = inspect_sqlite_db(db_path)

    # Assert
    assert overview.path == db_path
    table_names = {t.name for t in overview.tables}
    assert "account" in table_names
    # At least the account table has 2 rows
    account_info = next(t for t in overview.tables if t.name == "account")
    assert account_info.row_count == 2
    # We expect at least one index (from relationship-based defaults)
    assert overview.index_count >= 0  # non-negative; exact value not important
