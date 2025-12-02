from __future__ import annotations

from pathlib import Path

from sfdump.viewer import build_sqlite_from_export, list_records


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


def test_list_records_can_filter_and_limit(tmp_path: Path) -> None:
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
            ["001C", "Another Acme"],
        ],
    )

    db_path = tmp_path / "sfdata.db"
    build_sqlite_from_export(export_dir, db_path)

    # Filter by Name containing 'Acme'
    result = list_records(
        db_path,
        "Account",
        where="Name LIKE '%Acme%'",
        limit=10,
    )

    names = {row["Name"] for row in result.rows}
    assert names == {"Acme Corp", "Another Acme"}
