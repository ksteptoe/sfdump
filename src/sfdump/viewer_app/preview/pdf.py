from __future__ import annotations

import base64
import uuid

import streamlit as st
import streamlit.components.v1 as components


def preview_pdf_bytes(data: bytes, *, height: int = 900, filename: str = "document.pdf") -> None:
    """
    Preview PDF bytes in the Streamlit app.

    Some browsers refuse to render PDFs inside iframes when src is a data: URL,
    resulting in a blank white frame. Using a blob: URL is far more reliable.
    """
    if not data:
        st.warning("No PDF data to preview.")
        return

    # Always keep a download fallback
    st.download_button(
        "Download PDF",
        data=data,
        file_name=filename,
        mime="application/pdf",
        key=f"dl_pdf_{uuid.uuid4().hex}",
    )

    # "Open in new tab" fallback via data URL
    b64 = base64.b64encode(data).decode("ascii")
    st.markdown(f"[Open PDF in a new tab](data:application/pdf;base64,{b64})")

    # Inline render via blob URL
    host_id = f"pdf_{uuid.uuid4().hex}"
    components.html(
        f"""
        <div id="{host_id}" style="width: 100%; height: {int(height)}px;"></div>
        <script>
        (function() {{
          const bytes = Uint8Array.from(atob("{b64}"), c => c.charCodeAt(0));
          const blob = new Blob([bytes], {{ type: "application/pdf" }});
          const url = URL.createObjectURL(blob);

          const el = document.getElementById("{host_id}");
          el.innerHTML = `
            <iframe
              src="${{url}}"
              width="100%"
              height="{int(height)}"
              style="border: 1px solid #ddd; border-radius: 6px;"
            ></iframe>
          `;
        }})();
        </script>
        """,
        height=int(height) + 20,
    )
