from __future__ import annotations

from pathlib import Path

import streamlit as st

from sfdump.viewer_app.ui.record_tabs import render_record_tabs


def _default_db_path() -> str:
    # Common local default; user can override in sidebar
    return "exports/export-latest/meta/sfdata.db"


def render_sidebar_controls() -> dict[str, object]:
    """
    Sidebar controls for the viewer.

    Returns a dict containing:
      db_path, api_name, selected_id, show_all_fields, show_ids
    """
    st.sidebar.header("sfdump viewer")

    db_path_str = st.sidebar.text_input("DB path", value=_default_db_path())
    db_path = Path(db_path_str).expanduser()

    api_name = st.sidebar.text_input("Object API name", value="Account").strip()
    selected_id = st.sidebar.text_input("Record Id", value="").strip()

    show_all_fields = st.sidebar.checkbox("Show all fields", value=False)
    show_ids = st.sidebar.checkbox("Show Id columns", value=False)

    return {
        "db_path": db_path,
        "api_name": api_name,
        "selected_id": selected_id,
        "show_all_fields": show_all_fields,
        "show_ids": show_ids,
    }


def render_main_page() -> None:
    st.title("sfdump viewer")

    cfg = render_sidebar_controls()
    db_path: Path = cfg["db_path"]  # type: ignore[assignment]
    api_name: str = cfg["api_name"]  # type: ignore[assignment]
    selected_id: str = cfg["selected_id"]  # type: ignore[assignment]
    show_all_fields: bool = bool(cfg["show_all_fields"])
    show_ids: bool = bool(cfg["show_ids"])

    if not db_path.exists():
        st.warning(f"DB not found: {db_path}")
        st.caption("Tip: set this to something like exports/export-YYYY-MM-DD/meta/sfdata.db")
        return

    if not api_name:
        st.info("Enter an object API name (e.g. Account, Opportunity, c2g__codaInvoice__c).")
        return

    if not selected_id:
        st.info("Enter a record Id to view.")
        return

    render_record_tabs(
        db_path=db_path,
        api_name=api_name,
        selected_id=selected_id,
        show_all_fields=show_all_fields,
        show_ids=show_ids,
    )
