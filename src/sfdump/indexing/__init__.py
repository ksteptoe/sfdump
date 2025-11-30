"""Index-building and schema metadata for linking objects, files, and relationships."""

from .schema import (
    OBJECTS,
    RELATIONSHIPS,
    SFObject,
    SFRelationship,
    children_of,
    get_object,
    iter_objects,
    parents_of,
)

__all__ = [
    "SFObject",
    "SFRelationship",
    "OBJECTS",
    "RELATIONSHIPS",
    "get_object",
    "iter_objects",
    "children_of",
    "parents_of",
]
