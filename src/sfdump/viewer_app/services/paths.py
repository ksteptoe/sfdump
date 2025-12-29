from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Infer EXPORT_ROOT from a DB path that looks like:
      EXPORT_ROOT/meta/sfdata.db

    Returns EXPORT_ROOT or None if it can't infer safely.
    """
    p = Path(db_path).expanduser().resolve()
    # Expect .../<export_root>/meta/sfdata.db
    if p.name.lower() != "sfdata.db":
        return None
    if p.parent.name.lower() != "meta":
        return None
    export_root = p.parent.parent
    return export_root if export_root.exists() else None


def safe_relpath(path: Path, start: Path) -> str:
    """
    Return a POSIX-ish relative path if possible, else absolute POSIX path.
    """
    try:
        rel = path.resolve().relative_to(start.resolve())
        return rel.as_posix()
    except Exception:
        return path.resolve().as_posix()


def to_posix_relpath(p: str) -> str:
    """
    Normalize a relative path string to POSIX style for consistent display.
    """
    return p.replace("\\", "/")
