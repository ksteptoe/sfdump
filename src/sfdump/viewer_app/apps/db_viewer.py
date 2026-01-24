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


def _export_root_from_db_path(db_path: Path) -> Optional[Path]:
    """
    Best-effort: infer EXPORT_ROOT from db_path.
    Typical layout: EXPORT_ROOT/meta/sfdata.db
    """
    return infer_export_root(db_path)


def _initial_db_path_from_argv() -> Optional[Path]:
    import os

    # First check environment variable (set by orchestrator)
    env_db = os.environ.get("SFDUMP_DB_PATH")
    if env_db:
        return Path(env_db)

    # Check command line: streamlit run <entry> -- <db-path>
    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)

    # Fallback: find the latest export with a database
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


def main() -> None:
    st.set_page_config(page_title="SF Dump DB Viewer", layout="wide")
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

    st.title("SF Dump DB Viewer")

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

    # NEW LAYOUT: Left = Object details (narrower), Right = Documents (wider)
    col_left, col_right = st.columns([2, 3])

    # ------------------------------------------------------------------
    # LEFT COLUMN: Object Details & Relationships
    # ------------------------------------------------------------------
    with col_left:
        st.subheader("Record details & relationships")

        # Render record list to get selected record
        rows, selected_id = render_record_list(
            db_path=db_path,
            api_name=api_name,
            selected_label=selected_label,
            selected_id=state.selected_id,
            search_term=search_term,
            regex_search=regex_search,
            limit=int(limit),
            show_all_fields=show_all_fields,
            show_ids=state.show_ids,
        )

    # ------------------------------------------------------------------
    # RIGHT COLUMN: Documents & Preview
    # ------------------------------------------------------------------
    with col_right:
        st.subheader("Documents")

        # Render documents (we have selected_id from left column)
        if not rows or not selected_id:
            st.info("Select a record from the list on the left to see documents.")
        else:
            # Recursive subtree document search (Account -> Opp -> Invoice -> ...)
            export_root = _export_root_from_db_path(db_path)
            if export_root is None:
                st.warning(
                    "Could not infer EXPORT_ROOT from DB path. "
                    "Expected EXPORT_ROOT/meta/sfdata.db layout."
                )
            else:
                # Controls in collapsed expander
                with st.expander("⚙️ Recursive docs controls", expanded=False):
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

                # Collect subtree (children of current record)
                subtree = collect_subtree_ids(
                    db_path=db_path,
                    root_api=api_name,
                    root_id=selected_id,
                    max_depth=int(max_depth) if "max_depth" in locals() else 3,
                    max_children_per_rel=int(max_children) if "max_children" in locals() else 100,
                    allow_objects=allow_objects if "allow_objects" in locals() else None,
                )

                # ALSO include parent records from navigation stack
                from sfdump.viewer_app.navigation.record_nav import breadcrumbs

                nav_stack = breadcrumbs()
                for nav_item in nav_stack:
                    if nav_item.api_name not in subtree:
                        subtree[nav_item.api_name] = set()
                    subtree[nav_item.api_name].add(nav_item.record_id)

                total_records = sum(len(v) for v in subtree.values())

                # Load and filter documents
                docs_df = load_master_documents_index(export_root)
                if docs_df is None:
                    st.error(
                        "meta/master_documents_index.csv not found. "
                        "Run: `sfdump docs-index --export-root <EXPORT_ROOT>`"
                    )
                else:
                    all_ids: set[str] = set()
                    for ids in subtree.values():
                        all_ids.update(ids)

                    sub_docs = docs_df[docs_df["record_id"].isin(list(all_ids))].copy()

                    # Combined summary on one line
                    st.write(
                        f"📊 **{total_records}** records across **{len(subtree)}** types  "
                        f"│  📄 **{len(sub_docs)}** documents"
                    )

                    if len(sub_docs) == 0:
                        st.info("No documents attached to any record in the subtree.")
                    else:
                        # Documents summary table
                        show_cols = [
                            "file_extension",
                            "file_name",
                            "object_type",
                            "record_name",
                            "account_name",
                            "opp_name",
                        ]
                        show_cols = [c for c in show_cols if c in sub_docs.columns]
                        st.dataframe(
                            sub_docs[show_cols],
                            height=260,
                            hide_index=True,
                        )

                        # Documents list + PDF preview (always visible)
                        from sfdump.viewer_app.ui.documents_panel import (
                            render_documents_panel_from_rows,
                        )

                        render_documents_panel_from_rows(
                            export_root=export_root,
                            rows=sub_docs.to_dict(orient="records"),
                            title="📎 Document Preview",
                            key_prefix=f"subtree_docs_{api_name}_{selected_id}",
                            pdf_height=800,
                        )

    # Continue with left column - record details tabs
    with col_left:
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

        import pandas as pd  # type: ignore[import-not-found]

        # NAV-002: Back button (main pane) pops the navigation stack
        from sfdump.viewer_app.navigation.record_nav import pop

        _nav_stack = st.session_state.get("_sfdump_nav_stack", [])
        _can_back = isinstance(_nav_stack, list) and len(_nav_stack) > 1

        if _can_back:
            if st.button("⬅ Back", key="nav_back_main", type="secondary"):
                pop()
                st.rerun()

        tab_details, tab_children, tab_docs, tab_explorer = st.tabs(
            ["Details", "Children", "Documents", "Explorer"]
        )

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
                "Open a relationship expander → pick a child in **Select a child record** → click **Open**."
            )
            render_children_with_navigation(
                record=record,
                show_all_fields=show_all_fields,
                show_ids=state.show_ids,
            )

        with tab_docs:
            render_documents_panel(
                db_path=db_path,
                object_type=api_name,
                record_id=selected_id,
                title="Documents tab preview",
            )

        with tab_explorer:
            export_root = _export_root_from_db_path(db_path)
            if export_root is None:
                st.warning(
                    "Could not infer EXPORT_ROOT from DB path (expected EXPORT_ROOT/meta/sfdata.db)."
                )
                st.stop()

            render_document_explorer(
                export_root=export_root,
                key_prefix=f"expl_{api_name}_{selected_id}",
            )


if __name__ == "__main__":
    main()
