from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .env_loader import load_env_files
from .exceptions import MissingCredentialsError

__author__ = "Kevin Steptoe"
__copyright__ = "Kevin Steptoe"
__license__ = "MIT"

_logger = logging.getLogger(__name__)

# Ensure .env is loaded for library use as well (e.g., scripts importing SalesforceAPI)
load_env_files(quiet=True)


# ----------------------------------------------------------------------
# Configuration dataclass
# ----------------------------------------------------------------------
@dataclass
class SFConfig:
    """Configuration for Salesforce API authentication."""

    # Which auth flow to use – currently we only support client_credentials
    auth_flow: str = "client_credentials"

    # Base login URL (not the instance URL)
    login_url: str = "https://login.salesforce.com"

    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    # Optional: pre-provided token / instance URL (e.g. from cache)
    access_token: Optional[str] = None
    instance_url: Optional[str] = None

    # Optional: override API version (e.g. "v60.0"); otherwise auto-discover
    api_version: Optional[str] = None

    @classmethod
    def from_env(cls) -> SFConfig:
        """Load configuration from environment variables."""
        return cls(
            auth_flow=os.getenv("SF_AUTH_FLOW", "client_credentials"),
            login_url=os.getenv("SF_LOGIN_URL", "https://login.salesforce.com"),
            client_id=os.getenv("SF_CLIENT_ID"),
            client_secret=os.getenv("SF_CLIENT_SECRET"),
            access_token=os.getenv("SF_ACCESS_TOKEN"),
            instance_url=os.getenv("SF_INSTANCE_URL"),
            api_version=os.getenv("SF_API_VERSION"),
        )


# ----------------------------------------------------------------------
# Main API client
# ----------------------------------------------------------------------
class SalesforceAPI:
    """Minimal Salesforce REST API client using OAuth client-credentials."""

    def __init__(self, cfg: Optional[SFConfig] = None) -> None:
        self.cfg = cfg or SFConfig.from_env()
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.instance_url: Optional[str] = None
        self.api_version: Optional[str] = None

    # --------------------------- Public methods -----------------------

    def connect(self) -> None:
        """Authenticate using either an existing token or configured auth flow."""
        if self.cfg.access_token and self.cfg.instance_url:
            _logger.debug("Using existing access token from configuration.")
            self.access_token = self.cfg.access_token
            self.instance_url = self.cfg.instance_url.rstrip("/")
        else:
            _logger.info("Performing OAuth login using auth flow: %s", self.cfg.auth_flow)
            self._login_via_auth_flow()

        if not self.access_token or not self.instance_url:
            raise RuntimeError("Authentication did not yield access_token and instance_url.")

        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        self.api_version = self.cfg.api_version or self._discover_latest_api_version()
        _logger.info(
            "Connected to Salesforce instance=%s api=%s",
            self.instance_url,
            self.api_version,
        )

    def whoami(self) -> Dict[str, Any]:
        """Return identity information for the current user."""
        url = f"{self.cfg.login_url.rstrip('/')}/services/oauth2/userinfo"
        return self._get(url).json()

    def limits(self) -> Dict[str, Any]:
        """Return API usage limits."""
        url = f"{self.instance_url}/services/data/{self.api_version}/limits"
        return self._get(url).json()

    def query(self, soql: str) -> Dict[str, Any]:
        """Run a SOQL query."""
        url = f"{self.instance_url}/services/data/{self.api_version}/query"
        return self._get(url, params={"q": soql}).json()

    # --------------------------- Internal helpers --------------------

    def _login_via_auth_flow(self) -> None:
        """Dispatch to the configured auth flow."""
        if self.cfg.auth_flow == "client_credentials":
            self._client_credentials_login()
        else:
            raise RuntimeError(f"Unsupported SF_AUTH_FLOW: {self.cfg.auth_flow!r}")

    def _client_credentials_login(self) -> None:
        """Perform OAuth2 client credentials flow."""
        missing = [
            k
            for k, v in {
                "SF_CLIENT_ID": self.cfg.client_id,
                "SF_CLIENT_SECRET": self.cfg.client_secret,
                "SF_LOGIN_URL": self.cfg.login_url,
            }.items()
            if not v
        ]
        if missing:
            raise MissingCredentialsError(missing)

        token_url = f"{self.cfg.login_url.rstrip('/')}/services/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.cfg.client_id,
            "client_secret": self.cfg.client_secret,
        }

        _logger.debug("Requesting access token from %s", token_url)
        r = self._post(token_url, data=data, auth_required=False)
        payload = r.json()

        # Expect standard Salesforce fields
        self.access_token = payload["access_token"]
        self.instance_url = payload["instance_url"].rstrip("/")

    def _discover_latest_api_version(self) -> str:
        """Find the latest available API version."""
        url = f"{self.instance_url}/services/data/"
        r = self._get(url)
        versions = r.json()
        best = sorted(versions, key=lambda v: float(v.get("version", "0")), reverse=True)[0]
        version_str = best.get("url", "").split("/")[-1]
        _logger.debug("Latest API version discovered: %s", version_str)
        return version_str

    # --------------------------- HTTP wrappers -----------------------

    def _get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ) -> requests.Response:
        return self._request("GET", url, params=params, auth_required=auth_required)

    def _post(
        self,
        url: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ) -> requests.Response:
        return self._request("POST", url, data=data, auth_required=auth_required)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
        retries: int = 3,
        backoff: float = 0.8,
        timeout: float = 30.0,
    ) -> requests.Response:
        """Generic request with retry and logging."""
        headers: Dict[str, str] = {}
        if auth_required and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        for attempt in range(1, retries + 1):
            try:
                r = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.RequestException as e:
                _logger.warning("Request error (attempt %d/%d): %s", attempt, retries, e)
                if attempt == retries:
                    raise
                time.sleep(backoff * attempt)
                continue

            if r.status_code < 400:
                return r

            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                _logger.warning("HTTP %s -> retrying %d/%d", r.status_code, attempt, retries)
                time.sleep(backoff * attempt)
                continue

            try:
                detail = r.json()
            except Exception:
                detail = r.text
            _logger.error("HTTP %s error for %s: %s", r.status_code, url, detail)
            r.raise_for_status()
        raise RuntimeError("Exceeded maximum retries.")

    # --- Convenience for discovery & paging ---

    def describe_global(self) -> dict:
        """Return /sobjects (global describe)."""
        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects"
        return self._get(url).json()

    def describe_object(self, name: str) -> dict:
        """Return /sobjects/{name}/describe."""
        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/{name}/describe"
        return self._get(url).json()

    def query_all_iter(self, soql: str):
        """Yield records across pages via nextRecordsUrl."""
        url = f"{self.instance_url}/services/data/{self.api_version}/query"
        res = self._get(url, params={"q": soql}).json()
        for r in res.get("records", []):
            yield r
        next_url = res.get("nextRecordsUrl")
        while next_url:
            res = self._get(f"{self.instance_url}{next_url}").json()
            for r in res.get("records", []):
                yield r
            next_url = res.get("nextRecordsUrl")


# ----------------------------------------------------------------------
# CLI integration shim
# ----------------------------------------------------------------------
def sfdump_api(loglevel: int) -> None:
    """Entry point called from CLI (for now performs connection test)."""
    logging.getLogger().setLevel(loglevel or logging.INFO)
    _logger.info("Starting Salesforce API connection test")

    api = SalesforceAPI(SFConfig.from_env())
    api.connect()
    info = api.whoami()

    _logger.info("Connected as: %s", info.get("email") or info.get("preferred_username"))
    limits = api.limits()
    core = limits.get("DailyApiRequests", {})
    _logger.info(
        "Daily API requests: %s used / %s remaining",
        core.get("Max"),
        core.get("Remaining"),
    )

    print("✅ Salesforce API connection successful")
