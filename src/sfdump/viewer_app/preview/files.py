from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_file
from sfdump.viewer_app.services.paths import resolve_export_path


def open_local_file(path: Path) -> None:
    """Open a file using the OS default application."""
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
        st.error(f"Failed to open locally: {exc}")


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def preview_file(
    export_root: Path,
    rel_or_abs_path: str,
    *,
    height: int = 900,
    label: Optional[str] = None,
) -> None:
    """
    Render an inline preview (PDF/images/text) plus Open/Download controls.

    NOTE:
    - export_root is the export root (folder containing meta/, files_legacy/, etc.)
    - rel_or_abs_path can be relative (to export_root) or absolute.
    """
    p = resolve_export_path(export_root, rel_or_abs_path)

    if label:
        st.caption(label)

    st.caption(str(p))

    if not p.exists():
        st.error(f"File not found on disk: {p}")
        return

    mime = _guess_mime(p)
    ext = p.suffix.lower()

    cols = st.columns([1, 1, 4])
    with cols[0]:
        if st.button("Open", key=f"open_{p}"):
            open_local_file(p)
    with cols[1]:
        try:
            data = p.read_bytes()
        except Exception as exc:
            st.error(f"Failed to read file: {exc}")
            return

        st.download_button(
            "Download",
            data=data,
            file_name=p.name,
            mime=mime,
            key=f"dl_{p}",
        )

    # Inline preview section (separate from buttons for reliable reruns)
    with st.spinner("Rendering preview…"):
        if ext == ".pdf" or mime == "application/pdf":
            with st.expander("Preview", expanded=True):
                preview_pdf_file(p, height=height)
            return

        if mime.startswith("image/"):
            with st.expander("Preview", expanded=True):
                st.image(str(p), caption=p.name)
            return

        if mime.startswith("text/") or ext in {".txt", ".md", ".rst", ".csv", ".log"}:
            with st.expander("Preview", expanded=True):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    # fallback
                    text = (p.read_bytes()[:200_000]).decode("utf-8", errors="replace")
                # Avoid dumping enormous files into the UI
                if len(text) > 200_000:
                    st.info("Showing first 200k characters.")
                    text = text[:200_000]
                st.code(text)
            return

    st.info("No inline preview available for this file type. Use Open or Download.")
