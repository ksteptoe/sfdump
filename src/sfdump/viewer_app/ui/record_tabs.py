from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from sfdump.viewer_app.preview.files import preview_file
from sfdump.viewer_app.services.display import get_important_fields, select_display_columns
from sfdump.viewer_app.services.documents import list_record_documents, load_master_documents_index
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root


def render_record_tabs(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    record: Any,
    show_all_fields: bool,
) -> None:
    """
    Renders the right pane: Details / Children / Documents (+ subtree docs if present).

    Navigation:
      - In Children tab, pick a child Id and click "Open" to push into nav stack.
      - Sidebar breadcrumbs + Back/Reset work via services.nav.
    """
    import pandas as pd  # type: ignore[import-not-found]

    parent = record.parent
    parent_label = getattr(parent.sf_object, "label", None) or parent.sf_object.api_name

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
        if not record.children:
            st.info("No child records found for this record.")
        else:
            st.caption("Tip: use the **Open** button inside a child relationship to navigate down.")
            for idx, coll in enumerate(record.children):
                child_obj = coll.sf_object
                rel = coll.relationship

                title = (
                    f"{child_obj.api_name} via {rel.child_field} "
                    f"(relationship: {rel.name}, {len(coll.records)} record(s))"
                )
                with st.expander(title, expanded=False):
                    child_df = pd.DataFrame(coll.records)
                    if child_df.empty:
                        st.info("No rows.")
                        continue

                    display_cols = select_display_columns(
                        child_obj.api_name, child_df, show_all_fields
                    )
                    st.dataframe(
                        child_df[display_cols] if display_cols else child_df,
                        width="stretch",
                        hide_index=True,
                        height=240,
                    )

                    # Navigation control: pick a child Id and Open
                    if "Id" in child_df.columns and len(child_df) > 0:
                        ids = [str(x) for x in child_df["Id"].fillna("").tolist() if str(x)]
                        if ids:
                            col_a, col_b = st.columns([3, 1])
                            with col_a:
                                picked = st.selectbox(
                                    "Child record Id",
                                    options=ids,
                                    key=f"child_pick_{idx}_{child_obj.api_name}",
                                )
                            with col_b:
                                if st.button(
                                    "Open",
                                    key=f"child_open_{idx}_{child_obj.api_name}",
                                    help="Navigate to this child record",
                                ):
                                    push(child_obj.api_name, picked, label=picked)
                                    st.rerun()

    with tab_docs:
        export_root = infer_export_root(db_path)
        if export_root is None:
            st.warning(
                "Could not infer EXPORT_ROOT from DB path (expected EXPORT_ROOT/meta/sfdata.db)."
            )
            st.stop()

        docs = list_record_documents(
            db_path=db_path,
            object_type=api_name,
            record_id=selected_id,
        )

        if not docs:
            st.info("No documents indexed for this record (in record_documents table).")
        else:
            docs_df = pd.DataFrame(docs)

            # compact table
            show_cols = [
                c
                for c in [
                    "file_source",
                    "file_id",
                    "file_name",
                    "file_extension",
                    "local_path",
                    "path",
                    "content_type",
                ]
                if c in docs_df.columns
            ]
            st.dataframe(docs_df[show_cols], width="stretch", hide_index=True, height=220)

            def _label(row: dict[str, Any]) -> str:
                name = row.get("file_name") or "(no name)"
                lp = row.get("local_path") or row.get("path") or ""
                return f"{name} :: {lp}"

            options = [_label(r) for r in docs]
            choice = st.selectbox("Preview a document", options, index=0, key="docs_preview_picker")

            chosen = docs[options.index(choice)]
            lp = str(chosen.get("local_path") or chosen.get("path") or "").strip()
            if not lp:
                st.warning("No local path for this document (it may not have been downloaded).")
            else:
                preview_file(export_root, lp, height=900, label="Selected document")

        # Optional: master index (subtree filtering) if present
        with st.expander("Recursive documents (subtree)", expanded=False):
            df = load_master_documents_index(export_root)
            if df is None:
                st.info("meta/master_documents_index.csv not found (subtree doc browse disabled).")
                return

            st.caption(
                "master_documents_index.csv loaded. (Filtering requires traversal IDs in db_app.)"
            )
            st.dataframe(df.head(50), hide_index=True, width="stretch")
