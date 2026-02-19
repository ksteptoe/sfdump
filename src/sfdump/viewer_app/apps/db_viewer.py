from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

from sfdump.indexing import OBJECTS
from sfdump.viewer import get_record_with_children
from sfdump.viewer_app.services.display import get_important_fields
from sfdump.viewer_app.services.documents import load_master_documents_index
from sfdump.viewer_app.services.paths import infer_export_root
from sfdump.viewer_app.services.traversal import collect_subtree_ids
from sfdump.viewer_app.ui.document_explorer import render_document_explorer
from sfdump.viewer_app.ui.documents_panel import render_documents_panel
from sfdump.viewer_app.ui.main_parts import render_record_list, render_sidebar_controls
from sfdump.viewer_app.ui.record_tabs import render_children_with_navigation

_VIEW_KEY = "_sfdump_view"

# ---------------------------------------------------------------------------
# Home landing page — three-way navigation
# ---------------------------------------------------------------------------


def _render_home(*, db_path: Path, export_root: Optional[Path]) -> None:
    """Landing page with three viewer options."""
    # Hide sidebar
    st.markdown(
        """
        <style>
          section[data-testid="stSidebar"] { display: none; }
          button[data-testid="stSidebarCollapsedControl"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("SF Dump Viewer")
    st.markdown("Select a viewer to get started:")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Object Viewer")
        st.markdown(
            "Browse any Salesforce object table. Drill into records, "
            "explore parent/child relationships, and view attached documents."
        )
        if st.button("Open Object Viewer", type="primary", width="stretch"):
            st.session_state[_VIEW_KEY] = "db_viewer"
            st.rerun()

    with col2:
        st.markdown("### HR Viewer")
        st.markdown(
            "View Contact records split by **Employee** and **Contractor**. "
            "Search and filter people with key HR fields at a glance."
        )
        import os

        if os.environ.get("SFDUMP_HR_PASSWORD_HASH", "").strip():
            st.caption("🔒 Protected")
        if st.button("Open HR Viewer", type="primary", width="stretch"):
            st.session_state[_VIEW_KEY] = "hr_viewer"
            st.rerun()

    with col3:
        st.markdown("### Finance Viewer")
        st.markdown(
            "Search and preview all exported documents — invoices, contracts, "
            "attachments, and more — with built-in PDF/file preview."
        )
        if st.button("Open Finance Viewer", type="primary", width="stretch"):
            st.session_state[_VIEW_KEY] = "explorer"
            st.rerun()


def _export_root_from_db_path(db_path: Path) -> Optional[Path]:
    """Best-effort: infer EXPORT_ROOT from db_path (EXPORT_ROOT/meta/sfdata.db)."""
    return infer_export_root(db_path)


def _initial_db_path_from_argv() -> Optional[Path]:
    import os

    env_db = os.environ.get("SFDUMP_DB_PATH")
    if env_db:
        return Path(env_db)

    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)

    exports_dir = Path("./exports")
    if exports_dir.exists():
        exports = sorted(
            [d for d in exports_dir.iterdir() if d.is_dir() and d.name.startswith("export-")],
            key=lambda d: d.name,
            reverse=True,
        )
        for export in exports:
            db_path = export / "meta" / "sfdata.db"
            if db_path.exists():
                return db_path

    return None


@st.cache_data(ttl=3600)
def _check_for_update() -> tuple[bool, str, str]:
    """Cached update check (1-hour TTL). Returns (available, current, latest)."""
    from sfdump.update_check import is_update_available

    return is_update_available()


def main() -> None:
    st.set_page_config(page_title="SF Dump Viewer", layout="wide")

    # Update banner (silent on failure)
    try:
        available, current, latest = _check_for_update()
        if available:
            st.info(
                f"A new version of sfdump is available: **{latest}** (you have {current}).  \n"
                f"Upgrade: `pip install --upgrade sfdump`"
            )
    except Exception:
        pass

    st.markdown(
        """
        <style>
          html, body, [class*="css"]  { font-size: 13px; }
          .block-container { padding-top: 1rem; padding-bottom: 1rem; }
          section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
          div[data-testid="stDataFrame"] { font-size: 12px; }
          details summary { font-size: 13px; }
          .stSelectbox, .stTextInput, .stNumberInput, .stCheckbox { font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    initial_db = _initial_db_path_from_argv()
    if initial_db is None:
        st.error("No database path provided.")
        return

    db_path = initial_db
    export_root = _export_root_from_db_path(db_path)

    view = st.session_state.get(_VIEW_KEY, "home")

    if view == "db_viewer":
        _render_db_viewer(db_path=db_path, export_root=export_root)
    elif view == "hr_viewer":
        _render_hr_viewer(db_path=db_path, export_root=export_root)
    elif view == "explorer":
        _render_explorer(db_path=db_path, export_root=export_root)
    else:
        _render_home(db_path=db_path, export_root=export_root)


# ---------------------------------------------------------------------------
# Explorer view — full-width document search, no sidebar
# ---------------------------------------------------------------------------


def _render_explorer(*, db_path: Path, export_root: Optional[Path]) -> None:
    # Hide sidebar via CSS
    st.markdown(
        """
        <style>
          section[data-testid="stSidebar"] { display: none; }
          button[data-testid="stSidebarCollapsedControl"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header row with title + Home button
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.title("SF Dump Viewer — Finance")
    with col_btn:
        st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Home", type="secondary", key="explorer_home_btn"):
            st.session_state[_VIEW_KEY] = "home"
            st.rerun()

    if export_root is None:
        st.warning(
            "Could not infer export root from DB path (expected EXPORT_ROOT/meta/sfdata.db)."
        )
        return

    render_document_explorer(export_root=export_root, key_prefix="explorer_main")


# ---------------------------------------------------------------------------
# HR Viewer — Contact records split by Employee / Contractor
# ---------------------------------------------------------------------------


def _render_hr_viewer(*, db_path: Path, export_root: Optional[Path]) -> None:
    # Hide sidebar
    st.markdown(
        """
        <style>
          section[data-testid="stSidebar"] { display: none; }
          button[data-testid="stSidebarCollapsedControl"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.title("SF Dump Viewer — HR")
    with col_btn:
        st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Home", type="secondary", key="hr_home_btn"):
            st.session_state[_VIEW_KEY] = "home"
            st.rerun()

    from sfdump.viewer_app.ui.hr_viewer import render_hr_viewer

    render_hr_viewer(db_path=db_path)


# ---------------------------------------------------------------------------
# DB Viewer view — sidebar controls + 2-column record browser
# ---------------------------------------------------------------------------


def _render_db_viewer(*, db_path: Path, export_root: Optional[Path]) -> None:
    st.title("SF Dump Viewer — Objects")

    # Sidebar: "Home" at top, then normal controls
    with st.sidebar:
        if st.button("Home", type="secondary", width="stretch", key="db_home_btn"):
            st.session_state[_VIEW_KEY] = "home"
            st.rerun()
        st.divider()

    state = render_sidebar_controls(db_path=db_path)
    if state is None:
        return

    api_name = state.api_name
    show_all_fields = state.show_all_fields

    # Two-column layout: Left = Record navigator, Right = Subtree documents
    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader("Records")
        rows, selected_id = render_record_list(
            db_path=db_path,
            api_name=api_name,
            selected_label=state.selected_label,
            selected_id=state.selected_id,
            search_term=state.search_term,
            regex_search=state.regex_search,
            limit=int(state.limit),
            show_all_fields=show_all_fields,
            show_ids=state.show_ids,
        )

    with col_right:
        _render_subtree_documents(
            db_path=db_path,
            api_name=api_name,
            selected_id=selected_id,
            rows=rows,
            export_root=export_root,
        )

    # Record detail tabs (below the record list)
    with col_left:
        _render_record_detail_tabs(
            db_path=db_path,
            api_name=api_name,
            selected_id=selected_id,
            rows=rows,
            show_all_fields=show_all_fields,
            show_ids=state.show_ids,
        )


# ---------------------------------------------------------------------------
# Subtree documents panel (right column in DB Viewer)
# ---------------------------------------------------------------------------


def _render_subtree_documents(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    rows: list,
    export_root: Optional[Path],
) -> None:
    if not rows or not selected_id:
        st.info("Select a record on the left to see its documents.")
        return

    if export_root is None:
        st.warning(
            "Could not infer EXPORT_ROOT from DB path. Expected EXPORT_ROOT/meta/sfdata.db layout."
        )
        return

    with st.expander("Recursive docs controls", expanded=False):
        st.caption(f"Export root: {export_root}")

        max_depth = st.slider("Max traversal depth", 1, 6, 3, 1)
        max_children = st.slider("Max children per relationship", 10, 500, 100, 10)

        allow_filter = st.checkbox("Filter to specific object types", value=False)
        allow_objects: Optional[set[str]] = None
        if allow_filter:
            all_api_names = sorted(OBJECTS.keys())
            selected = st.multiselect(
                "Allowed objects",
                options=all_api_names,
                default=[
                    "Opportunity",
                    "c2g__codaInvoice__c",
                    "fferpcore__BillingDocument__c",
                ],
            )
            allow_objects = set(selected)

    subtree = collect_subtree_ids(
        db_path=db_path,
        root_api=api_name,
        root_id=selected_id,
        max_depth=int(max_depth),
        max_children_per_rel=int(max_children),
        allow_objects=allow_objects,
    )

    # Also include parent records from navigation stack
    from sfdump.viewer_app.navigation.record_nav import breadcrumbs

    nav_stack = breadcrumbs()
    for nav_item in nav_stack:
        if nav_item.api_name not in subtree:
            subtree[nav_item.api_name] = set()
        subtree[nav_item.api_name].add(nav_item.record_id)

    total_records = sum(len(v) for v in subtree.values())

    docs_df = load_master_documents_index(export_root)
    if docs_df is None:
        st.error(
            "meta/master_documents_index.csv not found. "
            "Run: `sfdump docs-index --export-root <EXPORT_ROOT>`"
        )
        return

    all_ids: set[str] = set()
    for ids in subtree.values():
        all_ids.update(ids)

    sub_docs = docs_df[docs_df["record_id"].isin(list(all_ids))].copy()

    st.write(
        f"**{total_records}** records across "
        f"**{len(subtree)}** types  "
        f"|  **{len(sub_docs)}** documents"
    )

    if len(sub_docs) == 0:
        st.info("No documents attached to any record in the subtree.")
        return

    show_cols = [
        "file_extension",
        "file_name",
        "object_type",
        "record_name",
        "account_name",
        "opp_name",
    ]
    show_cols = [c for c in show_cols if c in sub_docs.columns]
    st.dataframe(sub_docs[show_cols], height=260, hide_index=True)

    from sfdump.viewer_app.ui.documents_panel import render_documents_panel_from_rows

    render_documents_panel_from_rows(
        export_root=export_root,
        rows=sub_docs.to_dict(orient="records"),
        title="Document Preview",
        key_prefix=f"subtree_docs_{api_name}_{selected_id}",
        pdf_height=800,
    )


# ---------------------------------------------------------------------------
# Record detail tabs (left column in DB Viewer)
# ---------------------------------------------------------------------------


def _render_record_detail_tabs(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    rows: list,
    show_all_fields: bool,
    show_ids: bool,
) -> None:
    if not rows or not selected_id:
        st.info("Use the sidebar to search and select records.")
        st.stop()

    try:
        record = get_record_with_children(
            db_path=db_path,
            api_name=api_name,
            record_id=selected_id,
            max_children_per_rel=50,
        )
    except Exception as exc:
        st.error(f"Error loading record {selected_id}: {exc}")
        st.stop()

    parent = record.parent
    parent_label = getattr(parent.sf_object, "label", None) or parent.sf_object.api_name

    import pandas as pd

    from sfdump.viewer_app.navigation.record_nav import pop

    _nav_stack = st.session_state.get("_sfdump_nav_stack", [])
    _can_back = isinstance(_nav_stack, list) and len(_nav_stack) > 1

    if _can_back:
        if st.button("Back", key="nav_back_main", type="secondary"):
            pop()
            st.rerun()

    tab_details, tab_children, tab_docs = st.tabs(["Details", "Children", "Documents"])

    with tab_details:
        st.markdown(
            f"**{parent_label}** "
            f"`{parent.data.get('Name', '')}` "
            f"(`{parent.data.get(parent.sf_object.id_field, selected_id)}`)"
        )

        with st.expander("Parent fields", expanded=True):
            all_items = sorted(parent.data.items())
            all_df = pd.DataFrame([{"Field": k, "Value": v} for k, v in all_items])

            if show_all_fields:
                parent_df = all_df
            else:
                important = get_important_fields(parent.sf_object.api_name)
                parent_df = all_df[all_df["Field"].isin(important)] if important else all_df

            st.table(parent_df)

    with tab_children:
        st.caption(
            "Open a relationship expander → pick a child in "
            "**Select a child record** → click **Open**."
        )
        render_children_with_navigation(
            record=record,
            show_all_fields=show_all_fields,
            show_ids=show_ids,
        )

    with tab_docs:
        render_documents_panel(
            db_path=db_path,
            object_type=api_name,
            record_id=selected_id,
            title="Documents tab preview",
        )


if __name__ == "__main__":
    main()
