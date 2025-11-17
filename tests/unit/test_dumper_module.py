from __future__ import annotations

from typing import Any, Dict, List


class DummyAPI:
    """Minimal stand-in for SalesforceAPI used by dumper tests.

    We implement only the methods that dumper.py needs:

      - describe_object(name)
      - query_all_iter(soql)

    This keeps the test fast and deterministic (no real HTTP).
    """

    def __init__(self) -> None:
        self.describe_calls: List[str] = []
        self.query_calls: List[str] = []
        self._records: List[Dict[str, Any]] = []

    # --- API surface used by fieldnames_for_o
