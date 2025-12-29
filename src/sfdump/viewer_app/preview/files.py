from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_bytes


def open_local_file(path: Path) -> None:
    """Open a file on the machine running Streamlit."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def preview_file(export_root: Path, local_path: str) -> None:
    """
    Preview PDFs inline; otherwise offer a download button.

    local_path must be relative to export_root, e.g. files/... or files_legacy/...
    """
    # Accept accidental absolute paths but prefer relative-to-export-root.
    p = Path(local_path)
    if not p.is_absolute():
        p = (export_root / local_path).resolve()

    if not p.exists():
        st.error(f"File not found: {p}")
        return

    # Convenient "open locally" for desktop usage (optional)
    cols = st.columns([1, 1, 6])
    with cols[0]:
        if st.button("Open locally", key=f"open_local_{p.as_posix()}"):
            open_local_file(p)
    with cols[1]:
        st.download_button(
            "Download",
            data=p.read_bytes(),
            file_name=p.name,
            key=f"download_{p.as_posix()}",
        )

    # Inline PDF preview
    if p.suffix.lower() == ".pdf":
        data = p.read_bytes()
        preview_pdf_bytes(data, height=900, filename=p.name)
        return

    st.info("Inline preview is available for PDFs. Use Download/Open for other file types.")
