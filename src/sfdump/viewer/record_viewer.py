"""Helpers for viewing a record and its related children from the viewer DB."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sfdump.indexing import OBJECTS, SFObject, SFRelationship, children_of


@dataclass(frozen=True)
class ParentRecord:
    """Represents a single parent record loaded from the DB."""

    sf_object: SFObject
    data: Dict[str, Any]


@dataclass(frozen=True)
class ChildCollection:
    """Represents a collection of child records for a given relationship."""

    relationship: SFRelationship
    sf_object: SFObject
    records: List[Dict[str, Any]]


@dataclass(frozen=True)
class RecordWithChildren:
    """Parent record plus all its child collections."""

    parent: ParentRecord
    children: List[ChildCollection]


def _resolve_object(api_name: str) -> SFObject:
    """Return SFObject for a given API name, case-insensitively."""
    # Try exact match first
    if api_name in OBJECTS:
        return OBJECTS[api_name]

    # Case-insensitive fallback
    lowered = api_name.lower()
    for obj in OBJECTS.values():
        if obj.api_name.lower() == lowered:
            return obj

    raise KeyError(f"Unknown Salesforce object API name: {api_name}")


def get_record_with_children(
    db_path: Path | str,
    api_name: str,
    record_id: str,
    *,
    max_children_per_rel: int = 20,
) -> RecordWithChildren:
    """Load a record and its direct children from the viewer SQLite DB.

    Parameters
    ----------
    db_path:
        Path to the SQLite database built via build_sqlite_from_export.
    api_name:
        Salesforce API name for the parent object (e.g. "Account").
    record_id:
        The Id of the parent record (e.g. "001...").
    max_children_per_rel:
        Maximum number of child records to load for each relationship.

    Returns
    -------
    RecordWithChildren

    Raises
    ------
    FileNotFoundError
        If the DB file does not exist.
    KeyError
        If the object API name is unknown.
    ValueError
        If the parent record does not exist in the DB.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {db_path}")
    if not db_path.is_file():
        raise ValueError(f"SQLite database path {db_path} is not a file")

    sf_obj = _resolve_object(api_name)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # Discover which tables actually exist in this DB so we can gracefully
        # skip relationships whose child tables are not present (partial export).
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {name for (name,) in cur.fetchall()}

        # Load the parent record
        cur.execute(
            f'SELECT * FROM "{sf_obj.table_name}" WHERE "{sf_obj.id_field}" = ?',
            (record_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(
                f"No {sf_obj.api_name} record with {sf_obj.id_field}={record_id} found in {db_path}"
            )

        parent = ParentRecord(sf_object=sf_obj, data=dict(row))

        # Load children for each relationship where this object is the parent
        child_collections: List[ChildCollection] = []
        for rel in children_of(sf_obj.api_name):
            child_obj: Optional[SFObject] = OBJECTS.get(rel.child)
            if child_obj is None:
                # Relationship references an object we don't have in the DB schema
                continue

            if child_obj.table_name not in existing_tables:
                # This export/DB simply doesn't contain this child object
                continue

            cur.execute(
                f'SELECT * FROM "{child_obj.table_name}" '
                f'WHERE "{rel.child_field}" = ? '
                f"LIMIT {max_children_per_rel}",
                (record_id,),
            )
            child_rows = [dict(r) for r in cur.fetchall()]
            if not child_rows:
                continue

            child_collections.append(
                ChildCollection(
                    relationship=rel,
                    sf_object=child_obj,
                    records=child_rows,
                )
            )

    finally:
        conn.close()

    return RecordWithChildren(parent=parent, children=child_collections)
