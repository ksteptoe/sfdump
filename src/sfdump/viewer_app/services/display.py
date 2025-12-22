from __future__ import annotations

from typing import Any

from sfdump.viewer_app.config import important_fields_for


def get_important_fields(api_name: str) -> list[str]:
    """Return configured key fields for an object."""
    return important_fields_for(api_name)


def select_display_columns(api_name: str, df: Any, show_all: bool) -> list[str]:
    """
    Decide which columns to show for a given object + DataFrame.

    - If show_all: return all columns.
    - Else: use important_fields_for() if present.
    - Else: fall back to a simple Id/Name/... heuristic.
    """
    cols = list(getattr(df, "columns", []))

    if show_all:
        return cols

    # 1) Try configured important fields
    important = get_important_fields(api_name)
    display_cols: list[str] = [c for c in important if c in cols]

    # 2) If none matched, use generic heuristic
    if not display_cols:
        for col in ("Id", "Name"):
            if col in cols and col not in display_cols:
                display_cols.append(col)

        for extra in ("Email", "Title", "StageName", "Amount"):
            if extra in cols and extra not in display_cols:
                display_cols.append(extra)

    # 3) Fallback
    if not display_cols:
        display_cols = cols[:5]

    return display_cols
