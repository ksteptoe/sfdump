from sfdump import api


def test_sfconfig_from_env(monkeypatch):
    """Ensure SFConfig.from_env reads expected client-credentials variables."""
    monkeypatch.setenv("SF_CLIENT_ID", "cid")
    monkeypatch.setenv("SF_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("SF_LOGIN_URL", "https://example.my.salesforce.com")
    monkeypatch.setenv("SF_AUTH_FLOW", "client_credentials")

    cfg = api.SFConfig.from_env()

    # Core attributes for client_credentials flow
    assert cfg is not None
    assert cfg.auth_flow == "client_credentials"
    assert cfg.client_id == "cid"
    assert cfg.client_secret == "csecret"
    assert cfg.login_url == "https://example.my.salesforce.com"

    # We have *intentionally* abandoned username/password
    assert not hasattr(cfg, "username")
    assert not hasattr(cfg, "password")


def test_sfconfig_missing_is_tolerated(monkeypatch):
    """Verify from_env() can still return an object even if some vars are missing."""
    for var in [
        "SF_CLIENT_ID",
        "SF_CLIENT_SECRET",
        "SF_LOGIN_URL",
        "SF_AUTH_FLOW",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = api.SFConfig.from_env()

    # Should not raise; may log a warning or leave fields empty
    assert cfg is not None

    # It should expose client-credential fields even if values are None
    assert hasattr(cfg, "client_id")
    assert hasattr(cfg, "client_secret")
    assert cfg.client_id is None
    assert cfg.client_secret is None

    # auth_flow should still default correctly
    assert cfg.auth_flow == "client_credentials"
    assert isinstance(cfg.login_url, str)
    assert cfg.login_url.startswith("https://")
