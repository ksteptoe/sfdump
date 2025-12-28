from __future__ import annotations

from typing import Any

from sfdump.indexing import OBJECTS


def get_object_choices(tables: list[Any]) -> list[tuple[str, str]]:
    """
    Return sorted (label, api_name) for objects that actually exist in the DB.

    Uses SFObject.label for friendliness, but keeps the API name visible.
    """
    table_names = {t.name for t in tables}
    choices: list[tuple[str, str]] = []

    for obj in OBJECTS.values():
        if obj.table_name in table_names:
            label = getattr(obj, "label", None) or obj.api_name
            ui_label = f"{label} ({obj.api_name})" if label != obj.api_name else label
            choices.append((ui_label, obj.api_name))

    return sorted(choices, key=lambda x: x[0])
