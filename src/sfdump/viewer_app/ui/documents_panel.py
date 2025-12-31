from __future__ import annotations

import csv
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


def _load_master_index_map(export_root: Path) -> dict[tuple[str, str], str]:
    """
    Map (file_source, file_id) -> local_path from meta/master_documents_index.csv.
    Cached in Streamlit session_state for speed.
    """
    key = f"_master_index_map::{str(export_root)}"
    cached = st.session_state.get(key)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    p = export_root / "meta" / "master_documents_index.csv"
    m: dict[tuple[str, str], str] = {}
    if not p.exists():
        st.session_state[key] = m
        return m

    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            src = (row.get("file_source") or "").strip()
            fid = (row.get("file_id") or "").strip()
            lp = (row.get("local_path") or "").strip()
            if src and fid and lp:
                m[(src, fid)] = lp

    st.session_state[key] = m
    return m


def _resolve_rel_path(export_root: Path, row: dict[str, Any]) -> str:
    # 1) Prefer direct fields on the row (DB/index rows)
    for k in ("path", "local_path", "Path", "LocalPath", "rel_path", "relative_path"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 2) Fall back to the master index (best source after backfill)
    src = (row.get("file_source") or row.get("source") or "").strip()
    fid = (row.get("file_id") or row.get("Id") or "").strip()
    if src and fid:
        m = _load_master_index_map(export_root)
        return m.get((src, fid), "")

    return ""


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

    # Build UNIQUE labels and map them to rows (avoid dict-key collisions)
    labels: list[str] = []
    label_to_row: dict[str, dict[str, Any]] = {}

    for i, r in enumerate(docs):
        lab = _doc_label(r)
        if not lab.strip():
            continue
        lab_u = f"{i + 1:03d} — {lab}"  # prefix ensures uniqueness
        labels.append(lab_u)
        label_to_row[lab_u] = r

    if not labels:
        st.info("Documents found but none have usable labels/paths.")
        return

    sel_label = st.selectbox(
        "Preview Doc",
        labels,
        key=f"preview_doc_{object_type}_{record_id}",
    )

    row = label_to_row[sel_label]

    rel_path = _resolve_rel_path(export_root, row)
    if not rel_path:
        st.warning("Selected document has no path in index (and no master index match).")
        with st.expander("Debug: selected row"):
            st.json(row)
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
