from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import streamlit as st

_NAV_KEY = "_sfdump_nav_stack"


@dataclass(frozen=True)
class NavItem:
    api_name: str
    record_id: str
    label: str = ""


def _stack() -> list[NavItem]:
    if _NAV_KEY not in st.session_state:
        st.session_state[_NAV_KEY] = []
    return st.session_state[_NAV_KEY]


def reset() -> None:
    st.session_state[_NAV_KEY] = []


def set_stack(items: list[NavItem]) -> None:
    st.session_state[_NAV_KEY] = list(items)


def push(api_name: str, record_id: str, label: Optional[str] = None) -> None:
    s = _stack()
    s.append(NavItem(api_name=api_name, record_id=record_id, label=label or ""))


def pop() -> Optional[NavItem]:
    s = _stack()
    if not s:
        return None
    return s.pop()


def peek() -> Optional[NavItem]:
    s = _stack()
    return s[-1] if s else None


def breadcrumbs(max_items: int = 6) -> list[NavItem]:
    s = _stack()
    if len(s) <= max_items:
        return s[:]
    return s[-max_items:]
