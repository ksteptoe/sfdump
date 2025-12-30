from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components


def preview_pdf_bytes(data: bytes, *, height: int = 750) -> None:
    """
    Inline PDF preview using an iframe + base64 data URL.
    """
    if not data:
        st.info("No PDF data to preview.")
        return

    b64 = base64.b64encode(data).decode("ascii")
    html = f"""
    <iframe
      src="data:application/pdf;base64,{b64}"
      width="100%"
      height="{int(height)}"
      style="border: 1px solid #ddd; border-radius: 6px;"
    ></iframe>
    """
    components.html(html, height=int(height) + 10, scrolling=True)


def preview_pdf_file(path, *, height: int = 750) -> None:
    p = str(path)
    try:
        data = open(p, "rb").read()
    except Exception as exc:
        st.error(f"Failed to read PDF: {p} ({exc})")
        return
    preview_pdf_bytes(data, height=height)
