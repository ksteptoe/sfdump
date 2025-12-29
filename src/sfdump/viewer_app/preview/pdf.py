from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


def preview_pdf_bytes(data: bytes, *, height: int = 900) -> None:
    """
    Backwards-compatible name expected by db_app.py.
    Render a PDF in Streamlit using an iframe with a base64 data URI.
    """
    if not data:
        st.info("No PDF data to render.")
        return

    b64 = base64.b64encode(data).decode("ascii")
    html = f"""
    <iframe
        src="data:application/pdf;base64,{b64}"
        width="100%"
        height="{int(height)}"
        style="border: 1px solid #ddd; border-radius: 6px;"
        type="application/pdf"
    ></iframe>
    """
    st.components.v1.html(html, height=int(height) + 20, scrolling=True)


# Newer/clearer alias (keep it)
render_pdf_bytes = preview_pdf_bytes


def render_pdf_path(path: Path, *, height: int = 900) -> None:
    """
    Render a PDF from a local path.
    """
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError:
        st.error(f"PDF not found: {path}")
        return
    except PermissionError as e:
        st.error(f"Permission error reading PDF: {path}\n\n{e}")
        return
    except OSError as e:
        st.error(f"Failed reading PDF: {path}\n\n{e}")
        return

    preview_pdf_bytes(data, height=height)
