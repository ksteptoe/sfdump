from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from .pdf import render_pdf_path


def open_local_file(path: Path) -> None:
    """
    Best-effort "open in default app".
    Windows: os.startfile
    macOS: open
    Linux: xdg-open
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
    except Exception as e:
        st.error(f"Could not open file: {p}\n\n{e}")


def _render_text_preview(path: Path, *, max_chars: int = 50_000) -> None:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        st.error(f"Failed reading text: {path}\n\n{e}")
        return

    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n…(truncated)…"
    st.code(txt)


def preview_file(path: Path, *, label: str = "", height: int = 900) -> None:
    """
    Render a preview for common file types. Always provides a download fallback.
    """
    p = Path(path)

    if label:
        st.subheader(label)

    if not p.exists():
        st.warning(f"Preview unavailable (missing file): {p}")
        return

    # Always provide "open locally" + download
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Open locally", key=f"open_{p.name}"):
            open_local_file(p)
    with col_b:
        try:
            data = p.read_bytes()
            st.download_button(
                "Download",
                data=data,
                file_name=p.name,
                key=f"dl_{p.name}",
            )
        except Exception:
            # If we can’t read bytes, still allow preview attempts below if possible
            pass

    ext = p.suffix.lower().lstrip(".")

    if ext == "pdf":
        render_pdf_path(p, height=height)
        return

    if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
        st.image(str(p), use_container_width=True)
        return

    if ext in {"txt", "md", "csv", "log", "json", "yaml", "yml"}:
        _render_text_preview(p)
        return

    # Not previewable types (docx/msg/xlsx/etc.)
    st.info(f"No inline preview available for .{ext}. Use **Open locally** or **Download**.")
