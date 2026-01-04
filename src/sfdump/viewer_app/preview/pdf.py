from __future__ import annotations

from pathlib import Path

import streamlit as st


def preview_pdf_file(path: Path, *, height: int = 750, context: str = "") -> None:
    """
    Preview a PDF file from disk in a way that avoids Streamlit widget key collisions.

    `context` should be a short string describing where this preview is shown
    (e.g. "Documents tab", "Subtree preview") so that the same PDF can be rendered
    in multiple UI locations without duplicate widget keys.
    """
    try:
        data = path.read_bytes()
    except Exception as exc:
        st.error(f"Failed to read PDF: {exc}")
        return

    key_suffix = f"{context}::{path}"
    preview_pdf_bytes(data, height=height, key_suffix=key_suffix)


def preview_pdf_bytes(data: bytes, *, height: int = 750, key_suffix: str = "") -> None:
    """
    PDF preview that does NOT depend on the browser PDF plugin.

    - Always offers Download
    - Renders first pages as images via PyMuPDF (fitz)

    key_suffix must be unique per rendered instance to avoid Streamlit key collisions.
    """
    if not data:
        st.info("No PDF data to preview.")
        return

    size_mb = len(data) / (1024 * 1024)
    st.caption(f"PDF size: {size_mb:.2f} MB")

    uniq = abs(hash(key_suffix)) if key_suffix else len(data)

    # Always provide a download (works even if inline preview is blocked)
    st.download_button(
        "Download PDF",
        data=data,
        file_name="document.pdf",
        mime="application/pdf",
        key=f"dl_pdf_{uniq}",
    )

    # Render pages as images (most reliable)
    try:
        import fitz  # type: ignore
    except Exception:
        st.warning("Inline PDF preview requires PyMuPDF. Install with: pip install pymupdf")
        return

    doc = fitz.open(stream=data, filetype="pdf")
    pages = doc.page_count

    # Streamlit slider requires min < max; handle 1-page PDFs
    if pages <= 1:
        max_pages = 1
        st.caption("Previewing 1 page (single-page PDF).")
    else:
        max_pages = st.slider(
            "Preview pages",
            1,
            min(10, pages),
            min(3, pages),
            key=f"pdf_pages_{uniq}",
        )

    zoom = st.select_slider(
        "Zoom",
        options=[1, 1.5, 2, 2.5, 3],
        value=2,
        key=f"pdf_zoom_{uniq}",
    )

    for i in range(max_pages):
        page = doc.load_page(i)
        mat = fitz.Matrix(float(zoom), float(zoom))
        pix = page.get_pixmap(matrix=mat, alpha=False)
        st.image(
            pix.tobytes("png"),
            caption=f"Page {i + 1}/{pages}",
            width="stretch",
        )
