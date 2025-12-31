from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_file
from sfdump.viewer_app.services.paths import resolve_export_path

Pathish = Union[str, Path]


def open_local_file(*args) -> None:
    """
    Open a local file using the OS.

    Backwards-compatible:
      - open_local_file(full_path: Path)
      - open_local_file(export_root: Path, rel_or_abs_path: str)
    """
    if len(args) == 1:
        p = Path(args[0])
    elif len(args) == 2:
        export_root = Path(args[0])
        rel_or_abs_path = str(args[1])
        p = resolve_export_path(export_root, rel_or_abs_path)
    else:
        raise TypeError("open_local_file expects (path) or (export_root, rel_or_abs_path)")

    if not p.exists():
        st.error(f"File not found: {p}")
        return

    try:
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
    except Exception as exc:
        st.error(f"Failed to open file: {exc}")


def preview_file(
    export_root: Path,
    rel_or_abs_path: str,
    *,
    title: Optional[str] = None,
    expanded: bool = True,
    pdf_height: int = 750,
) -> None:
    """
    Inline preview for common file types.

    IMPORTANT UX FIX:
    - Defaults to expanded=True so the user *sees* the preview immediately.
    """
    full_path = resolve_export_path(Path(export_root), rel_or_abs_path)

    header = title or "Preview"
    st.markdown(f"**{header}**")
    st.caption(str(full_path))

    if not full_path.exists():
        st.warning("File not found on disk (not downloaded into the export?).")
        return

    ext = full_path.suffix.lower()

    with st.spinner("Loading preview..."):
        if ext == ".pdf":
            with st.expander("PDF preview", expanded=expanded):
                preview_pdf_file(full_path, height=pdf_height, context=title or "")
            return

        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"):
            with st.expander("Image preview", expanded=expanded):
                st.image(str(full_path))
            return

        # Fallback: show a small text preview if it looks like text
        try:
            data = full_path.read_bytes()
        except Exception as exc:
            st.error(f"Failed to read file: {exc}")
            return

        # Heuristic: if it decodes, show first chunk
        try:
            txt = data.decode("utf-8")
            with st.expander("Text preview", expanded=expanded):
                st.code(txt[:20000])
        except Exception:
            st.info("No inline preview available for this file type.")
