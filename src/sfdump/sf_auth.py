import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


CACHE_FILE = Path.home() / ".sfdump_token.json"


def _load_cached_token() -> str | None:
    """Return cached token if still valid, else None."""
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            if data["expires_at"] > time.time():
                return data["access_token"]
        except Exception:
            pass
    return None


def _save_cached_token(token: str, expires_in: int) -> None:
    """Save token and expiry timestamp to disk."""
    CACHE_FILE.write_text(
        json.dumps(
            {
                "access_token": token,
                "expires_at": time.time() + expires_in - 60,  # 1 min safety margin
            }
        )
    )


def get_salesforce_token() -> str:
    """Return an access token using Client Credentials flow, cached locally."""
    # Check cache first
    cached = _load_cached_token()
    if cached:
        return cached

    login_url = _require_env("SF_LOGIN_URL")
    client_id = _require_env("SF_CLIENT_ID")
    client_secret = _require_env("SF_CLIENT_SECRET")

    resp = requests.post(
        f"{login_url}/services/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Token request failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    _save_cached_token(token, expires_in)
    return token


def run_salesforce_query(soql: str) -> dict:
    from urllib.parse import quote

    access_token = get_salesforce_token()
    login_url = _require_env("SF_LOGIN_URL")
    api_version = os.getenv("SF_API_VERSION", "v60.0")
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{login_url}/services/data/{api_version}/query?q={quote(soql)}"
    r = requests.get(url, headers=headers)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text}
        raise RuntimeError(f"Query failed ({r.status_code}): {detail}")
    return r.json()
