from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Best-effort inference of EXPORT_ROOT from a DB path.

    Expected layout:
        <EXPORT_ROOT>/meta/sfdata.db

    Returns EXPORT_ROOT or None if it can't be inferred.
    """
    p = Path(db_path)
    if p.name.lower() == "sfdata.db" and p.parent.name == "meta":
        return p.parent.parent
    # fallback: if user passed export root accidentally, try to find meta/sfdata.db
    if p.is_dir():
        candidate = p / "meta" / "sfdata.db"
        if candidate.exists():
            return p
    return None


def resolve_export_path(export_root: Path, rel_or_abs_path: str | Path) -> Path:
    """
    Resolve a document path stored in CSV/DB to an absolute on-disk path.

    - If rel_or_abs_path is already absolute, return it as Path.
    - Otherwise join with export_root.
    - Normalizes slashes for cross-platform paths.
    """
    export_root = Path(export_root)

    if isinstance(rel_or_abs_path, Path):
        p = rel_or_abs_path
    else:
        # Normalize both Windows and POSIX separators
        s = (rel_or_abs_path or "").strip().replace("\\", "/")
        p = Path(s)

    if p.is_absolute():
        return p
    return export_root / p
