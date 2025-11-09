# tests/unit/test_command_csv_cli.py
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sfdump import exceptions as exc
from sfdump.command_csv import csv_cmd

# --- Dummies -----------------------------------------------------------------


class _DummyConfig:
    @staticmethod
    def from_env():
        return object()  # ignored by DummyAPI


class _DummyAPI_OK:
    def __init__(self, _cfg):
        self.connected = False

    def connect(self):
        self.connected = True
        return True


class _DummyAPI_Fail:
    def __init__(self, _cfg):
        pass

    def connect(self):
        # Simulate missing credentials at connect()
        raise exc.MissingCredentialsError(missing=["SF_USERNAME", "SF_PASSWORD"])


class _DumpRecorder:
    """Records parameters passed to dump_object_to_csv and returns a fake path/count."""

    def __init__(self, rows=7):
        self.calls = []
        self.rows = rows

    def __call__(self, *, api, object_name, out_dir, fields, where, limit):
        # record all parameters to assert propagation
        self.calls.append(
            dict(
                api=api,
                object_name=object_name,
                out_dir=out_dir,
                fields=tuple(fields) if fields is not None else None,
                where=where,
                limit=limit,
            )
        )
        fake_path = str(Path(out_dir) / f"{object_name}.csv")
        return fake_path, self.rows


# --- Tests -------------------------------------------------------------------


def test_csv_with_explicit_fields_and_filters(monkeypatch, tmp_path):
    import sfdump.command_csv as mod

    # Patch API and Config
    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # Use real fieldnames_for_object path? We won't touch it here because --fields is provided.
    rec = _DumpRecorder(rows=11)
    monkeypatch.setattr(mod, "dump_object_to_csv", rec, raising=True)

    out_dir = tmp_path / "export"
    args = [
        "--object",
        "Account",
        "--out",
        str(out_dir),
        "--fields",
        "Id, Name ,Industry",
        "--where",
        "IsActive = true",
        "--limit",
        "5",
    ]
    result = CliRunner().invoke(csv_cmd, args)
    assert result.exit_code == 0, result.output

    # Assert dump was called once with correct propagation
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call["object_name"] == "Account"
    assert Path(call["out_dir"]).name == "csv"  # out_dir joined with /csv
    assert call["fields"] == ("Id", "Name", "Industry")
    assert call["where"] == "IsActive = true"
    assert call["limit"] == 5

    # Success message contains row count and path
    assert "Wrote 11 rows" in result.output
    assert str(Path(call["out_dir"]) / "Account.csv") in result.output


def test_csv_uses_fieldnames_for_object_when_fields_missing(monkeypatch, tmp_path):
    import sfdump.command_csv as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # Make fieldnames_for_object return a known set
    monkeypatch.setattr(
        mod, "fieldnames_for_object", lambda api, name: ["Id", "X", "Y"], raising=True
    )

    rec = _DumpRecorder(rows=2)
    monkeypatch.setattr(mod, "dump_object_to_csv", rec, raising=True)

    out_dir = tmp_path / "exp2"
    result = CliRunner().invoke(csv_cmd, ["--object", "Contact", "--out", str(out_dir)])
    assert result.exit_code == 0, result.output

    call = rec.calls[0]
    assert call["object_name"] == "Contact"
    assert call["fields"] == ("Id", "X", "Y")
    assert call["where"] is None
    assert call["limit"] is None
    assert "Wrote 2 rows" in result.output


def test_csv_describe_failure_clickerror(monkeypatch, tmp_path):
    import sfdump.command_csv as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    def _boom(*_a, **_k):
        raise RuntimeError("describe failed")

    monkeypatch.setattr(mod, "fieldnames_for_object", _boom, raising=True)

    out_dir = tmp_path / "exp3"
    result = CliRunner().invoke(csv_cmd, ["--object", "Unknown__c", "--out", str(out_dir)])
    assert result.exit_code != 0
    assert "Failed to describe object 'Unknown__c'." in result.output


def test_csv_dump_failure_clickerror(monkeypatch, tmp_path):
    import sfdump.command_csv as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # fields resolution path (no --fields) but then dump raises
    monkeypatch.setattr(mod, "fieldnames_for_object", lambda api, name: ["Id"], raising=True)

    def _dump_fail(**kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(mod, "dump_object_to_csv", _dump_fail, raising=True)

    out_dir = tmp_path / "exp4"
    result = CliRunner().invoke(
        csv_cmd, ["--object", "Case", "--out", str(out_dir), "--limit", "1"]
    )
    assert result.exit_code != 0
    assert "Failed to dump Case to CSV." in result.output


def test_csv_missing_credentials_clickerror(monkeypatch, tmp_path):
    import sfdump.command_csv as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_Fail, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    out_dir = tmp_path / "exp5"
    result = CliRunner().invoke(csv_cmd, ["--object", "Lead", "--out", str(out_dir)])
    assert result.exit_code != 0
    out = result.output
    assert "Missing Salesforce credentials:" in out
    assert "SF_USERNAME" in out and "SF_PASSWORD" in out
