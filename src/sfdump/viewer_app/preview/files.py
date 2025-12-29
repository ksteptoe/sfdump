from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_bytes
from sfdump.viewer_app.services.paths import resolve_export_path


def open_local_file(path: Path) -> None:
    """Open a local file using the OS default application."""
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:  # pragma: no cover
        st.warning(f"Failed to open file: {exc}")


def preview_file(export_root: Path, local_path: str) -> None:
    """
    Preview a file referenced by a relative path inside an export root.
    PDFs are rendered inline; others offer download + open.
    """
    p = resolve_export_path(export_root, local_path)
    if not p.exists():
        st.warning(f"File not found: {p}")
        return

    ext = p.suffix.lower().lstrip(".")
    st.subheader("Preview")
    st.caption(str(p))

    if ext == "pdf":
        preview_pdf_bytes(p.read_bytes())
        return

    # Generic download + open
    with open(p, "rb") as f:
        st.download_button(
            "Download",
            data=f,
            file_name=p.name,
            use_container_width=True,
        )

    if st.button("Open locally", use_container_width=True):
        open_local_file(p)
