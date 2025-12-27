from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from sfdump.viewer_app.preview.pdf import preview_pdf_bytes


def open_local_file(path: Path) -> None:
    """Open a file on the machine running Streamlit."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def preview_file(export_root: Path, local_path: str) -> None:
    """
    Preview PDFs inline (best-effort); ALWAYS provide Download/Open fallbacks.

    local_path should be relative to export_root, e.g. files/... or files_legacy/...
    Absolute paths are also tolerated.
    """
    raw = (local_path or "").strip()
    disp = raw.replace("\\", "/")

    p = Path(disp)
    if not p.is_absolute():
        p = export_root / p

    try:
        p = p.resolve()
    except Exception:
        # resolve() can fail on odd paths; still try the raw join
        pass

    if not p.exists():
        st.error(f"File not found on disk: `{p}`")
        return

    try:
        size = p.stat().st_size
    except Exception:
        size = None

    if size is not None:
        st.caption(f"File: `{disp}`  •  {size:,} bytes")
    else:
        st.caption(f"File: `{disp}`")

    col_a, col_b, _ = st.columns([1, 1, 2])

    # Always: download
    with col_a:
        st.download_button(
            "Download",
            data=p.read_bytes(),
            file_name=p.name,
            key=f"dl_{p.name}_{size or 0}",
        )

    # Always: open locally (helps when inline PDF fails)
    with col_b:
        if st.button("Open locally", key=f"open_{p.name}_{size or 0}"):
            open_local_file(p)

    # Best-effort inline PDF preview
    if p.suffix.lower() == ".pdf":
        try:
            preview_pdf_bytes(p.read_bytes(), height=900)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Inline PDF preview failed: {exc}")
