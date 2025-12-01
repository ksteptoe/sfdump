"""SQLite-oriented schema helpers for an offline Salesforce viewer.

This module does *not* talk to a database directly. Instead, it describes
how we want to map Salesforce objects and relationships (from
``sfdump.indexing``) into SQLite tables and indexes.

A future db-builder can use these definitions to:
- CREATE TABLE ... statements (per exported object)
- CREATE INDEX ... statements (based on relationships)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from sfdump.indexing import OBJECTS, RELATIONSHIPS, SFObject, SFRelationship


@dataclass(frozen=True)
class SqliteTableConfig:
    """Minimal description of a SQLite table for an exported SF object.

    We deliberately only model what we need up front: table name and primary
    key column. Actual columns will be inferred from CSV headers by the
    loader at runtime.
    """

    table_name: str
    pk_column: str = "Id"


@dataclass(frozen=True)
class SqliteIndexConfig:
    """Description of an index we want to create in SQLite."""

    name: str
    table: str
    columns: tuple[str, ...]
    unique: bool = False


def default_table_configs(
    objects: Iterable[SFObject] | None = None,
) -> Dict[str, SqliteTableConfig]:
    """Return a mapping of API name -> table configuration.

    By default this uses all objects registered in ``sfdump.indexing.OBJECTS``.
    """
    if objects is None:
        objects = OBJECTS.values()

    configs: Dict[str, SqliteTableConfig] = {}
    for obj in objects:
        configs[obj.api_name] = SqliteTableConfig(
            table_name=obj.table_name,
            pk_column=obj.id_field,
        )
    return configs


def default_index_configs(
    relationships: Iterable[SFRelationship] | None = None,
) -> List[SqliteIndexConfig]:
    """Return a list of index configurations based on known relationships.

    Strategy:
    - For every relationship, create a non-unique index on the child table's
      foreign key column (e.g. Opportunity.AccountId, ContentVersion.ContentDocumentId).
    - We also include polymorphic relationships (parent="*"), since they still
      benefit from an index on the child_field.
    """
    if relationships is None:
        relationships = RELATIONSHIPS

    table_configs = default_table_configs()
    index_configs: List[SqliteIndexConfig] = []

    for rel in relationships:
        child_obj = table_configs.get(rel.child)
        if child_obj is None:
            # Relationship references an object we don't have a table for (yet)
            continue

        index_name = f"idx_{child_obj.table_name}_{rel.child_field.lower()}"
        index_configs.append(
            SqliteIndexConfig(
                name=index_name,
                table=child_obj.table_name,
                columns=(rel.child_field,),
                unique=False,
            )
        )

    return index_configs
