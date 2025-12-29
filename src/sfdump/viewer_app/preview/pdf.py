from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components


def preview_pdf_bytes(data: bytes, *, height: int = 800) -> None:
    """
    Inline PDF preview via an iframe using a data: URL.
    Also provides a download button.
    """
    if not data:
        st.info("No PDF data.")
        return

    st.download_button(
        "Download PDF",
        data=data,
        file_name="document.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    b64 = base64.b64encode(data).decode("ascii")
    html = f"""
    <iframe
        src="data:application/pdf;base64,{b64}"
        width="100%"
        height="{height}"
        style="border: 1px solid #ddd; border-radius: 8px;"
    ></iframe>
    """
    components.html(html, height=height + 20, scrolling=True)
