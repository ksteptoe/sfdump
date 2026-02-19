"""Tests for the ``sf setup`` command."""

from click.testing import CliRunner

from sfdump.cli_simple import cli


def test_setup_creates_env_file(tmp_path, monkeypatch):
    """sf setup creates a .env with the correct variables."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup"],
        input="my_client_id\nmy_secret\nhttps://acme.my.salesforce.com\n",
    )
    assert result.exit_code == 0

    env_path = tmp_path / ".env"
    assert env_path.exists()
    content = env_path.read_text()

    assert "SF_AUTH_FLOW=client_credentials" in content
    assert "SF_CLIENT_ID=my_client_id" in content
    assert "SF_CLIENT_SECRET=my_secret" in content
    assert "SF_LOGIN_URL=https://acme.my.salesforce.com" in content


def test_setup_does_not_contain_username_or_password(tmp_path, monkeypatch):
    """sf setup must NOT prompt for or write SF_USERNAME / SF_PASSWORD."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup"],
        input="id\nsecret\nhttps://acme.my.salesforce.com\n",
    )
    assert result.exit_code == 0

    content = (tmp_path / ".env").read_text()
    assert "SF_USERNAME" not in content
    assert "SF_PASSWORD" not in content


def test_setup_uses_default_login_url(tmp_path, monkeypatch):
    """Pressing Enter at the URL prompt uses the default."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup"],
        input="id\nsecret\n\n",  # blank = accept default
    )
    assert result.exit_code == 0

    content = (tmp_path / ".env").read_text()
    assert "SF_LOGIN_URL=https://yourcompany.my.salesforce.com" in content


def test_setup_cancel_overwrite(tmp_path, monkeypatch):
    """Declining overwrite of existing .env does not change it."""
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("original")

    runner = CliRunner()
    result = runner.invoke(cli, ["setup"], input="n\n")
    assert result.exit_code == 0
    assert env_path.read_text() == "original"


def test_setup_shows_next_steps(tmp_path, monkeypatch):
    """sf setup prints helpful next-step commands."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup"],
        input="id\nsecret\nhttps://x.my.salesforce.com\n",
    )
    assert "sf test" in result.output
    assert "sf dump" in result.output
