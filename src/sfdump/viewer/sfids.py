from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd


def _sf_prefix(sf_id: str) -> str:
    return (sf_id or "")[:3]


@lru_cache(maxsize=1)
def prefix_to_object(export_root: str) -> dict[str, str]:
    meta = Path(export_root) / "meta"
    for name in ("objects.csv", "sobjects.csv", "sobject_index.csv"):
        p = meta / name
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str).fillna("")
        name_col = next((c for c in df.columns if c.lower() in {"name", "object", "sobject"}), None)
        px_col = next(
            (c for c in df.columns if c.lower() in {"keyprefix", "key_prefix", "prefix"}), None
        )
        if not name_col or not px_col:
            continue
        m = {}
        for _, r in df.iterrows():
            px = r[px_col]
            nm = r[name_col]
            if px and len(px) == 3:
                m[px] = nm
        if m:
            return m
    return {}


def resolve_object(export_root: str, sf_id: str) -> str | None:
    px = _sf_prefix(sf_id)
    return prefix_to_object(export_root).get(px)
