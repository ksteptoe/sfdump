from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sfdump.viewer_app.services.nav import open_record
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

    # Precompute search blob (fast filtering)
    df["__search_blob"] = (
        df["file_name"].astype(str)
        + " "
        + df["object_type"].astype(str)
        + " "
        + df["record_name"].astype(str)
        + " "
        + df["record_id"].astype(str)
    ).str.lower()

    return df


def render_document_explorer(*, export_root: Path, key_prefix: str = "docx") -> None:
    st.subheader("Document Explorer")
    st.caption("Search across all documents using meta/master_documents_index.csv")

    df = _load_master_index(export_root)
    if df.empty:
        st.warning(f"master_documents_index.csv not found under: {export_root / 'meta'}")
        return

    # --- Filters
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        q = st.text_input(
            "Search (filename/record/object/id)", value="", key=f"{key_prefix}_q"
        ).strip()
    with c2:
        default_pdf_only = True
        pdf_only = st.checkbox(
            "PDF first (only .pdf)", value=default_pdf_only, key=f"{key_prefix}_pdf_only"
        )
    with c3:
        sources = sorted([s for s in df["file_source"].unique().tolist() if str(s).strip()])
        source = st.selectbox(
            "Source", options=["(all)"] + sources, index=0, key=f"{key_prefix}_src"
        )

    obj_types = sorted([s for s in df["object_type"].unique().tolist() if str(s).strip()])
    selected_types = st.multiselect(
        "Object types",
        options=obj_types,
        default=[],
        key=f"{key_prefix}_types",
        help="Leave empty for all object types.",
    )

    mask = pd.Series(True, index=df.index)

    if pdf_only:
        mask &= df["file_extension"].astype(str).str.lower().eq(".pdf") | df[
            "file_extension"
        ].astype(str).str.lower().eq("pdf")

    if source != "(all)":
        mask &= df["file_source"].astype(str).eq(source)

    if selected_types:
        mask &= df["object_type"].astype(str).isin(selected_types)

    if q:
        qq = q.lower()
        mask &= df["__search_blob"].str.contains(qq, na=False)

    results = df[mask].copy()

    st.info(f"Matches: {len(results):,}")
    st.dataframe(
        results[
            [
                c
                for c in [
                    "file_source",
                    "file_name",
                    "file_extension",
                    "object_type",
                    "record_name",
                    "record_id",
                    "local_path",
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
        fn = str(row.get("file_name", "")).strip() or "(no name)"
        ot = str(row.get("object_type", "")).strip()
        rn = str(row.get("record_name", "")).strip()
        fid = str(row.get("file_id", "")).strip()
        return f"{i+1:03d} — {fn} | {ot} | {rn} [{fid}]"

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
        key_prefix=f"{key_prefix}_preview_{chosen.get('file_id','')}",
        pdf_height=800,
    )
