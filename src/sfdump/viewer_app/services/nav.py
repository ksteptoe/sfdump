from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import streamlit as st

NAV_STATE_KEY = "sfdump_nav_stack"


@dataclass(frozen=True)
class NavItem:
    api_name: str
    record_id: str
    label: str = ""


def _stack() -> List[NavItem]:
    if NAV_STATE_KEY not in st.session_state:
        st.session_state[NAV_STATE_KEY] = []
    return st.session_state[NAV_STATE_KEY]


def push(api_name: str, record_id: str, *, label: str = "") -> None:
    """Push a record onto the navigation stack."""
    if not api_name or not record_id:
        return
    _stack().append(NavItem(api_name=api_name, record_id=record_id, label=label))


def pop() -> Optional[NavItem]:
    """Pop the current record (if any) and return it."""
    s = _stack()
    if not s:
        return None
    return s.pop()


def clear() -> None:
    """Clear the navigation stack."""
    st.session_state[NAV_STATE_KEY] = []


def current() -> Optional[NavItem]:
    """Return the current record (top of stack) if any."""
    s = _stack()
    return s[-1] if s else None


def breadcrumbs() -> str:
    """Human readable breadcrumb string."""
    s = _stack()
    if not s:
        return ""
    parts = []
    for it in s:
        lab = it.label or it.record_id
        parts.append(f"{it.api_name}:{lab}")
    return "  →  ".join(parts)


def nav_sidebar() -> None:
    """
    Optional: render a sidebar navigation control.
    Doesn't change state automatically (except back/clear buttons).
    """
    st.sidebar.subheader("Navigation")
    bc = breadcrumbs()
    if bc:
        st.sidebar.caption(bc)
    cols = st.sidebar.columns([1, 1])
    with cols[0]:
        if st.button("Back", key="nav_back", disabled=(len(_stack()) <= 1)):
            pop()
            st.rerun()
    with cols[1]:
        if st.button("Clear", key="nav_clear", disabled=(len(_stack()) == 0)):
            clear()
            st.rerun()
