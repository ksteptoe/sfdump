from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Best-effort inference of export root from a DB path.

    Typical layout:
        EXPORT_ROOT/meta/sfdata.db
    """
    p = Path(db_path)

    # Common case: .../meta/sfdata.db
    if p.name.lower() == "sfdata.db" and p.parent.name.lower() == "meta":
        return p.parent.parent

    # Another common case: someone passes .../sfdata.db directly
    if p.name.lower() == "sfdata.db":
        # If there's a sibling "meta", assume parent is export root
        # (EXPORT_ROOT/meta/sfdata.db)
        if (p.parent / "meta").exists():
            return p.parent
        # else unknown
        return None

    return None


def resolve_export_path(export_root: Path, rel_or_abs_path: str) -> Path:
    """
    Resolve a relative path inside EXPORT_ROOT to an absolute Path.

    - If rel_or_abs_path is already absolute, return it.
    - Accept Windows backslashes in rel paths even when running elsewhere.
    """
    raw = (rel_or_abs_path or "").strip()
    if not raw:
        return Path(export_root)

    p = Path(raw)
    if p.is_absolute():
        return p

    # Normalize separators (the export indices may contain backslashes)
    norm = raw.replace("\\", "/").lstrip("/")

    return Path(export_root) / norm
