from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from sfdump.core import SalesforceAPI


def test_query_all_iter_handles_paging(monkeypatch) -> None:
    """SalesforceAPI.query_all_iter should follow nextRecordsUrl until exhausted."""

    api = SalesforceAPI()
    api.instance_url = "https://example.my.salesforce.com"
    api.api_version = "v60.0"

    # Simulate two pages of results
    responses = [
        {
            "records": [{"Id": "1"}, {"Id": "2"}],
            "nextRecordsUrl": "/services/data/v60.0/query/01gNEXT",
        },
        {
            "records": [{"Id": "3"}],
            "nextRecordsUrl": None,
        },
    ]
    call_index = {"i": 0}
    urls_seen: list[str] = []

    def fake_get(
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ):
        # First call should be the base /query endpoint with params,
        # second call should use the nextRecordsUrl directly.
        urls_seen.append(url)
        payload = responses[call_index["i"]]
        call_index["i"] += 1

        class DummyResp:
            def json(self_inner) -> Dict[str, Any]:
                return payload

        return DummyResp()

    monkeypatch.setattr(api, "_get", fake_get)

    records = list(api.query_all_iter("SELECT Id FROM Account"))

    # We should see all 3 records from both pages
    assert records == [{"Id": "1"}, {"Id": "2"}, {"Id": "3"}]

    # We should have called _get twice: first the query endpoint,
    # then the nextRecordsUrl.
    assert len(urls_seen) == 2
    assert urls_seen[0].endswith("/services/data/v60.0/query")
    assert urls_seen[1] == "https://example.my.salesforce.com/services/data/v60.0/query/01gNEXT"


def test_download_path_to_file_streams_to_disk(tmp_path: Path, monkeypatch) -> None:
    """download_path_to_file should stream response bytes to the target file."""
    api = SalesforceAPI()
    api.instance_url = "https://example.my.salesforce.com"

    # We'll monkeypatch the session.get method
    chunks = [b"abc", b"def"]
    urls_seen: list[str] = []

    class DummyResponse:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, exc_type, exc, tb):
            return False

        def raise_for_status(self_inner) -> None:
            # Simulate a 200 OK
            return None

        def iter_content(self_inner, chunk_size: int = 8192):
            # Ignore chunk_size; just yield our predefined chunks
            for c in chunks:
                yield c

    class DummySession:
        def get(self_inner, url: str, stream: bool = False):
            urls_seen.append(url)
            assert stream is True
            return DummyResponse()

    api.session = DummySession()  # type: ignore[assignment]

    target = tmp_path / "out.bin"
    written = api.download_path_to_file(
        "/services/data/v60.0/sobjects/ContentVersion/123/VersionData", str(target)
    )

    # Confirm the URL was built correctly and data written
    assert urls_seen == [
        "https://example.my.salesforce.com/services/data/v60.0/sobjects/ContentVersion/123/VersionData"
    ]
    assert written == len(b"abcdef")
    assert target.read_bytes() == b"abcdef"
