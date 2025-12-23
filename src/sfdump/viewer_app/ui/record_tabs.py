from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit as st

from sfdump.indexing import OBJECTS
from sfdump.viewer import get_record_with_children
from sfdump.viewer_app.preview.files import open_local_file, preview_file
from sfdump.viewer_app.preview.pdf import preview_pdf_bytes
from sfdump.viewer_app.services.content import enrich_contentdocument_links_with_title
from sfdump.viewer_app.services.display import get_important_fields, select_display_columns
from sfdump.viewer_app.services.documents import (
    list_record_documents,
    load_master_documents_index,
)
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root, resolve_export_path
from sfdump.viewer_app.services.traversal import collect_subtree_ids


def render_record_tabs(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    show_all_fields: bool,
) -> None:
    st.subheader("Record details & relationships")

    try:
        record = get_record_with_children(
            db_path=db_path,
            api_name=api_name,
            record_id=selected_id,
            max_children_per_rel=50,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error loading record {selected_id}: {exc}")
        return

    parent = record.parent
    parent_label = getattr(parent.sf_object, "label", None) or parent.sf_object.api_name

    import pandas as pd  # type: ignore[import-not-found]

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
            for coll in record.children:
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
                    else:
                        if child_obj.api_name == "ContentDocumentLink":
                            child_df = enrich_contentdocument_links_with_title(db_path, child_df)

                        display_cols = select_display_columns(
                            child_obj.api_name, child_df, show_all_fields, show_ids=False
                        )
                        st.dataframe(
                            child_df[display_cols],
                            width="stretch",
                            hide_index=True,
                            height=260,
                        )

                        # Option A drill-down (Open) for Opportunities
                        if child_obj.api_name == "Opportunity" and "Id" in child_df.columns:
                            opts: list[str] = []
                            for _, r in child_df.iterrows():
                                rid = str(r.get("Id") or "")
                                name = str(r.get("Name") or rid or "(no name)")
                                opts.append(f"{name} [{rid}]")

                            cols_open = st.columns([4, 1])
                            with cols_open[0]:
                                choice = st.selectbox(
                                    "Open Opportunity",
                                    options=opts,
                                    index=0,
                                    key=f"open_opp_{api_name}_{selected_id}_{child_obj.api_name}_{rel.name}",
                                )
                            with cols_open[1]:
                                if st.button(
                                    "Open",
                                    key=f"btn_open_opp_{api_name}_{selected_id}_{child_obj.api_name}_{rel.name}",
                                ):
                                    rid = choice.rsplit("[", 1)[-1].rstrip("]")
                                    label = choice.rsplit("[", 1)[0].strip()
                                    push("Opportunity", rid, label=label)
                                    st.rerun()

                        # Option A drill-down (Open) for Opportunities
                        if child_obj.api_name == "Opportunity" and "Id" in child_df.columns:
                            opts = []
                            for _, r in child_df.iterrows():
                                rid = str(r.get("Id") or "")
                                name = str(r.get("Name") or rid or "(no name)")
                                opts.append(f"{name} [{rid}]")

                            cols_open = st.columns([4, 1])
                            with cols_open[0]:
                                choice = st.selectbox(
                                    "Open Opportunity",
                                    options=opts,
                                    index=0,
                                    key=f"open_opp_{api_name}_{selected_id}_{child_obj.api_name}_{rel.name}",
                                )
                            with cols_open[1]:
                                if st.button(
                                    "Open",
                                    key=f"btn_open_opp_{api_name}_{selected_id}_{child_obj.api_name}_{rel.name}",
                                ):
                                    rid = choice.rsplit("[", 1)[-1].rstrip("]")
                                    label = choice.rsplit("[", 1)[0].strip()
                                    push("Opportunity", rid, label=label)
                                    st.rerun()

    with tab_docs:
        export_root = infer_export_root(db_path)
        if export_root is None:
            st.warning(
                "Could not infer EXPORT_ROOT from DB path. "
                "Expected EXPORT_ROOT/meta/sfdata.db layout."
            )
            return

        docs = list_record_documents(
            db_path=db_path,
            object_type=api_name,
            record_id=selected_id,
        )

        if not docs:
            st.info("No documents indexed for this record.")
        else:
            docs_df = pd.DataFrame(docs)

            show_cols = [
                c
                for c in [
                    "file_source",
                    "file_id",
                    "file_name",
                    "file_extension",
                    "path",
                    "size_bytes",
                    "content_type",
                ]
                if c in docs_df.columns
            ]
            st.dataframe(docs_df[show_cols], width="stretch", hide_index=True, height=260)

            def _label(row: dict[str, Any]) -> str:
                name = row.get("file_name") or "(no name)"
                fid = row.get("file_id") or ""
                return f"{name} [{fid}]"

            options = [_label(r) for r in docs]
            choice = st.selectbox("Select a document", options, index=0)

            chosen = docs[options.index(choice)]
            rel_path = str(chosen.get("path") or "")
            if not rel_path:
                st.warning(
                    "This row has no local path. That usually means the file wasn’t downloaded into the export."
                )
            else:
                full_path = resolve_export_path(export_root, rel_path)

                cols = st.columns([1, 3])
                with cols[0]:
                    if st.button("Open"):
                        if full_path.exists():
                            open_local_file(full_path)
                            st.success("Opened locally.")
                        else:
                            st.error(f"File not found on disk: {full_path}")

                with cols[1]:
                    st.caption(str(full_path))

                if full_path.exists():
                    data = full_path.read_bytes()
                    download_name = full_path.name
                    mime = chosen.get("content_type") or "application/octet-stream"
                    ext = full_path.suffix.lower()

                    if ext == ".pdf":
                        with st.expander("Preview PDF", expanded=True):
                            preview_pdf_bytes(data, height=750)
                    elif str(mime).startswith("image/"):
                        with st.expander("Preview image", expanded=True):
                            st.image(data, caption=download_name)

                    st.download_button(
                        "Download",
                        data=data,
                        file_name=download_name,
                        mime=str(mime),
                    )
                else:
                    st.error(f"File not found on disk: {full_path}")

    with st.expander("Recursive documents (subtree)", expanded=True):
        export_root = infer_export_root(db_path)
        if export_root is None:
            st.warning(
                "Could not infer EXPORT_ROOT from DB path. "
                "Expected EXPORT_ROOT/meta/sfdata.db layout."
            )
            st.stop()

        st.caption(f"Export root inferred as: {export_root}")

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

        total_records = sum(len(v) for v in subtree.values())
        st.write(f"Records in subtree: **{total_records}** across **{len(subtree)}** object types.")
        st.write({k: len(v) for k, v in sorted(subtree.items(), key=lambda x: -len(x[1]))})

        docs_df = load_master_documents_index(export_root)
        if docs_df is None:
            st.error(
                "meta/master_documents_index.csv not found. "
                "Run: `sfdump docs-index --export-root <EXPORT_ROOT>` "
                "(or `make -f Makefile.export export-doc-index`)."
            )
            st.stop()

        all_ids: set[str] = set()
        for ids in subtree.values():
            all_ids.update(ids)

        sub_docs = docs_df[docs_df["record_id"].isin(list(all_ids))].copy()

        st.write(f"Documents found: **{len(sub_docs)}**")
        if len(sub_docs) == 0:
            st.info("No documents attached to any record in the subtree.")
            st.stop()

        show_cols = [
            "file_extension",
            "file_source",
            "file_name",
            "local_path",
            "object_type",
            "record_name",
            "account_name",
            "opp_name",
            "opp_stage",
            "opp_amount",
            "opp_close_date",
        ]
        show_cols = [c for c in show_cols if c in sub_docs.columns]
        st.dataframe(sub_docs[show_cols], height=260, hide_index=True, width="stretch")

        choices = []
        for _, r in sub_docs.iterrows():
            lp = r.get("local_path", "")
            fn = r.get("file_name", "")
            rn = r.get("record_name", "")
            ot = r.get("object_type", "")
            rid = r.get("record_id", "")
            label = f"{fn} — {ot}:{rn} [{rid}] :: {lp}"
            choices.append(label)

        selected_doc = st.selectbox("Preview a document", choices, index=0)
        local_path = selected_doc.rsplit("::", 1)[-1].strip()
        if local_path:
            preview_file(export_root, local_path)
