from __future__ import annotations

import csv
import json
import os
from typing import Dict, Iterable, List, Optional, Tuple

from .utils import ensure_dir


def _move_id_first(fields: List[str]) -> List[str]:
    if "Id" in fields:
        fields = [f for f in fields if f != "Id"]
        return ["Id"] + fields
    return fields


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _is_polymorphic_reference(fdesc: dict) -> bool:
    # Polymorphic references have multiple possible targets (e.g. WhoId/WhatId).
    refs = fdesc.get("referenceTo") or []
    return (
        bool(fdesc.get("relationshipName")) and fdesc.get("type") == "reference" and len(refs) != 1
    )


def _get_queryable_fieldnames(desc: dict) -> List[str]:
    return [f["name"] for f in desc.get("fields", []) if f.get("queryable", True)]


def fieldnames_for_object(
    api,
    object_name: str,
    *,
    include_relationship_fields: bool = False,
    relationship_subfields: Optional[List[str]] = None,
) -> List[str]:
    """
    Return queryable fieldnames for object (Id first).

    - Always includes reference Id fields (e.g. OwnerId, AccountId) so relationships can be reconstructed.
    - If include_relationship_fields=True, also adds dot-path parent fields for non-polymorphic references,
      e.g. Owner.Name, Account.Name (only if the target has those fields and they are queryable).
    """
    relationship_subfields = relationship_subfields or ["Name"]

    d = api.describe_object(object_name)

    # 1) Base fields: ALL queryable fields (including lookup/master-detail Ids)
    base_fields = _move_id_first(_get_queryable_fieldnames(d))

    if not include_relationship_fields:
        return _dedupe_preserve_order(base_fields)

    # 2) Optional relationship display fields (e.g. Owner.Name)
    describe_cache: Dict[str, dict] = {}
    rel_fields: List[str] = []

    for f in d.get("fields", []):
        if not f.get("queryable", True):
            continue
        if f.get("type") != "reference":
            continue

        rel_name = f.get("relationshipName")
        if not rel_name:
            continue

        if _is_polymorphic_reference(f):
            # Can't safely pick a single target type to describe.
            continue

        target = (f.get("referenceTo") or [None])[0]
        if not target:
            continue

        if target not in describe_cache:
            describe_cache[target] = api.describe_object(target)

        target_desc = describe_cache[target]
        target_queryable = set(_get_queryable_fieldnames(target_desc))

        for sub in relationship_subfields:
            if sub in target_queryable:
                rel_fields.append(f"{rel_name}.{sub}")

    return _dedupe_preserve_order(_move_id_first(base_fields + rel_fields))


def _get_by_path(obj: object, path: str) -> object:
    """Traverse dicts using dot paths like 'Owner.Name'. Returns None if missing."""
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _scalarize(v: object) -> object:
    # Some Salesforce fields may return dict/list structures; keep CSV stable.
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return v


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

    soql = f"SELECT {', '.join(fields)} FROM {object_name}"
    if where:
        soql += f" WHERE {where}"

    has_paths = any("." in f for f in fields)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        count = 0
        for rec in _record_iter(api, soql, limit):
            if has_paths:
                row = {fn: _scalarize(_get_by_path(rec, fn)) for fn in fields}
            else:
                row = {fn: _scalarize(rec.get(fn)) for fn in fields}
            w.writerow(row)
            count += 1

    return csv_path, count
