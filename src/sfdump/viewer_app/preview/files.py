from __future__ import annotations

import email
import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_file
from sfdump.viewer_app.services.paths import resolve_export_path

Pathish = Union[str, Path]


def open_local_file(*args) -> None:
    """
    Open a local file using the OS.

    Backwards-compatible:
      - open_local_file(full_path: Path)
      - open_local_file(export_root: Path, rel_or_abs_path: str)
    """
    if len(args) == 1:
        p = Path(args[0])
    elif len(args) == 2:
        export_root = Path(args[0])
        rel_or_abs_path = str(args[1])
        p = resolve_export_path(export_root, rel_or_abs_path)
    else:
        raise TypeError("open_local_file expects (path) or (export_root, rel_or_abs_path)")

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
        st.error(f"Failed to open file: {exc}")


def preview_file(
    export_root: Path,
    rel_or_abs_path: str,
    *,
    title: Optional[str] = None,
    expanded: bool = True,
    pdf_height: int = 750,
) -> None:
    """
    Inline preview for common file types.

    IMPORTANT UX FIX:
    - Defaults to expanded=True so the user *sees* the preview immediately.
    """
    full_path = resolve_export_path(Path(export_root), rel_or_abs_path)

    header = title or "Preview"
    st.markdown(f"**{header}**")
    st.caption(str(full_path))

    if not full_path.exists():
        st.warning("File not found on disk (not downloaded into the export?).")
        return

    ext = full_path.suffix.lower()

    with st.spinner("Loading preview..."):
        if ext == ".pdf":
            with st.expander("PDF preview", expanded=expanded):
                preview_pdf_file(full_path, height=pdf_height, context=title or "")
            return

        if ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".bmp",
            ".tif",
            ".tiff",
            ".jfif",
        ):
            with st.expander("Image preview", expanded=expanded):
                st.image(str(full_path))
            return

        # Read file data for preview/download
        try:
            data = full_path.read_bytes()
        except Exception as exc:
            st.error(f"Failed to read file: {exc}")
            return

        # Excel spreadsheets — render as table
        if ext in (".xlsx", ".xls", ".xltx", ".xlsm"):
            _preview_excel(full_path, data, expanded=expanded, context=title or "")
            return

        # CSV/TSV — render as table
        if ext in (".csv", ".tsv"):
            _preview_csv(full_path, data, expanded=expanded, context=title or "")
            return

        # HTML/HTM — render source
        if ext in (".html", ".htm", ".mht"):
            _preview_html(full_path, data, expanded=expanded, context=title or "")
            return

        # Email messages (.eml) — parse headers + body
        if ext == ".eml":
            _preview_eml(full_path, data, expanded=expanded, context=title or "")
            return

        # Text files — show first chunk
        try:
            txt = data.decode("utf-8")
            with st.expander("Text preview", expanded=expanded):
                st.code(txt[:20000])
            return
        except Exception:
            pass

        # Binary files with no inline preview — always offer download
        _download_button(full_path, data, context=title or "")


def _download_button(full_path: Path, data: bytes, *, context: str = "") -> None:
    """Render a download button for any file."""
    mime, _ = mimetypes.guess_type(full_path.name)
    mime = mime or "application/octet-stream"
    size_mb = len(data) / (1024 * 1024)
    uniq = abs(hash(f"{context}::{full_path}"))

    st.caption(f"File size: {size_mb:.2f} MB")
    st.download_button(
        f"Download {full_path.suffix.upper().lstrip('.')} file",
        data=data,
        file_name=full_path.name,
        mime=mime,
        key=f"dl_file_{uniq}",
    )


def _preview_excel(
    full_path: Path, data: bytes, *, expanded: bool = True, context: str = ""
) -> None:
    """Preview an Excel file as a table, with download fallback."""
    _download_button(full_path, data, context=context)

    try:
        import pandas as pd

        dfs = pd.read_excel(full_path, sheet_name=None, engine=None)
    except ImportError:
        st.info("Install openpyxl for Excel preview: `pip install openpyxl`")
        return
    except Exception as exc:
        st.info(f"Could not parse spreadsheet: {exc}")
        return

    for sheet_name, df in dfs.items():
        label = f"Sheet: {sheet_name}" if len(dfs) > 1 else "Spreadsheet preview"
        with st.expander(label, expanded=expanded):
            st.dataframe(df, use_container_width=True)


def _preview_csv(full_path: Path, data: bytes, *, expanded: bool = True, context: str = "") -> None:
    """Preview a CSV/TSV file as a table, with download fallback."""
    _download_button(full_path, data, context=context)

    try:
        import pandas as pd

        sep = "\t" if full_path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(full_path, sep=sep, nrows=2000)
    except Exception as exc:
        st.info(f"Could not parse CSV: {exc}")
        return

    with st.expander("Table preview", expanded=expanded):
        st.dataframe(df, use_container_width=True)


def _preview_html(
    full_path: Path, data: bytes, *, expanded: bool = True, context: str = ""
) -> None:
    """Preview an HTML file: download + source view."""
    _download_button(full_path, data, context=context)

    for encoding in ("utf-8", "latin-1"):
        try:
            txt = data.decode(encoding)
            break
        except Exception:
            continue
    else:
        st.info("Could not decode HTML file.")
        return

    with st.expander("HTML source", expanded=expanded):
        st.code(txt[:30000], language="html")


def _preview_eml(full_path: Path, data: bytes, *, expanded: bool = True, context: str = "") -> None:
    """Preview an .eml email: download + parsed headers and body."""
    _download_button(full_path, data, context=context)

    try:
        msg = email.message_from_bytes(data)
    except Exception as exc:
        st.info(f"Could not parse email: {exc}")
        return

    with st.expander("Email preview", expanded=expanded):
        for hdr in ("From", "To", "Cc", "Date", "Subject"):
            val = msg.get(hdr)
            if val:
                st.markdown(f"**{hdr}:** {val}")

        st.divider()

        body = _extract_email_body(msg)
        if body:
            st.text(body[:20000])
        else:
            st.info("(no text body found)")


def _extract_email_body(msg: email.message.Message) -> str | None:
    """Walk a MIME message and return the first text/plain part."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset)
                    except Exception:
                        return payload.decode("latin-1", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset)
            except Exception:
                return payload.decode("latin-1", errors="replace")
    return None
