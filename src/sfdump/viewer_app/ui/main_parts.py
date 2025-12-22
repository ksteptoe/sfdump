from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from sfdump.viewer import inspect_sqlite_db, list_records
from sfdump.viewer_app.services.display import select_display_columns
from sfdump.viewer_app.services.objects import get_object_choices


@dataclass(frozen=True)
class SidebarState:
    db_path: Path
    api_name: str
    selected_label: str
    search_term: str
    limit: int
    regex_search: bool
    show_all_fields: bool


def render_sidebar_controls(*, initial_db: Optional[Path]) -> Optional[SidebarState]:
    """Render sidebar inputs and return chosen state, or None if not ready."""
    db_path_str = st.sidebar.text_input(
        "SQLite DB path",
        value=str(initial_db) if initial_db is not None else "",
        help="Path to sfdata.db created by 'sfdump build-db'.",
    )

    if not db_path_str:
        st.info("Enter a path to a sfdata.db file in the sidebar to get started.")
        return None

    db_path = Path(db_path_str)

    try:
        overview = inspect_sqlite_db(db_path)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to open or inspect DB at {db_path}: {exc}")
        return None

    st.sidebar.markdown(f"**DB:** `{overview.path}`")
    st.sidebar.markdown(
        f"**Tables:** {len(overview.tables)}  |  **Indexes:** {overview.index_count}"
    )

    object_choices = get_object_choices(overview.tables)
    if not object_choices:
        st.warning(
            "No known Salesforce objects found in this DB. "
            "Did you build it with 'sfdump build-db' from an export that included object CSVs?"
        )
        return None

    labels = [label for (label, _api) in object_choices]
    label_to_api = {label: api for (label, api) in object_choices}

    selected_label = st.sidebar.selectbox("Object", labels, index=0)
    api_name = label_to_api[selected_label]

    search_term = st.sidebar.text_input(
        "Search (Name contains)",
        value="",
        help="Substring match on the Name field where present.",
    )

    limit = st.sidebar.number_input(
        "Max rows",
        min_value=1,
        max_value=1000,
        value=100,
        step=10,
    )

    regex_search = st.sidebar.checkbox(
        "Use regex (Name REGEXP)",
        value=False,
        help="When enabled, interpret the search string as a regular expression applied to the Name field.",
    )

    show_all_fields = st.sidebar.checkbox(
        "Show all fields",
        value=False,
        help="When checked, show all columns for this object. When unchecked, only show key fields.",
    )

    return SidebarState(
        db_path=db_path,
        api_name=api_name,
        selected_label=selected_label,
        search_term=search_term,
        limit=int(limit),
        regex_search=regex_search,
        show_all_fields=show_all_fields,
    )


def _build_where_clause(search_term: str, regex_search: bool) -> Optional[str]:
    if not search_term:
        return None
    safe_term = search_term.replace("'", "''")
    if regex_search:
        return f"Name REGEXP '{safe_term}'"
    return f"Name LIKE '%{safe_term}%'"


def render_record_list(
    *,
    db_path: Path,
    api_name: str,
    selected_label: str,
    search_term: str,
    regex_search: bool,
    limit: int,
    show_all_fields: bool,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Render the left record list area and return (rows, selected_id)."""
    where_clause = _build_where_clause(search_term, regex_search)

    try:
        listing = list_records(
            db_path=db_path,
            api_name=api_name,
            where=where_clause,
            limit=int(limit),
            order_by="Name",
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error listing records for {api_name}: {exc}")
        return [], None

    rows = listing.rows

    st.subheader(f"{selected_label} records")

    if not rows:
        st.info("No records found. Try adjusting the search or increasing the max rows.")
        return rows, None

    import pandas as pd  # type: ignore[import-not-found]

    df = pd.DataFrame(rows)
    display_cols = select_display_columns(api_name, df, show_all_fields, show_ids=False)
    st.dataframe(df[display_cols], height=260, hide_index=True, width="stretch")

    options = []
    for r in rows:
        rid = r.get("Id")
        label = r.get("Name") or rid or "(no Id)"
        options.append(f"{label} [{rid}]")

    selected_label_value = st.selectbox("Select record", options, index=0)

    if "[" in selected_label_value and selected_label_value.endswith("]"):
        selected_id = selected_label_value.rsplit("[", 1)[-1].rstrip("]")
    else:
        selected_id = rows[0].get("Id")

    return rows, selected_id
