import os

import requests
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def get_salesforce_token() -> str:
    """Return an access token using the Client Credentials flow, with clear errors."""
    login_url = _require_env("SF_LOGIN_URL")  # e.g. https://yourorg.my.salesforce.com
    client_id = _require_env("SF_CLIENT_ID")  # your Consumer Key
    client_secret = _require_env("SF_CLIENT_SECRET")  # your generated secret

    print("DEBUG URL:", f"{login_url}/services/oauth2/token")
    print(
        "DEBUG DATA:",
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret[:6] + "...",
        },
    )

    resp = requests.post(
        f"{login_url}/services/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    # If Salesforce returns 400, show their JSON error so we know the cause
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = {"raw": resp.text}
        raise RuntimeError(f"Token request failed ({resp.status_code}): {detail}")
    return resp.json()["access_token"]


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
