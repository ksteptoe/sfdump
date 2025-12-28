from __future__ import annotations

from pathlib import Path
from typing import Optional


def infer_export_root(db_path: Path) -> Optional[Path]:
    """
    Best-effort: infer EXPORT_ROOT from db_path.
    Typical layout: EXPORT_ROOT/meta/sfdata.db
    """
    try:
        if db_path.name.lower() == "sfdata.db" and db_path.parent.name.lower() == "meta":
            return db_path.parent.parent
    except Exception:
        pass

    # fallback: walk up a few levels looking for a folder that contains csv/ and meta/
    p = db_path.resolve()
    for _ in range(6):
        if (p / "csv").exists() and (p / "meta").exists():
            return p
        p = p.parent
    return None


def export_root_for_db(db_path: Path) -> Path:
    """
    Return an export root for this db_path.

    Keeps legacy behavior (db_path.parent.parent) if inference fails,
    but prefers the more robust infer_export_root().
    """
    root = infer_export_root(db_path)
    if root is not None:
        return root
    return db_path.parent.parent


def resolve_export_path(export_root: Path, rel_path: str) -> Path:
    """
    Resolve a path from the export root.

    Paths in your CSV/DB may use Windows backslashes like files_legacy\\00\\...
    """
    rel_path = (rel_path or "").replace("\\", "/")
    return export_root / rel_path
