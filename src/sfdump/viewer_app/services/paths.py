from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Given .../exports/export-YYYY-MM-DD/meta/sfdata.db, return .../exports/export-YYYY-MM-DD
    """
    p = Path(db_path)
    if not p.exists():
        # still try to infer by shape
        pass

    # Most common: export_root/meta/sfdata.db
    if p.name.lower() == "sfdata.db" and p.parent.name.lower() == "meta":
        return p.parent.parent

    # Fallback: if someone passed the meta dir, etc.
    if p.is_dir() and p.name.lower() == "meta":
        return p.parent

    return None


def resolve_export_path(export_root: Path, rel_path: str | Path) -> Path:
    """
    Resolve a (possibly Windows-backslash) relative path against export_root.
    If rel_path is already absolute, return it as a Path.
    """
    if isinstance(rel_path, Path):
        rp = rel_path
    else:
        rp = Path(str(rel_path).strip().replace("\\", "/"))

    if not str(rp):
        return Path("")

    if rp.is_absolute():
        return rp

    return Path(export_root) / rp
