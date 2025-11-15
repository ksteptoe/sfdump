import json
import time

import pytest

import sfdump.sf_auth as sf_auth


class DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text="OK"):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


# ---- _require_env -----------------------------------------------------------


def test_require_env_ok(monkeypatch):
    monkeypatch.setenv("SF_TEST_ENV", "value")
    assert sf_auth._require_env("SF_TEST_ENV") == "value"


def test_require_env_missing(monkeypatch):
    monkeypatch.delenv("SF_TEST_ENV", raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        sf_auth._require_env("SF_TEST_ENV")
    assert "Missing required env var: SF_TEST_ENV" in str(excinfo.value)


# ---- get_salesforce_token ---------------------------------------------------


def test_get_salesforce_token_uses_cache(tmp_path, monkeypatch):
    """If cache file is valid, no HTTP call should be made."""
    cache_path = tmp_path / ".sfdump_token.json"
    now = time.time()
    cache_path.write_text(
        json.dumps(
            {
                "access_token": "CACHED_TOKEN",
                "expires_at": now + 3600,  # valid in the future
            }
        )
    )

    # Redirect CACHE_FILE to our temp location
    monkeypatch.setattr(sf_auth, "CACHE_FILE", cache_path)

    # Fail loudly if requests.post is called (it shouldn't be)
    def fake_post(*args, **kwargs):  # pragma: no cover - should not be hit
        raise AssertionError("requests.post should not be called when cache is valid")

    monkeypatch.setattr(sf_auth.requests, "post", fake_post)

    token = sf_auth.get_salesforce_token()
    assert token == "CACHED_TOKEN"


def test_get_salesforce_token_fetches_and_caches(tmp_path, monkeypatch):
    """When no valid cache exists, token is fetched and written to cache."""
    cache_path = tmp_path / ".sfdump_token.json"
    monkeypatch.setattr(sf_auth, "CACHE_FILE", cache_path)

    # Ensure no valid env var cache is used
    monkeypatch.setenv("SF_LOGIN_URL", "https://example.my.salesforce.com")
    monkeypatch.setenv("SF_CLIENT_ID", "cid")
    monkeypatch.setenv("SF_CLIENT_SECRET", "secret")

    calls = {}

    def fake_post(url, data=None, **kwargs):
        calls["url"] = url
        calls["data"] = data
        return DummyResponse(
            status_code=200,
            json_data={"access_token": "NEW_TOKEN", "expires_in": 1800},
        )

    monkeypatch.setattr(sf_auth.requests, "post", fake_post)

    token = sf_auth.get_salesforce_token()

    assert token == "NEW_TOKEN"
    # Check that we called the right endpoint and used client_credentials
    assert "oauth2/token" in calls["url"]
    assert calls["data"]["grant_type"] == "client_credentials"
    assert calls["data"]["client_id"] == "cid"
    assert calls["data"]["client_secret"] == "secret"

    # Check cache file was written
    assert cache_path.exists()
    cached = json.loads(cache_path.read_text())
    assert cached["access_token"] == "NEW_TOKEN"
    assert cached["expires_at"] > time.time()


def test_get_salesforce_token_http_error(tmp_path, monkeypatch):
    """HTTP error during token fetch should raise RuntimeError."""
    cache_path = tmp_path / ".sfdump_token.json"
    monkeypatch.setattr(sf_auth, "CACHE_FILE", cache_path)

    monkeypatch.setenv("SF_LOGIN_URL", "https://example.my.salesforce.com")
    monkeypatch.setenv("SF_CLIENT_ID", "cid")
    monkeypatch.setenv("SF_CLIENT_SECRET", "secret")

    def fake_post(url, data=None, **kwargs):
        return DummyResponse(status_code=400, text="Bad request", json_data={"err": "x"})

    monkeypatch.setattr(sf_auth.requests, "post", fake_post)

    with pytest.raises(RuntimeError) as excinfo:
        sf_auth.get_salesforce_token()

    msg = str(excinfo.value)
    assert "Token request failed (400)" in msg
    assert "Bad request" in msg


# ---- run_salesforce_query ---------------------------------------------------


def test_run_salesforce_query_success(monkeypatch):
    """Happy path: query succeeds and JSON is returned."""
    # Don't hit the real token logic here; just simulate a token
    monkeypatch.setattr(sf_auth, "get_salesforce_token", lambda: "ACCESS_TOKEN")

    monkeypatch.setenv("SF_LOGIN_URL", "https://example.my.salesforce.com")
    monkeypatch.setenv("SF_API_VERSION", "v60.0")

    calls = {}

    def fake_get(url, headers=None, **kwargs):
        calls["url"] = url
        calls["headers"] = headers
        return DummyResponse(status_code=200, json_data={"totalSize": 1, "done": True})

    monkeypatch.setattr(sf_auth.requests, "get", fake_get)

    res = sf_auth.run_salesforce_query("SELECT Id FROM Account LIMIT 1")

    assert res["totalSize"] == 1
    # Ensure Authorization header and URL look correct
    assert calls["headers"]["Authorization"] == "Bearer ACCESS_TOKEN"
    assert "/services/data/v60.0/query" in calls["url"]
    assert "SELECT+Id+FROM+Account+LIMIT+1" in calls["url"]


def test_run_salesforce_query_error(monkeypatch):
    """On non-2xx response, run_salesforce_query should raise RuntimeError."""
    monkeypatch.setattr(sf_auth, "get_salesforce_token", lambda: "ACCESS_TOKEN")
    monkeypatch.setenv("SF_LOGIN_URL", "https://example.my.salesforce.com")

    def fake_get(url, headers=None, **kwargs):
        # Return JSON error body
        return DummyResponse(
            status_code=500,
            json_data={"error": "server_error"},
            text="Internal Server Error",
        )

    monkeypatch.setattr(sf_auth.requests, "get", fake_get)

    with pytest.raises(RuntimeError) as excinfo:
        sf_auth.run_salesforce_query("SELECT Id FROM Account")

    msg = str(excinfo.value)
    assert "Query failed (500)" in msg
    assert "server_error" in msg
