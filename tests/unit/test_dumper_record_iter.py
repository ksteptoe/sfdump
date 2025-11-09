from sfdump.dumper import _record_iter


class APIMany:
    def query_all_iter(self, soql: str):
        for i in range(10):
            yield {"attributes": {}, "Id": f"00{i}", "Name": f"N{i}"}


def test_record_iter_respects_limit():
    api = APIMany()
    recs = list(_record_iter(api, "SELECT Id FROM X", limit=3))
    assert len(recs) == 3
    # attributes key should be popped
    assert all("attributes" not in r for r in recs)
