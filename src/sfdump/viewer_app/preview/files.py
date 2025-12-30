from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_file
from sfdump.viewer_app.services.paths import resolve_export_path


def open_local_file(path: Path) -> None:
    """
    Open a file using the OS default application.
    """
    p = Path(path)
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


def preview_file(export_root: Path, rel_or_abs_path: str, *, height: int = 750) -> None:
    """
    Inline preview for common file types (PDF, images). Always renders:
      - resolved path
      - errors if missing
      - preview if supported
    """
    export_root = Path(export_root)
    full_path = resolve_export_path(export_root, rel_or_abs_path)

    st.caption(f"Preview target: `{full_path}`")

    if not full_path.exists():
        st.warning("File does not exist on disk (path above).")
        return

    ext = full_path.suffix.lower()

    with st.spinner("Loading preview…"):
        try:
            if ext == ".pdf":
                preview_pdf_file(full_path, height=height)
                return

            # images
            if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                st.image(str(full_path), use_container_width=True)
                return

            # fallback
            st.info(
                "No inline preview for this file type. Use **Open** or **Download** in the Documents tab."
            )
        except Exception as exc:
            st.error(f"Preview failed: {exc}")
