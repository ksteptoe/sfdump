#!/usr/bin/env python
from __future__ import annotations

import sys

from sfdump.api import SalesforceAPI, SFConfig  # adjust import if your package name differs


def main(doc_id: str) -> None:
    cfg = SFConfig.from_env()
    api = SalesforceAPI.from_config(cfg)

    print(f"Connected to instance={api.instance_url} api=v{api.api_version}")
    print(f"Querying ContentVersion for ContentDocumentId={doc_id!r}")

    soql = (
        "SELECT Id, ContentDocumentId, Title, FileType, "
        "ContentSize, VersionNumber, IsLatest, IsDeleted "
        f"FROM ContentVersion WHERE ContentDocumentId = '{doc_id}'"
    )

    rows = list(api.query_all_iter(soql))
    print(f"Rows returned: {len(rows)}")
    for r in rows:
        r.pop("attributes", None)
        print(r)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: debug_content_version.py <ContentDocumentId>")
        sys.exit(1)
    main(sys.argv[1])
