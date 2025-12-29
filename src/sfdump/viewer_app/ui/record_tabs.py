from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

from sfdump.viewer_app.preview import preview_file
from sfdump.viewer_app.services.documents import load_master_documents_index, resolve_document_path
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root


def _pick_table(cur: sqlite3.Cursor, api_name: str) -> Optional[str]:
    candidates = [api_name, api_name.lower()]
    for t in candidates:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,))
        if cur.fetchone() is not None:
            return t
    return None


def _load_record_row(db_path: Path, api_name: str, record_id: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        table = _pick_table(cur, api_name)
        if not table:
            return None
        cur.execute(f'SELECT * FROM "{table}" WHERE Id=? LIMIT 1', (record_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def render_record_tabs(*, db_path: Path, api_name: str, record_id: str) -> None:
    export_root = infer_export_root(Path(db_path))

    tabs = st.tabs(["Details", "Children", "Documents"])

    with tabs[0]:
        row = _load_record_row(Path(db_path), api_name, record_id)
        if not row:
            st.info("Record details not available.")
        else:
            st.dataframe(pd.DataFrame([row]))

    with tabs[1]:
        st.caption("Subtree navigation is based on the exported relationships/indexing you built.")
        st.info(
            "If you want richer child traversal (per-relationship lists), we can add it once we confirm the relationship tables you’re persisting."
        )

        # A simple “jump” UI: allow manual push to nav stack
        c1, c2 = st.columns([2, 2])
        with c1:
            child_api = st.text_input("Jump to object (API name)", value="")
        with c2:
            child_id = st.text_input("Jump to record Id", value="")

        if st.button("Go"):
            if child_api.strip() and child_id.strip():
                push(child_api.strip(), child_id.strip(), label=child_id.strip())
                st.rerun()

    with tabs[2]:
        if not export_root:
            st.error("Could not infer export_root from db_path; previews need export_root.")
            return

        df = load_master_documents_index(export_root)
        if df is None or df.empty:
            st.warning("No master_documents_index.csv found or it is empty.")
            return

        # Filter docs linked to this record
        docs = df[(df["record_id"] == record_id) & (df["object_type"] == api_name)].copy()
        if docs.empty:
            # fallback: sometimes object_type casing differs
            docs = df[(df["record_id"] == record_id)].copy()

        st.write(f"Documents found: **{len(docs)}**")
        st.dataframe(
            docs[["file_extension", "file_source", "file_name", "object_type", "record_name"]],
            use_container_width=True,
        )

        choices: list[tuple[str, str]] = []
        for _, r in docs.iterrows():
            name = str(r.get("file_name", "") or "").strip()
            obj = str(r.get("object_type", "") or "").strip()
            lp = str(r.get("local_path", "") or "").strip()
            label = f"{name} — {obj}" if name else (lp or "document")
            choices.append((label, lp))

        if not choices:
            st.info("No previewable documents (missing local_path).")
            return

        sel_label = st.selectbox("Preview a document", [c[0] for c in choices], index=0)
        sel_lp = dict(choices).get(sel_label, "")

        if not sel_lp:
            st.warning(
                "Selected document has no local_path. Fix the master_documents_index normalization."
            )
            return

        full_path = resolve_document_path(export_root, sel_lp)
        preview_file(full_path, label=sel_label)
