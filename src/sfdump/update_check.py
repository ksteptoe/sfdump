from __future__ import annotations

import re

import requests

from . import __version__

PYPI_URL = "https://pypi.org/pypi/sfdump/json"


def _parse_version(v: str) -> tuple[int, ...]:
    """Strip dev/post/local suffixes and return an int tuple for comparison."""
    v = re.split(r"(\.dev|\.post|\+)", v)[0]
    parts: list[int] = []
    for segment in v.lstrip("v").split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            break
    return tuple(parts)


def get_latest_release() -> dict | None:
    """Fetch latest version from PyPI.

    Returns ``{"version": "..."}`` or *None* on any error.
    """
    try:
        resp = requests.get(PYPI_URL, timeout=5)
        resp.raise_for_status()
    except Exception:
        return None

    try:
        data = resp.json()
        version = data["info"]["version"]
    except Exception:
        return None

    return {"version": version}


def is_update_available() -> tuple[bool, str, str]:
    """Check whether a newer release exists on PyPI.

    Returns ``(available, current_version, latest_version)``.
    On network errors returns ``(False, current, "")``.
    """
    current = __version__
    release = get_latest_release()
    if release is None:
        return False, current, ""
    latest = release["version"]
    try:
        available = _parse_version(latest) > _parse_version(current)
    except Exception:
        return False, current, latest
    return available, current, latest
