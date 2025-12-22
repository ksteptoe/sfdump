from __future__ import annotations

import base64

import streamlit as st


def preview_pdf_bytes(pdf_bytes: bytes, *, height: int = 750) -> None:
    """
    Render a PDF inline in Streamlit using a Blob URL.

    Avoids Chrome blocking data:application/pdf;base64,... in iframes,
    and avoids requiring internet access (unlike PDF.js CDN).
    """
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    html = f"""
    <iframe id="pdf_frame" style="width:100%; height:{height}px; border:none;"></iframe>
    <script>
      (function() {{
        const b64 = "{b64}";
        const binary = atob(b64);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {{
          bytes[i] = binary.charCodeAt(i);
        }}
        const blob = new Blob([bytes], {{ type: "application/pdf" }});
        const url = URL.createObjectURL(blob);
        document.getElementById("pdf_frame").src = url;
      }})();
    </script>
    """
    st.components.v1.html(html, height=height, scrolling=True)
