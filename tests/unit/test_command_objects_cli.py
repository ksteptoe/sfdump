# tests/unit/test_command_objects_cli.py
from click.testing import CliRunner

from sfdump import exceptions as exc
from sfdump.command_objects import objects_cmd


class _DummyConfig:
    @staticmethod
    def from_env():
        return object()  # anything; our DummyAPI ignores it


class _DummyAPI_OK:
    """Dummy API that connects fine and returns a mixed describe_global."""

    def __init__(self, _cfg):
        pass

    def connect(self):
        return True

    def describe_global(self):
        return {
            "sobjects": [
                {"name": "Account", "queryable": True},
                {"name": "Contact", "queryable": True},
                {"name": "AuditTrail", "queryable": False},
                {"name": "BigObject__b", "queryable": False},
            ]
        }


class _DummyAPI_Fail:
    """Dummy API that raises MissingCredentialsError from connect()."""

    def __init__(self, _cfg):
        pass

    def connect(self):
        # Provide a realistic 'missing' list so the CLI renders it
        raise exc.MissingCredentialsError(missing=["SF_USERNAME", "SF_PASSWORD"])


def test_objects_lists_queryable_by_default(monkeypatch):
    # Monkeypatch the API + Config used inside the command module
    import sfdump.command_objects as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    result = CliRunner().invoke(objects_cmd, [])
    assert result.exit_code == 0, result.output
    # Only queryable (sorted): Account, Contact
    lines = [ln.strip() for ln in result.output.splitlines() if ln.strip()]
    assert lines == ["Account", "Contact"]


def test_objects_lists_all_with_flag(monkeypatch):
    import sfdump.command_objects as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    result = CliRunner().invoke(objects_cmd, ["--all"])
    assert result.exit_code == 0, result.output
    # All (sorted): Account, AuditTrail, BigObject__b, Contact
    lines = [ln.strip() for ln in result.output.splitlines() if ln.strip()]
    assert lines == ["Account", "AuditTrail", "BigObject__b", "Contact"]


def test_objects_missing_credentials_clickerror(monkeypatch):
    import sfdump.command_objects as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_Fail, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    result = CliRunner().invoke(objects_cmd, [])
    # ClickException returns exit_code == 1 and prints our friendly message
    assert result.exit_code != 0
    out = result.output
    assert "Missing Salesforce credentials:" in out
    assert "SF_USERNAME" in out and "SF_PASSWORD" in out
    assert "sfdump login --help" in out
