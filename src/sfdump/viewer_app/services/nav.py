from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import streamlit as st


@dataclass(frozen=True)
class NavTarget:
    api_name: str
    record_id: str
    label: str = ""


_STACK_KEY = "viewer_nav_stack"


def get_current_override() -> Optional[NavTarget]:
    """Return the current navigation target override (top of stack), if any."""
    stack = st.session_state.get(_STACK_KEY, [])
    if not stack:
        return None
    top = stack[-1]
    if isinstance(top, dict):
        return NavTarget(**top)
    if isinstance(top, NavTarget):
        return top
    return None


def push(api_name: str, record_id: str, *, label: str = "") -> None:
    stack = st.session_state.get(_STACK_KEY, [])
    stack.append({"api_name": api_name, "record_id": record_id, "label": label})
    st.session_state[_STACK_KEY] = stack


def pop() -> None:
    stack = st.session_state.get(_STACK_KEY, [])
    if stack:
        stack.pop()
    st.session_state[_STACK_KEY] = stack


def clear() -> None:
    st.session_state[_STACK_KEY] = []


def breadcrumb() -> str:
    stack = st.session_state.get(_STACK_KEY, [])
    if not stack:
        return ""
    parts = []
    for item in stack:
        if isinstance(item, dict):
            api = item.get("api_name", "")
            label = item.get("label") or item.get("record_id") or ""
        else:
            api = getattr(item, "api_name", "")
            label = getattr(item, "label", "") or getattr(item, "record_id", "")
        parts.append(f"{api}:{label}".strip(":"))
    return "  ›  ".join(parts)
