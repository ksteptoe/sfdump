from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Best-effort: infer EXPORT_ROOT from a db path.
    Common layout: EXPORT_ROOT/meta/sfdata.db
    """
    p = Path(db_path)

    # If user passed EXPORT_ROOT instead of the DB file
    if p.is_dir():
        candidate = p / "meta" / "sfdata.db"
        if candidate.exists():
            return p
        return None

    if p.name.lower() != "sfdata.db":
        # still try: if a file under meta/
        for parent in p.parents:
            if parent.name.lower() == "meta":
                return parent.parent
        return None

    # p is sfdata.db
    if p.parent.name.lower() == "meta":
        return p.parent.parent

    # search upwards for /meta/
    for parent in p.parents:
        if parent.name.lower() == "meta":
            return parent.parent

    return None


def resolve_export_path(export_root: Path, rel_or_abs_path: str) -> Path:
    """
    Resolve a document path which might be:
      - absolute, or
      - relative to export_root, possibly with backslashes
    """
    s = (rel_or_abs_path or "").strip().strip('"').strip("'")
    p = Path(s)

    if p.is_absolute():
        return p

    # normalize windows-y separators
    s = s.replace("\\", "/").lstrip("/")
    return Path(export_root) / s
