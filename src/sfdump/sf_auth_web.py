"""Web Server OAuth flow with PKCE for Salesforce.

This flow opens a browser for interactive login, capturing the authorization code
via a local HTTP server. It produces a token tied to a real user session, which is
required for operations like rendering Visualforce pages (invoice PDFs).

Token is stored separately from the client_credentials token so both flows can
coexist.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

CALLBACK_PORT = 8439
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
TOKEN_FILE = Path.home() / ".sfdump_web_token.json"


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _generate_code_verifier() -> str:
    """Generate a 128-character URL-safe code verifier."""
    return secrets.token_urlsafe(96)


def _generate_code_challenge(verifier: str) -> str:
    """SHA256 hash of verifier, base64url-encoded (no padding)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------


def _load_cached_token() -> dict | None:
    """Return cached token data if access_token is still valid, else None."""
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            if data.get("expires_at", 0) > time.time():
                return data
        except Exception:
            pass
    return None


def _save_token(data: dict, expires_in: int) -> None:
    """Save token data with expiry timestamp."""
    data["expires_at"] = time.time() + expires_in - 60  # 1 min safety margin
    TOKEN_FILE.write_text(json.dumps(data, indent=2))


def load_refresh_token() -> str | None:
    """Return the stored refresh token, if any."""
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            return data.get("refresh_token")
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def _refresh_access_token(refresh_token: str) -> dict:
    """Use refresh_token to get a new access_token."""
    login_url = _require_env("SF_LOGIN_URL")
    client_id = _require_env("SF_CLIENT_ID")
    client_secret = _require_env("SF_CLIENT_SECRET")

    resp = requests.post(
        f"{login_url}/services/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Token refresh failed ({resp.status_code}): {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the authorization code from the OAuth callback."""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        if "error" in params:
            _CallbackHandler.error = params["error"][0]
            body = (
                f"<h2>Authorization failed</h2><p>{params['error'][0]}: "
                f"{params.get('error_description', [''])[0]}</p>"
                "<p>You can close this tab.</p>"
            )
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())
            return

        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            body = (
                "<h2>Login successful!</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())
            return

        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Missing authorization code</h2>")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default HTTP server logging."""


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def get_web_token(*, force_login: bool = False) -> str:
    """Return an access token from the Web Server flow.

    Uses cached token if valid, refreshes if possible, otherwise requires
    interactive login (force_login=True or no cached tokens).
    """
    if not force_login:
        # Try cached access token
        cached = _load_cached_token()
        if cached:
            return cached["access_token"]

        # Try refresh
        refresh_token = load_refresh_token()
        if refresh_token:
            try:
                data = _refresh_access_token(refresh_token)
                expires_in = int(data.get("expires_in", 7200))
                # Preserve existing refresh_token if not returned
                if "refresh_token" not in data:
                    data["refresh_token"] = refresh_token
                _save_token(data, expires_in)
                return data["access_token"]
            except RuntimeError:
                pass  # Refresh token expired, need interactive login

    return interactive_login()


def interactive_login() -> str:
    """Run the full interactive Web Server OAuth flow with PKCE.

    Opens a browser, waits for callback, exchanges code for tokens.
    Returns the access_token.
    """
    login_url = _require_env("SF_LOGIN_URL")
    client_id = _require_env("SF_CLIENT_ID")
    client_secret = _require_env("SF_CLIENT_SECRET")

    # Generate PKCE values
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)

    # Reset handler state
    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    # Start local server
    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # Build authorization URL
        auth_params = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT_URI,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        auth_url = f"{login_url}/services/oauth2/authorize?{auth_params}"

        # Open browser
        webbrowser.open(auth_url)

        # Wait for callback (timeout after 120 seconds)
        deadline = time.time() + 120
        while _CallbackHandler.auth_code is None and _CallbackHandler.error is None:
            if time.time() > deadline:
                raise RuntimeError("Login timed out after 120 seconds")
            time.sleep(0.2)

        if _CallbackHandler.error:
            raise RuntimeError(f"Authorization failed: {_CallbackHandler.error}")

        auth_code = _CallbackHandler.auth_code
    finally:
        server.shutdown()

    # Exchange authorization code for tokens
    resp = requests.post(
        f"{login_url}/services/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    expires_in = int(data.get("expires_in", 7200))
    _save_token(data, expires_in)

    return data["access_token"]
