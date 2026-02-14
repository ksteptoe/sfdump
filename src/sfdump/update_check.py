from __future__ import annotations

import re

import requests

from . import __version__

GITHUB_REPO = "ksteptoe/sfdump"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


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
    """Fetch latest release from GitHub API.

    Returns ``{version, tag, url, asset_url}`` or *None* on any error.
    """
    try:
        resp = requests.get(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=5,
        )
        resp.raise_for_status()
    except Exception:
        return None

    data = resp.json()
    tag: str = data.get("tag_name", "")
    html_url: str = data.get("html_url", "")
    version = tag.lstrip("v")

    # Prefer wheel (version baked in, no build deps) over source ZIP
    asset_url = ""
    for asset in data.get("assets", []):
        name: str = asset.get("name", "")
        if name.endswith(".whl") and "sfdump" in name.lower():
            asset_url = asset.get("browser_download_url", "")
            break
    if not asset_url:
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip") and "sfdump" in name.lower():
                asset_url = asset.get("browser_download_url", "")
                break

    return {"version": version, "tag": tag, "url": html_url, "asset_url": asset_url}


def is_update_available() -> tuple[bool, str, str]:
    """Check whether a newer release exists on GitHub.

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
