from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import streamlit as st

from sfdump.utils import find_file_on_disk
from sfdump.viewer_app.preview.files import open_local_file, preview_file
from sfdump.viewer_app.services.documents import list_record_documents
from sfdump.viewer_app.services.paths import infer_export_root


def _as_str(x: Any) -> str:
    return "" if x is None else str(x)


def _doc_label(row: dict[str, Any]) -> str:
    """
    Build a friendly label for a document row.

    Use name/title where possible, otherwise fall back to basename(path).
    Always include the file_id when present to aid uniqueness.
    """
    name = (_as_str(row.get("file_name")) or _as_str(row.get("title"))).strip()
    fid = (_as_str(row.get("file_id")) or _as_str(row.get("Id"))).strip()
    rel_path = (_as_str(row.get("path")) or _as_str(row.get("local_path"))).strip()

    if not name and rel_path:
        name = Path(rel_path.replace("\\", "/")).name

    base = name or "(unnamed document)"
    if fid:
        return f"{base} [{fid}]"
    return base


def _rel_path(row: dict[str, Any]) -> str:
    return (_as_str(row.get("path")) or _as_str(row.get("local_path"))).strip()


def _render_documents_panel_rows(
    *,
    export_root: Path,
    rows: list[dict[str, Any]],
    title: str,
    key_prefix: str,
    pdf_height: int = 800,
) -> None:
    """
    Core renderer from already-available document rows + known export_root.

    This is the reusable bit: no DB assumptions, no duplicate preview logic elsewhere.
    """
    if not rows:
        st.info("No documents indexed for this record.")
        return

    # Build unique labels (avoid collisions and “selectbox does nothing”)
    labels: list[str] = []
    label_to_row: dict[str, dict[str, Any]] = {}

    for i, r in enumerate(rows, start=1):
        lab = _doc_label(r).strip()
        if not lab:
            continue
        # Prefix index makes labels stable+unique even if names repeat
        u = f"{i:03d} — {lab}"
        labels.append(u)
        label_to_row[u] = r

    if not labels:
        st.info("Documents found but none have usable labels.")
        return

    # Show summary of documents with/without local files
    with_path = sum(1 for r in rows if _rel_path(r))
    without_path = len(rows) - with_path
    if without_path > 0:
        st.caption(f"📄 {with_path} downloaded, ⚠️ {without_path} not downloaded")

    sel = st.selectbox(
        "Preview Doc",
        labels,
        key=f"{key_prefix}_select",
    )
    row = label_to_row[sel]
    rel_path = _rel_path(row)

    if not rel_path:
        file_id = row.get("file_id") or row.get("Id") or ""
        file_source = row.get("file_source") or ""
        # Try to find the file on disk (handles chunked-export CSV gaps)
        if file_id and file_source:
            rel_path = find_file_on_disk(export_root, file_id, file_source)

    if not rel_path:
        file_id = row.get("file_id") or row.get("Id") or "(unknown)"
        file_source = row.get("file_source") or "(unknown)"
        st.warning(
            "This file has not been downloaded yet. "
            "Click **Rebuild indexes** to re-scan, or run "
            "`sfdump files` to download missing files."
        )
        if st.button("Rebuild indexes", key=f"{key_prefix}_rebuild"):
            from sfdump.command_check_export import auto_check_and_fix

            with st.spinner("Rebuilding indexes..."):
                auto_check_and_fix(export_root)
            st.success("Indexes rebuilt -- please reload the page.")
            st.rerun()
        with st.expander("Details", expanded=False):
            st.text(f"File ID: {file_id}")
            st.text(f"Source: {file_source}")
        return

    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        if st.button("Open", key=f"{key_prefix}_open"):
            open_local_file(export_root, rel_path)

    with c2:
        # simple + reliable (no clipboard hacks)
        st.code(rel_path, language="text")

    with c3:
        st.caption(str((export_root / rel_path).resolve()))

    # IMPORTANT: pass a title/context so PDF widget keys stay unique per location
    preview_file(
        export_root,
        rel_path,
        title=title,
        expanded=True,
        pdf_height=pdf_height,
    )


def render_documents_panel(
    *,
    db_path: Path,
    object_type: str,
    record_id: str,
    title: str = "Document preview",
    key_prefix: Optional[str] = None,
    pdf_height: int = 800,
) -> None:
    """
    Standard documents panel for a (object_type, record_id) record.
    """
    export_root = infer_export_root(db_path)
    if export_root is None:
        st.warning(
            "Couldn't infer EXPORT_ROOT from DB path. Expected .../EXPORT_ROOT/meta/sfdata.db"
        )
        st.caption("Preview/open needs EXPORT_ROOT to resolve relative file paths.")
        return

    rows = list_record_documents(db_path=db_path, object_type=object_type, record_id=record_id)

    kp = key_prefix or f"docs_{object_type}_{record_id}"
    _render_documents_panel_rows(
        export_root=export_root,
        rows=rows,
        title=title,
        key_prefix=kp,
        pdf_height=pdf_height,
    )


def render_documents_panel_from_rows(
    *,
    export_root: Path,
    rows: Iterable[dict[str, Any]],
    title: str,
    key_prefix: str,
    pdf_height: int = 800,
) -> None:
    """
    Use this when you already have a list of docs (e.g. subtree docs),
    and you just want the standard preview/open behaviour.
    """
    _render_documents_panel_rows(
        export_root=export_root,
        rows=list(rows),
        title=title,
        key_prefix=key_prefix,
        pdf_height=pdf_height,
    )
