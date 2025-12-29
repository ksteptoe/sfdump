from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd  # type: ignore[import-not-found]
import streamlit as st

from sfdump.viewer_app.preview.files import preview_file
from sfdump.viewer_app.services.display import get_important_fields, select_display_columns
from sfdump.viewer_app.services.documents import (
    list_record_documents,
    resolve_local_path,
)

# Your invoice heuristics module (the one you pasted earlier)
# Adjust this import path if your project uses a different module name.
from sfdump.viewer_app.services.invoices import (  # type: ignore[import-not-found]
    find_invoices_for_opportunity,
)
from sfdump.viewer_app.services.nav import current as nav_current
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root

# ---------------------------
# Minimal "record" abstraction
# ---------------------------


@dataclass(frozen=True)
class SFObject:
    api_name: str
    id_field: str = "Id"


@dataclass
class ParentRecord:
    sf_object: SFObject
    data: dict[str, Any]


@dataclass(frozen=True)
class Relationship:
    name: str
    child_field: str


@dataclass
class ChildCollection:
    sf_object: SFObject
    relationship: Relationship
    records: list[dict[str, Any]]


@dataclass
class RecordBundle:
    parent: ParentRecord
    children: list[ChildCollection]


# ---------------------------
# DB helpers
# ---------------------------


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _load_parent_record(db_path: Path, api_name: str, record_id: str) -> Optional[dict[str, Any]]:
    """
    Load a single record from a table matching api_name.
    This assumes your builder uses table names identical to api_name.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if not _table_exists(cur, api_name):
            return None
        cur.execute(f'SELECT * FROM "{api_name}" WHERE "Id" = ? LIMIT 1', (record_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _load_children_stub(db_path: Path, api_name: str, record_id: str) -> list[ChildCollection]:
    """
    Best-effort children loader.
    If your project has a proper relationship engine, replace this with it.

    For now: return no children (except special cases handled elsewhere).
    """
    # In your “real” repo you likely already have relationship discovery.
    # This stub keeps the viewer working even without it.
    return []


def _load_record_bundle(db_path: Path, api_name: str, record_id: str) -> Optional[RecordBundle]:
    parent = _load_parent_record(db_path, api_name, record_id)
    if not parent:
        return None
    parent_rec = ParentRecord(sf_object=SFObject(api_name=api_name, id_field="Id"), data=parent)
    children = _load_children_stub(db_path, api_name, record_id)
    return RecordBundle(parent=parent_rec, children=children)


# ---------------------------
# UI helpers
# ---------------------------


def _open_child_control(*, child_api: str, child_df: "pd.DataFrame", key_prefix: str) -> None:
    """
    Generic drill-down selector:
      - expects child_df contains an "Id" column
      - tries to label rows by Name/Subject/Title/etc
    """
    if child_df is None or child_df.empty:
        return
    if "Id" not in child_df.columns:
        st.caption("No Id column available for drill-down.")
        return

    important = get_important_fields(child_api)

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
    rows = child_df.to_dict(orient="records")
    for r in rows:
        rid = str(r.get("Id") or "").strip()
        if not rid:
            continue
        opts.append(f"{_label_row(r)} [{rid}]")

    cols = st.columns([4, 1])
    with cols[0]:
        choice = st.selectbox(
            "Open record",
            options=opts,
            index=0,
            key=f"{key_prefix}_select",
        )
    with cols[1]:
        if st.button("Open", key=f"{key_prefix}_open", disabled=(choice == opts[0])):
            rid = choice.rsplit("[", 1)[-1].rstrip("]").strip()
            label = choice.rsplit("[", 1)[0].strip()
            push(child_api, rid, label=label)
            st.rerun()


# ---------------------------
# Main tabs renderer
# ---------------------------


def render_record_tabs(
    *,
    db_path: Path,
    api_name: str,
    selected_id: str,
    show_all_fields: bool,
    show_ids: bool,
) -> None:
    """
    Render the record viewer area (Details / Children / Documents).
    Uses navigation stack if present.
    """
    nav = nav_current()
    if nav is not None:
        api_name = nav.api_name
        selected_id = nav.record_id

    record = _load_record_bundle(db_path, api_name, selected_id)
    if record is None:
        st.error(f"Record not found: {api_name} [{selected_id}]")
        return

    parent = record.parent
    parent_label = parent.sf_object.api_name

    tab_details, tab_children, tab_docs = st.tabs(["Details", "Children", "Documents"])

    # -------- Details --------
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

    # -------- Children --------
    with tab_children:
        # Opportunity -> Invoices traversal
        if parent.sf_object.api_name == "Opportunity":
            with st.expander("Invoices for this Opportunity", expanded=False):
                rows, strategy = find_invoices_for_opportunity(db_path, selected_id, limit=200)
                if strategy not in ("none", "no-table"):
                    st.caption(f"Invoice match: {strategy}")

                if not rows:
                    st.caption("No invoices found (or invoice tables/fields not present).")
                else:
                    inv_df = pd.DataFrame(rows)
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
                            "_via",
                        ]
                        if c in inv_df.columns
                    ]

                    st.dataframe(
                        inv_df[show] if show else inv_df,
                        width="stretch",
                        hide_index=True,
                        height=220,
                    )

                    # Drill-down to an invoice record
                    _open_child_control(
                        child_api="c2g__codaInvoice__c",
                        child_df=inv_df,
                        key_prefix=f"open_invoice_from_opp_{selected_id}",
                    )

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

                display_cols = select_display_columns(
                    child_obj.api_name, child_df, show_all_fields, show_ids=show_ids
                )
                st.dataframe(child_df[display_cols], width="stretch", hide_index=True, height=260)

                _open_child_control(
                    child_api=child_obj.api_name,
                    child_df=child_df,
                    key_prefix=(
                        f"open_child_{api_name}_{selected_id}_"
                        f"{child_obj.api_name}_{rel.name}_{coll_idx}"
                    ),
                )

    # -------- Documents --------
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

        # Resolve local path from disk if missing
        lp_col = (
            "path"
            if "path" in docs_df.columns
            else ("local_path" if "local_path" in docs_df.columns else "")
        )
        fid_col = (
            "file_id" if "file_id" in docs_df.columns else ("Id" if "Id" in docs_df.columns else "")
        )

        if lp_col and fid_col:
            docs_df = docs_df.copy()
            docs_df[lp_col] = docs_df[lp_col].fillna("").astype(str)
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

        # Status + filter
        if lp_col:
            docs_df = docs_df.copy()
            docs_df["status"] = docs_df[lp_col].apply(
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

        # Attached_to column (nice display)
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

        # Preview choices
        choices = ["-- Select --"]
        lp_col2 = (
            "path"
            if "path" in docs_df.columns
            else ("local_path" if "local_path" in docs_df.columns else "")
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
