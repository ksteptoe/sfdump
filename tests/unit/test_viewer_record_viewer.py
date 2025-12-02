from __future__ import annotations

from pathlib import Path

from sfdump.viewer import build_sqlite_from_export, get_record_with_children


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


def test_get_record_with_children_loads_account_and_opportunities(tmp_path: Path) -> None:
    # Arrange: create a small export with Account and Opportunity in csv/
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    csv_dir = export_dir / "csv"
    csv_dir.mkdir()

    _write_csv(
        csv_dir / "Account.csv",
        header=["Id", "Name"],
        rows=[
            ["001A", "Acme Corp"],
        ],
    )

    _write_csv(
        csv_dir / "Opportunity.csv",
        header=["Id", "Name", "AccountId"],
        rows=[
            ["006X", "Big Deal", "001A"],
            ["006Y", "Smaller Deal", "001A"],
        ],
    )

    db_path = tmp_path / "sfdata.db"
    build_sqlite_from_export(export_dir, db_path)

    # Act
    result = get_record_with_children(db_path, "Account", "001A", max_children_per_rel=10)

    # Assert: parent is Account 001A
    assert result.parent.sf_object.api_name == "Account"
    assert result.parent.data["Id"] == "001A"
    assert result.parent.data["Name"] == "Acme Corp"

    # Assert: we have at least one child collection for Opportunities
    child_objs = {c.sf_object.api_name for c in result.children}
    assert "Opportunity" in child_objs

    opp_collection = next(c for c in result.children if c.sf_object.api_name == "Opportunity")
    opp_ids = {r["Id"] for r in opp_collection.records}
    assert opp_ids == {"006X", "006Y"}
