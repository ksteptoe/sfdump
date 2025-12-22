from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

from sfdump.viewer_app.services.paths import (
    infer_export_root,
)
from sfdump.viewer_app.ui.main_parts import render_record_list, render_sidebar_controls
from sfdump.viewer_app.ui.record_tabs import render_record_tabs


def _export_root_from_db_path(db_path: Path) -> Optional[Path]:
    """
    Best-effort: infer EXPORT_ROOT from db_path.
    Typical layout: EXPORT_ROOT/meta/sfdata.db
    """
    return infer_export_root(db_path)


def _initial_db_path_from_argv() -> Optional[Path]:
    # When launched via: streamlit run db_app.py -- <db-path>
    # sys.argv for this script will look like: ['db_app.py', '<db-path>']
    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)
    return None


def main() -> None:
    st.set_page_config(page_title="SF Dump DB Viewer", layout="wide")
    st.markdown(
        """
        <style>
          /* overall app font */
          html, body, [class*="css"]  { font-size: 13px; }

          /* tighten padding */
          .block-container { padding-top: 1rem; padding-bottom: 1rem; }
          section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

          /* dataframes: smaller text */
          div[data-testid="stDataFrame"] { font-size: 12px; }

          /* expander headers a bit smaller */
          details summary { font-size: 13px; }

          /* shrink selectbox / inputs slightly */
          .stSelectbox, .stTextInput, .stNumberInput, .stCheckbox { font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("SF Dump DB Viewer")
    # Sidebar: DB selection (delegated)
    initial_db = _initial_db_path_from_argv()
    state = render_sidebar_controls(initial_db=initial_db)
    if state is None:
        return

    db_path = state.db_path
    api_name = state.api_name
    selected_label = state.selected_label
    search_term = state.search_term
    limit = state.limit
    regex_search = state.regex_search
    show_all_fields = state.show_all_fields

    col_left, col_right = st.columns([2, 3])
    with col_left:
        rows, selected_id = render_record_list(
            db_path=db_path,
            api_name=api_name,
            selected_label=selected_label,
            search_term=search_term,
            regex_search=regex_search,
            limit=int(limit),
            show_all_fields=show_all_fields,
        )
    with col_right:
        if not rows or not selected_id:
            st.info("Select a record on the left to see details and related records.")
            return

        render_record_tabs(
            db_path=db_path,
            api_name=api_name,
            selected_id=str(selected_id),
            show_all_fields=show_all_fields,
        )


if __name__ == "__main__":
    main()
