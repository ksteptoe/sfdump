from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import streamlit as st


@dataclass(frozen=True)
class NavFrame:
    view: str
    params: Dict[str, Any]
    title: str


_STACK_KEY = "_sfdump_nav_stack_v1"


def nav_init(*, start_view: str = "home", start_title: str = "Home") -> None:
    if _STACK_KEY not in st.session_state:
        st.session_state[_STACK_KEY] = [NavFrame(start_view, {}, start_title)]


def nav_stack() -> List[NavFrame]:
    return list(st.session_state.get(_STACK_KEY, []))


def nav_current() -> NavFrame:
    stack = st.session_state.get(_STACK_KEY)
    if not stack:
        nav_init()
        stack = st.session_state[_STACK_KEY]
    return stack[-1]


def nav_push(view: str, *, title: str, **params: Any) -> None:
    stack = st.session_state.get(_STACK_KEY)
    if not stack:
        nav_init()
        stack = st.session_state[_STACK_KEY]
    stack.append(NavFrame(view=view, params=dict(params), title=title))


def nav_pop() -> None:
    stack = st.session_state.get(_STACK_KEY)
    if not stack:
        nav_init()
        stack = st.session_state[_STACK_KEY]
    if len(stack) > 1:
        stack.pop()


def nav_back_button(*, label: str = "← Back") -> None:
    stack = st.session_state.get(_STACK_KEY, [])
    if len(stack) <= 1:
        return
    if st.button(label, use_container_width=False):
        nav_pop()
        st.rerun()


def nav_open_button(
    *,
    label: str,
    view: str,
    title: str,
    key: str,
    disabled: bool = False,
    **params: Any,
) -> None:
    if st.button(label, key=key, disabled=disabled, use_container_width=False):
        nav_push(view, title=title, **params)
        st.rerun()


def nav_breadcrumb() -> str:
    stack = st.session_state.get(_STACK_KEY, [])
    if not stack:
        return ""
    return " / ".join(f.title for f in stack)
