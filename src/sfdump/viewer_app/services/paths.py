from __future__ import annotations

from pathlib import Path


def infer_export_root(db_path: Path) -> Path:
    """
    Given <export_root>/meta/sfdata.db, return <export_root>.
    Fallback to parent if the structure is unexpected.
    """
    p = Path(db_path)
    if p.name.lower().endswith(".db") and p.parent.name.lower() == "meta":
        return p.parent.parent
    return p.parent


def resolve_export_path(export_root: Path, local_path: str) -> Path:
    """
    Resolve a relative path from the export root.

    Handles both Windows-style backslashes and forward slashes.
    """
    lp = (local_path or "").replace("\\", "/").lstrip("/")
    return (Path(export_root) / lp).resolve()
