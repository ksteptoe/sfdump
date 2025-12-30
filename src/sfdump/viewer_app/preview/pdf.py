from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


def preview_pdf_bytes(data: bytes, *, height: int = 900) -> None:
    """
    Inline PDF preview using an <iframe> with base64 data URI.
    """
    if not data:
        st.info("Empty PDF.")
        return

    b64 = base64.b64encode(data).decode("ascii")
    html = f"""
    <iframe
        src="data:application/pdf;base64,{b64}"
        width="100%"
        height="{int(height)}"
        style="border: none;"
    ></iframe>
    """
    components.html(html, height=int(height) + 20, scrolling=True)


def preview_pdf_file(path: Path, *, height: int = 900) -> None:
    """
    Convenience wrapper: read bytes then call preview_pdf_bytes().
    """
    p = Path(path)
    if not p.exists():
        st.error(f"PDF not found: {p}")
        return

    try:
        data = p.read_bytes()
    except Exception as exc:
        st.error(f"Failed to read PDF: {exc}")
        return

    preview_pdf_bytes(data, height=height)
