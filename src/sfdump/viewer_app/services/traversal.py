from __future__ import annotations

from pathlib import Path
from typing import Optional

from sfdump.viewer import get_record_with_children


def collect_subtree_ids(
    db_path: Path,
    root_api: str,
    root_id: str,
    *,
    max_depth: int = 3,
    max_children_per_rel: int = 50,
    allow_objects: Optional[set[str]] = None,
) -> dict[str, set[str]]:
    """
    BFS traverse using existing get_record_with_children().

    Returns {api_name -> set(ids)} including the root.
    """
    out: dict[str, set[str]] = {root_api: {root_id}}
    seen: set[tuple[str, str]] = {(root_api, root_id)}
    q: list[tuple[str, str, int]] = [(root_api, root_id, 0)]

    while q:
        api, rid, depth = q.pop(0)
        if depth >= max_depth:
            continue

        try:
            rec = get_record_with_children(
                db_path=db_path,
                api_name=api,
                record_id=rid,
                max_children_per_rel=max_children_per_rel,
            )
        except Exception:
            # Some objects may not be loadable; skip silently
            continue

        for coll in rec.children or []:
            child_api = coll.sf_object.api_name
            if allow_objects is not None and child_api not in allow_objects:
                continue

            for row in coll.records or []:
                child_id = row.get("Id") or row.get(coll.sf_object.id_field)
                if not child_id:
                    continue
                key = (child_api, str(child_id))
                if key in seen:
                    continue
                seen.add(key)
                out.setdefault(child_api, set()).add(str(child_id))
                q.append((child_api, str(child_id), depth + 1))

    return out
