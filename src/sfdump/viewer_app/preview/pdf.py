from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components

# Data-URL embedding can silently fail for large files in some browsers.
# Keep this conservative; you can bump later if it works well for you.
_MAX_INLINE_BYTES = 6_000_000  # ~6 MB


def preview_pdf_bytes(data: bytes, *, height: int = 900) -> None:
    """
    Inline PDF preview.

    Strategy:
      - Always provide a download button.
      - For "small enough" PDFs, embed via iframe(data: URL) + provide an "Open in tab" link.
      - For large PDFs, skip inline (common to show a blank/white frame) and tell the user.
    """
    if not data:
        st.warning("No PDF data to preview.")
        return

    # Always provide a reliable fallback
    st.download_button(
        "Download PDF",
        data=data,
        file_name="document.pdf",
        mime="application/pdf",
        key=f"download_pdf_{len(data)}",
    )

    if len(data) > _MAX_INLINE_BYTES:
        st.info(
            f"PDF is {len(data)/1_000_000:.1f}MB; skipping inline preview (often fails/blank in browsers). "
            "Use Download/Open locally."
        )
        return

    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:application/pdf;base64,{b64}"

    # 1) Try Streamlit's iframe helper (often more reliable)
    try:
        components.iframe(data_url, height=int(height), scrolling=True)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Inline iframe preview failed: {exc}")

    # 2) Offer "open in browser tab" – sometimes works even when iframe is blank
    st.markdown(f"[Open PDF in a new tab]({data_url})")
