import csv
from pathlib import Path

from sfdump import dumper


class APIExplicit:
    def query_all_iter(self, soql: str):
        # emit two rows, ensure attributes key pops safely
        yield {"attributes": {}, "Id": "ID1", "X": "x1"}
        yield {"attributes": {"type": "X"}, "Id": "ID2", "X": "x2"}


def test_dump_with_explicit_fields_no_where_no_limit(tmp_path):
    api = APIExplicit()
    out_dir = tmp_path / "csv_explicit"
    csv_path, count = dumper.dump_object_to_csv(
        api,
        object_name="X__c",
        out_dir=str(out_dir),
        fields=["Id", "X"],
        where=None,
        limit=None,
    )
    assert count == 2 and Path(csv_path).exists()
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == [{"Id": "ID1", "X": "x1"}, {"Id": "ID2", "X": "x2"}]
