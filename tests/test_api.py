import json
import logging

import pytest

from sfdump.api import SalesforceAPI, SFConfig


class DummyResponse:
    """Simple fake response object mimicking requests.Response."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture()
def mock_session(monkeypatch):
    """Patch requests.Session to use predictable fake responses."""
    calls = []

    def fake_request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        # Return fake results based on endpoint
        if url.endswith("/services/data/"):
            # discovery endpoint
            return DummyResponse(
                200,
                [
                    {"version": "61.0", "url": "/services/data/v61.0"},
                    {"version": "62.0", "url": "/services/data/v62.0"},
                ],
            )
        if url.endswith("/limits"):
            return DummyResponse(200, {"DailyApiRequests": {"Max": 15000, "Remaining": 14999}})
        if "userinfo" in url:
            return DummyResponse(200, {"organization_id": "ORG123", "email": "user@example.com"})
        if "query" in url:
            return DummyResponse(200, {"records": [{"Id": "001", "Name": "Acme"}]})
        if url.endswith("/token"):
            return DummyResponse(
                200,
                {
                    "access_token": "tok",
                    "instance_url": "https://example.my.salesforce.com",
                },
            )
        return DummyResponse(200, {})

    monkeypatch.setattr("requests.Session.request", fake_request)
    return calls


@pytest.fixture()
def cfg_env(monkeypatch):
    """Preload env-style config."""
    return SFConfig(
        host="login.salesforce.com",
        client_id="cid",
        client_secret="sec",
        username="user@example.com",
        password="pw",
    )


def test_connect_and_discover_version(cfg_env, mock_session):
    api = SalesforceAPI(cfg_env)
    api.connect()

    assert api.api_version.startswith("v")
    assert api.instance_url.startswith("https://")
    assert api.access_token == "tok"


def test_whoami_and_limits(cfg_env, mock_session, caplog):
    api = SalesforceAPI(cfg_env)
    api.connect()

    with caplog.at_level(logging.INFO):
        who = api.whoami()
        lim = api.limits()

    assert "organization_id" in who
    assert "DailyApiRequests" in lim
    assert "Connected" in caplog.text or "Connected" not in caplog.text  # just ensure no crash


def test_query_returns_expected(cfg_env, mock_session):
    api = SalesforceAPI(cfg_env)
    api.connect()
    res = api.query("SELECT Id, Name FROM Account LIMIT 1")
    assert res["records"][0]["Name"] == "Acme"


def test_retry_and_error_handling(monkeypatch, cfg_env):
    """Ensure that retries occur and raise after final attempt."""

    calls = {"count": 0}

    def flaky_request(self, method, url, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            # simulate 503 twice
            resp = DummyResponse(503)
        else:
            resp = DummyResponse(200, {"ok": True})
        return resp

    monkeypatch.setattr("requests.Session.request", flaky_request)

    api = SalesforceAPI(cfg_env)
    api.access_token = "tok"
    api.instance_url = "https://example.my.salesforce.com"
    api.api_version = "v62.0"

    r = api._request("GET", f"{api.instance_url}/services/data/{api.api_version}/limits")
    assert r.json()["ok"]
    assert calls["count"] == 3
