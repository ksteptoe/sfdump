from sfdump import api


def test_sfconfig_from_env(monkeypatch):
    """Ensure SFConfig.from_env reads expected variables."""
    monkeypatch.setenv("SF_USERNAME", "demo@example.com")
    monkeypatch.setenv("SF_PASSWORD", "pw")
    monkeypatch.setenv("SF_CLIENT_ID", "cid")
    monkeypatch.setenv("SF_CLIENT_SECRET", "csecret")

    cfg = api.SFConfig.from_env()
    # expected attributes based on common pattern
    assert hasattr(cfg, "username")
    assert hasattr(cfg, "password")
    assert hasattr(cfg, "client_id")
    assert hasattr(cfg, "client_secret")

    # contents
    assert cfg.username == "demo@example.com"
    assert "pw" in cfg.password
    assert cfg.client_id == "cid"


def test_sfconfig_missing_is_tolerated(monkeypatch):
    """Verify from_env() can still return an object even if some vars are missing."""
    for var in [
        "SF_USERNAME",
        "SF_PASSWORD",
        "SF_CLIENT_ID",
        "SF_CLIENT_SECRET",
    ]:
        monkeypatch.delenv(var, raising=False)

    # Should not raise; may log a warning or leave fields empty
    cfg = api.SFConfig.from_env()
    assert cfg is not None
    # It should have username/password attributes even if empty
    assert hasattr(cfg, "username")
    assert hasattr(cfg, "password")
