from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sfdump.utils import glob_to_regex
from sfdump.viewer_app.navigation.record_nav import open_record
from sfdump.viewer_app.ui.documents_panel import render_documents_panel_from_rows


@st.cache_data(show_spinner=False)
def _load_master_index(export_root: Path) -> pd.DataFrame:
    path = export_root / "meta" / "master_documents_index.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, dtype=str).fillna("")

    # Normalize a few column names we rely on
    cols_lower = {c.lower(): c for c in df.columns}

    def _ensure(target: str, aliases: list[str]) -> None:
        if target in df.columns:
            return
        for a in aliases:
            if a.lower() in cols_lower:
                df[target] = df[cols_lower[a.lower()]]
                return
        df[target] = ""

    _ensure("file_id", ["file_id", "content_document_id", "document_id", "id"])
    _ensure("file_name", ["file_name", "title", "name"])
    _ensure("file_extension", ["file_extension", "ext", "extension"])
    _ensure("file_source", ["file_source", "source"])
    _ensure("object_type", ["object_type", "record_api", "api_name"])
    _ensure("record_id", ["record_id", "linked_entity_id", "linkedentityid"])
    _ensure("record_name", ["record_name"])
    _ensure("local_path", ["local_path", "path"])
    _ensure("account_name", ["account_name"])
    _ensure("account_id", ["account_id"])
    _ensure("opp_name", ["opp_name"])
    _ensure("opp_id", ["opp_id"])

    # Precompute search blob (fast filtering)
    df["__search_blob"] = (
        df["file_name"].astype(str)
        + " "
        + df["object_type"].astype(str)
        + " "
        + df["record_name"].astype(str)
        + " "
        + df["record_id"].astype(str)
        + " "
        + df["account_name"].astype(str)
        + " "
        + df["opp_name"].astype(str)
    ).str.lower()

    return df


def render_document_explorer(*, export_root: Path, key_prefix: str = "docx") -> None:
    st.subheader("Document Explorer")
    st.caption("Search across all exported documents")

    df = _load_master_index(export_root)
    if df.empty:
        st.warning(f"master_documents_index.csv not found under: {export_root / 'meta'}")
        return

    # --- Primary Search (most important - front and center)
    q = st.text_input(
        "Search",
        value="",
        key=f"{key_prefix}_q",
        placeholder="e.g. PIN01006*, SIN002469, Softcat...",
        help="Search by file name, invoice number, record name, or ID. Supports wildcards.",
    ).strip()

    # Search tips (collapsed by default)
    with st.expander("Search tips"):
        st.markdown(
            """
| Pattern | Meaning | Example |
|---------|---------|---------|
| `*` | Any characters | `PIN01006*` matches PIN010060, PIN010061, ... |
| `?` | Single character | `PIN01006?` matches PIN010060 to PIN010069 |
| `[1-5]` | Range | `PIN0100[6-9]*` matches PIN01006x, PIN01007x, ... |
| `[abc]` | Any of a, b, c | `[SP]IN*` matches SIN... or PIN... |
| `[!0-9]` | Not a digit | `*[!0-9].pdf` matches files not ending in digit |
"""
        )

    # PDF filter and match count on same row
    col_pdf, col_count = st.columns([1, 3])
    with col_pdf:
        pdf_only = st.checkbox("PDF only", value=False, key=f"{key_prefix}_pdf_only")

    # --- Additional Filters (collapsed by default)
    with st.expander("Additional Filters"):
        col_acct, col_opp = st.columns(2)
        with col_acct:
            account_search = st.text_input(
                "Account Name",
                value="",
                key=f"{key_prefix}_account",
                placeholder="e.g. Arm Limited, Intel...",
                help="Filter by Account name (partial match)",
            ).strip()
        with col_opp:
            opp_search = st.text_input(
                "Opportunity Name",
                value="",
                key=f"{key_prefix}_opp",
                placeholder="e.g. Project-Alpha...",
                help="Filter by Opportunity name (partial match)",
            ).strip()

        obj_types = sorted([s for s in df["object_type"].unique().tolist() if str(s).strip()])
        selected_types = st.multiselect(
            "Object types",
            options=obj_types,
            default=[],
            key=f"{key_prefix}_types",
            help="Leave empty for all object types",
        )

    mask = pd.Series(True, index=df.index)

    # Primary search filter (case-insensitive, supports * and ? wildcards)
    if q:
        pattern = glob_to_regex(q.lower())
        mask &= df["__search_blob"].str.contains(pattern, na=False, regex=True)

    # PDF filter
    if pdf_only:
        mask &= df["file_extension"].astype(str).str.lower().eq(".pdf") | df[
            "file_extension"
        ].astype(str).str.lower().eq("pdf")

    # Account and Opportunity filters (case-insensitive partial match)
    if account_search:
        account_lower = account_search.lower()
        mask &= df["account_name"].astype(str).str.lower().str.contains(account_lower, na=False)

    if opp_search:
        opp_lower = opp_search.lower()
        mask &= df["opp_name"].astype(str).str.lower().str.contains(opp_lower, na=False)

    if selected_types:
        mask &= df["object_type"].astype(str).isin(selected_types)

    has_filter = bool(q or pdf_only or account_search or opp_search or selected_types)

    results = df[mask].copy()

    # Show match count
    with col_count:
        if has_filter:
            st.markdown(f"**{len(results):,}** documents found")
        else:
            st.markdown(f"**{len(df):,}** documents available for search")

    if not has_filter:
        return

    st.dataframe(
        results[
            [
                c
                for c in [
                    "record_name",
                    "file_name",
                    "account_name",
                    "opp_name",
                    "object_type",
                    "file_extension",
                    "record_id",
                    "file_id",
                ]
                if c in results.columns
            ]
        ].head(500),
        width="stretch",
        hide_index=True,
        height=260,
    )

    if results.empty:
        return

    # --- Picker (first 500 for responsiveness)
    limited = results.head(500).reset_index(drop=True)

    def _label(i: int, row: pd.Series) -> str:
        rn = str(row.get("record_name", "")).strip() or "(no record)"
        fn = str(row.get("file_name", "")).strip() or "(no name)"
        return f"{i + 1:03d} — {rn} | {fn}"

    labels = [_label(i, limited.iloc[i]) for i in range(len(limited))]

    choice = st.selectbox("Select a document", options=labels, index=0, key=f"{key_prefix}_pick")
    idx = labels.index(choice)
    row = limited.iloc[idx]

    rel_path = str(row.get("local_path", "")).strip()
    if not rel_path:
        st.warning(
            "This row has no local_path/path (index knows it exists, but no on-disk path is recorded)."
        )
        return

    chosen: dict[str, Any] = {
        "file_source": str(row.get("file_source", "")),
        "file_id": str(row.get("file_id", "")),
        "file_name": str(row.get("file_name", "")),
        "file_extension": str(row.get("file_extension", "")),
        "record_id": str(row.get("record_id", "")),
        "object_type": str(row.get("object_type", "")),
        "record_name": str(row.get("record_name", "")),
        "path": rel_path,
        "local_path": rel_path,
    }

    # --- Jump to parent record (if indexed)
    parent_api = str(row.get("object_type", "")).strip()
    parent_id = str(row.get("record_id", "")).strip()
    parent_label = str(row.get("record_name", "")).strip() or parent_id

    cols = st.columns([1, 3])
    with cols[0]:
        if st.button(
            "Open parent record", key=f"{key_prefix}_open_parent_{parent_api}_{parent_id}"
        ):
            if parent_api and parent_id:
                open_record(parent_api, parent_id, label=parent_label)
                st.session_state["_sfdump_view"] = "db_viewer"
                st.rerun()
            else:
                st.warning(
                    "This row is missing object_type or record_id, so navigation isn’t possible."
                )
    with cols[1]:
        st.caption(f"{parent_api} / {parent_id}")

    render_documents_panel_from_rows(
        export_root=export_root,
        rows=[chosen],
        title="Preview",
        key_prefix=f"{key_prefix}_preview_{chosen.get('file_id', '')}",
        pdf_height=800,
    )
