from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from sfdump.viewer_app.preview.files import open_local_file, preview_file
from sfdump.viewer_app.services.documents import list_record_documents
from sfdump.viewer_app.services.paths import infer_export_root


def _doc_label(row: dict[str, Any]) -> str:
    # Prefer friendly names if present, fall back to path basename
    name = (row.get("file_name") or row.get("title") or "").strip()
    path = (row.get("path") or row.get("local_path") or "").strip()
    if not name and path:
        name = Path(path.replace("\\", "/")).name
    src = (row.get("file_source") or row.get("source") or "").strip()
    if src:
        return f"{name} — {src}" if name else src
    return name or "(unnamed document)"


def render_documents_panel(*, db_path: Path, object_type: str, record_id: str) -> None:
    docs = list_record_documents(db_path=db_path, object_type=object_type, record_id=record_id)
    if not docs:
        st.info("No documents indexed for this record.")
        return

    export_root = infer_export_root(db_path)
    if export_root is None:
        st.warning(
            "Couldn't infer EXPORT_ROOT from DB path. Expected .../EXPORT_ROOT/meta/sfdata.db"
        )
        st.caption("Preview/open needs EXPORT_ROOT to resolve relative file paths.")
        return

    # Build stable options
    options = {_doc_label(r): r for r in docs}
    labels = [k for k in options.keys() if k.strip()]
    if not labels:
        st.info("Documents found but none have usable labels/paths.")
        return

    sel_label = st.selectbox(
        "Preview Doc",
        labels,
        key=f"preview_doc_{object_type}_{record_id}",
    )
    row = options[sel_label]
    rel_path = (row.get("path") or row.get("local_path") or "").strip()
    if not rel_path:
        st.warning("Selected document has no path in index.")
        return

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        if st.button("Open", key=f"doc_open_{object_type}_{record_id}"):
            open_local_file(export_root, rel_path)
    with c2:
        st.button(
            "Copy path",
            on_click=lambda: st.write(rel_path),
            key=f"doc_copy_{object_type}_{record_id}",
        )

    preview_file(export_root, rel_path, title="Preview", expanded=True, pdf_height=800)
