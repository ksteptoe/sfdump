from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from sfdump.viewer import get_record_with_children
from sfdump.viewer_app.preview.files import preview_file
from sfdump.viewer_app.services.content import enrich_contentdocument_links_with_title
from sfdump.viewer_app.services.display import get_important_fields, select_display_columns
from sfdump.viewer_app.services.documents import (
    list_record_documents,
    resolve_local_path,
)
from sfdump.viewer_app.services.invoices import (
    find_invoices_for_opportunity,
    list_invoices_for_account,
)
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root


def render_record_tabs(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    show_all_fields: bool,
    show_ids: bool = False,
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

    def _open_child_control(*, child_api: str, child_df: "pd.DataFrame", key_prefix: str) -> None:
        """Option A: drill-down navigation for a child relationship table."""
        if child_df.empty or "Id" not in child_df.columns:
            return

        important = get_important_fields(child_api) or []

        def _label_row(r: dict[str, Any]) -> str:
            parts: list[str] = []
            for c in important:
                v = str(r.get(c, "") or "").strip()
                if v:
                    parts.append(v)

            if not parts:
                for c in ("Name", "Subject", "Title", "DocumentTitle"):
                    v = str(r.get(c, "") or "").strip()
                    if v:
                        parts.append(v)
                        break

            if not parts:
                parts.append(str(r.get("Id", "") or "").strip())

            return " — ".join(parts)

        opts = ["(select…)"]
        for _, rr in child_df.head(200).iterrows():
            rid = str(rr.get("Id", "") or "").strip()
            if not rid:
                continue
            opts.append(f"{_label_row(dict(rr))} [{rid}]")

        cols_open = st.columns([4, 1])
        with cols_open[0]:
            choice = st.selectbox(
                f"Open {child_api}",
                options=opts,
                index=0,
                key=f"{key_prefix}_sel",
            )
        with cols_open[1]:
            do_open = st.button(
                "Open",
                key=f"{key_prefix}_btn",
                disabled=(choice == opts[0]),
            )

        if do_open and choice != opts[0]:
            rid = choice.rsplit("[", 1)[-1].rstrip("]").strip()
            label = choice.rsplit("[", 1)[0].strip()
            push(child_api, rid, label=label)
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

        # Computed: invoices associated to this Opportunity's Account
        if api_name == "Opportunity":
            opp_account_id = str(parent.data.get("AccountId") or "")
            opp_account_name = str(
                parent.data.get("Account", "") or parent.data.get("AccountName", "") or ""
            )

            if opp_account_id:
                with st.expander("Invoices (via Account)", expanded=False):
                    rows, strategy = list_invoices_for_account(
                        db_path,
                        account_id=opp_account_id,
                        limit=200,
                    )
                    if strategy not in ("none", "no-table"):
                        st.caption(f"Invoice match: {strategy}")

                    if not rows:
                        st.info(
                            "No invoices found for the Opportunity's Account (or invoice table not present)."
                        )
                    else:
                        inv_df = pd.DataFrame(rows)

                        wanted = [
                            "Name",
                            "c2g__InvoiceDate__c",
                            "c2g__InvoiceStatus__c",
                            "c2g__InvoiceTotal__c",
                            "c2g__OutstandingValue__c",
                            "CurrencyIsoCode",
                            "Id",
                        ]
                        show = [c for c in wanted if c in inv_df.columns]
                        st.dataframe(
                            inv_df[show] if show else inv_df,
                            width="stretch",
                            hide_index=True,
                            height=260,
                        )

                        if "Id" in inv_df.columns:
                            opts = ["(select…)"]
                            for _, r in inv_df.iterrows():
                                rid = str(r.get("Id") or "")
                                name = str(r.get("Name") or rid or "(invoice)")
                                opts.append(f"{name} [{rid}]")

                            cols_open = st.columns([4, 1])
                            with cols_open[0]:
                                choice = st.selectbox(
                                    "Open invoice",
                                    options=opts,
                                    index=0,
                                    key=f"open_invoice_for_opp_{selected_id}",
                                )
                            with cols_open[1]:
                                if st.button(
                                    "Open",
                                    key=f"btn_open_invoice_for_opp_{selected_id}",
                                    disabled=(choice == opts[0]),
                                ):
                                    rid = choice.rsplit("[", 1)[-1].rstrip("]").strip()
                                    label = choice.rsplit("[", 1)[0].strip()
                                    push("c2g__codaInvoice__c", rid, label=label)
                                    st.rerun()
            else:
                if opp_account_name:
                    st.caption(
                        "Opportunity has no AccountId; cannot resolve invoices via account reliably."
                    )
                else:
                    st.caption("Opportunity has no AccountId; cannot resolve invoices.")

    with tab_children:
        # Opportunity -> Invoices traversal
        if parent.sf_object.api_name == "Opportunity":
            with st.expander("Invoices for this Opportunity", expanded=False):
                inv_rows = find_invoices_for_opportunity(db_path, selected_id, limit=200)

                inv_rows_list = inv_rows[0] if isinstance(inv_rows, tuple) else inv_rows
                if not inv_rows_list:
                    st.caption("No invoices found (or invoice tables/fields not present).")
                else:
                    inv_df = pd.DataFrame(inv_rows_list)

                    show = [
                        c
                        for c in [
                            "object_type",
                            "Name",
                            "c2g__InvoiceDate__c",
                            "InvoiceDate",
                            "c2g__InvoiceStatus__c",
                            "Status",
                            "c2g__InvoiceTotal__c",
                            "TotalAmount",
                            "c2g__OutstandingValue__c",
                            "Balance",
                            "Id",
                        ]
                        if c in inv_df.columns
                    ]

                    st.dataframe(
                        inv_df[show] if show else inv_df,
                        width="stretch",
                        hide_index=True,
                        height=220,
                    )

                    # Open invoice buttons
                    for r in (inv_rows_list or [])[:50]:
                        oid = str(r.get("Id") or "")
                        ot = str(r.get("object_type") or "")
                        nm = str(r.get("Name") or oid)
                        if oid and ot:
                            if st.button(
                                f"Open invoice: {ot} {nm}", key=f"open_invoice_{ot}_{oid}"
                            ):
                                push(ot, oid, label=nm)
                                st.rerun()

        if not record.children:
            st.info("No child records found for this record.")
            return

        for coll_idx, coll in enumerate(record.children):
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

                # Special handling for ContentDocumentLink to show titles
                if child_obj.api_name == "ContentDocumentLink":
                    child_df = enrich_contentdocument_links_with_title(db_path, child_df)

                display_cols = select_display_columns(
                    child_obj.api_name, child_df, show_all_fields, show_ids=show_ids
                )
                st.dataframe(child_df[display_cols], width="stretch", hide_index=True, height=260)

                # Option A (single implementation): drill-down open
                _open_child_control(
                    child_api=child_obj.api_name,
                    child_df=child_df,
                    key_prefix=f"open_child_{api_name}_{selected_id}_{child_obj.api_name}_{rel.name}_{coll_idx}",
                )

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
            return

        docs_df = pd.DataFrame(docs)

        # Best-effort: if local_path is blank but the file has been downloaded,
        # try to resolve it from disk using file_id (works for both 069* and 068* ids).
        lp_col = (
            "local_path"
            if "local_path" in docs_df.columns
            else ("path" if "path" in docs_df.columns else "")
        )
        if lp_col:
            docs_df[lp_col] = docs_df[lp_col].fillna("").astype(str)
            docs_df.loc[docs_df[lp_col].str.lower().eq("nan"), lp_col] = ""

            fid_col = (
                "file_id"
                if "file_id" in docs_df.columns
                else ("Id" if "Id" in docs_df.columns else "")
            )
            if fid_col:
                docs_df[fid_col] = docs_df[fid_col].fillna("").astype(str)

                mask = docs_df[lp_col].eq("") & docs_df[fid_col].ne("")
                if mask.any():

                    def _fill_local_path(row: "pd.Series") -> str:
                        fid = str(row.get(fid_col, "")).strip()
                        if not fid:
                            return ""
                        found = resolve_local_path(export_root, fid)
                        return str(found or "")

                    docs_df.loc[mask, lp_col] = docs_df.loc[mask].apply(_fill_local_path, axis=1)

        # Status + filter: treat blank path/local_path as missing on disk
        path_col = (
            "path"
            if "path" in docs_df.columns
            else ("local_path" if "local_path" in docs_df.columns else "")
        )
        if path_col:
            docs_df = docs_df.copy()
            docs_df["status"] = docs_df[path_col].apply(
                lambda x: "Downloaded" if str(x or "").strip() else "Missing"
            )
            missing_count = int((docs_df["status"] == "Missing").sum())
            st.caption(f"Documents: {len(docs_df)} (missing: {missing_count})")

            hide_missing = st.checkbox(
                "Hide missing (no local path)",
                value=False,
                key=f"hide_missing_docs_{api_name}_{selected_id}",
            )
            if hide_missing:
                docs_df = docs_df[docs_df["status"] == "Downloaded"].copy()
        else:
            st.caption(f"Documents: {len(docs_df)}")

        # Make parent/attachment explicit in the table
        if {"object_type", "record_name", "record_id"}.issubset(set(docs_df.columns)):
            docs_df = docs_df.copy()
            docs_df["attached_to"] = (
                docs_df["object_type"].astype(str)
                + " — "
                + docs_df["record_name"].astype(str)
                + " ["
                + docs_df["record_id"].astype(str)
                + "]"
            )

        show_cols = [
            c
            for c in [
                "status",
                "attached_to",
                "file_source",
                "file_id",
                "file_name",
                "file_extension",
                "path",
                "local_path",
                "size_bytes",
                "content_type",
            ]
            if c in docs_df.columns
        ]
        st.dataframe(docs_df[show_cols], width="stretch", hide_index=True, height=260)

        # Build preview choices (single source of truth)
        choices = ["-- Select --"]
        lp_col2 = (
            "local_path"
            if "local_path" in docs_df.columns
            else ("path" if "path" in docs_df.columns else "")
        )
        for _, r in docs_df.iterrows():
            name = str(r.get("file_name", "") or "")
            ext = str(r.get("file_extension", "") or "")
            fid = str(r.get("file_id", "") or "")
            attached = str(r.get("attached_to", "") or "")

            title = name + ("." + ext if ext and not name.endswith("." + ext) else "")
            prefix = title
            if attached:
                prefix = prefix + " — " + attached

            lp = str(r.get(lp_col2, "") or "") if lp_col2 else ""
            if lp:
                choices.append(prefix + " :: " + lp)
            elif fid:
                choices.append(prefix + " [" + fid + "]")
            else:
                choices.append(prefix)

        selected_doc = st.selectbox(
            "Preview a document",
            choices,
            index=0,
            key=f"doc_preview_{api_name}_{selected_id}",
        )

        local_path = ""
        file_id = ""

        # selected_doc format: '<label> :: <local_path>' OR '<label> [<file_id>]'
        if "::" in selected_doc:
            local_path = selected_doc.rsplit("::", 1)[-1].strip()
        elif selected_doc.endswith("]") and "[" in selected_doc:
            file_id = selected_doc.rsplit("[", 1)[-1][:-1].strip()
            found = resolve_local_path(export_root, file_id)
            if found:
                local_path = str(found)

        if local_path:
            preview_file(export_root, local_path)
        elif selected_doc != "-- Select --":
            st.info(
                "No local file path is available for this document. "
                "Try running `sfdump files-backfill` to download missing Files into the export."
            )
