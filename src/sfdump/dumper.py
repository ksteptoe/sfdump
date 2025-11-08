from __future__ import annotations

import os
from typing import Iterable, List, Optional, Tuple

from .utils import ensure_dir


def fieldnames_for_object(api, object_name: str) -> List[str]:
    """All queryable, non-relationship fields for the object (Id first)."""
    d = api.describe_object(object_name)
    fields = [
        f["name"]
        for f in d.get("fields", [])
        if f.get("queryable", True) and not f.get("relationshipName")
    ]
    if "Id" in fields:
        fields.remove("Id")
        fields = ["Id"] + fields
    return fields


def _record_iter(api, soql: str, limit: Optional[int]) -> Iterable[dict]:
    """Iterate records, honoring optional LIMIT on client side (simple & safe)."""
    n = 0
    for rec in api.query_all_iter(soql):
        rec.pop("attributes", None)
        yield rec
        n += 1
        if limit is not None and n >= limit:
            break


def dump_object_to_csv(
    api,
    object_name: str,
    out_dir: str,
    fields: Optional[List[str]] = None,
    where: Optional[str] = None,
    limit: Optional[int] = None,
) -> Tuple[str, int]:
    """Dump a single sObject to CSV. Returns (csv_path, row_count)."""
    ensure_dir(out_dir)
    fields = fields or fieldnames_for_object(api, object_name)
    csv_path = os.path.join(out_dir, f"{object_name}.csv")

    # Build SOQL
    soql = f"SELECT {', '.join(fields)} FROM {object_name}"
    if where:
        soql += f" WHERE {where}"

    # Stream write (avoid loading whole result into memory)
    import csv

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        count = 0
        for rec in _record_iter(api, soql, limit):
            w.writerow(rec)
            count += 1
    return csv_path, count
