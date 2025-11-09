import pytest

# only import the dataclass and helpers; avoid network
from sfdump import api


def test_sfconfig_from_env(monkeypatch):
    """Check SFConfig.from_env and its missing-var handling."""
    # populate minimal env vars
    monkeypatch.setenv("SF_USERNAME", "demo@example.com")
    monkeypatch.setenv("SF_PASSWORD", "pw")
    monkeypatch.setenv("SF_TOKEN", "tok")
    monkeypatch.setenv("SF_CLIENT_ID", "cid")
    monkeypatch.setenv("SF_CLIENT_SECRET", "csecret")

    cfg = api.SFConfig.from_env()
    assert cfg.username == "demo@example.com"
    assert "pw" in cfg.password
    assert cfg.token == "tok"
    assert cfg.client_id == "cid"


def test_sfconfig_missing(monkeypatch):
    """Ensure missing credentials raise MissingCredentialsError."""
    for var in [
        "SF_USERNAME",
        "SF_PASSWORD",
        "SF_TOKEN",
        "SF_CLIENT_ID",
        "SF_CLIENT_SECRET",
    ]:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(api.MissingCredentialsError):
        _ = api.SFConfig.from_env()
