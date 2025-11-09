# tests/unit/test_command_manifest_cli.py
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sfdump import exceptions as exc
from sfdump.command_manifest import manifest_cmd
from sfdump.manifest import FilesExport, ObjectExport

# ------------------------ Dummies / recorders ------------------------


class _DummyConfig:
    @staticmethod
    def from_env():
        return object()


class _API_OK:
    def __init__(self, _cfg):
        self.instance_url = "https://example.my.salesforce.com"
        self.api_version = "v59.0"

    def connect(self):
        return True

    def whoami(self):
        return {
            "organization_id": "ORG123",
            "preferred_username": "user@example.com",
            "email": "fallback@example.com",
            "name": "User Name",
        }


class _API_MissingCreds:
    def __init__(self, _cfg):
        pass

    def connect(self):
        raise exc.MissingCredentialsError(missing=["SF_USERNAME", "SF_PASSWORD"])


class _API_Boom:
    def __init__(self, _cfg):
        pass

    def connect(self):
        raise RuntimeError("network down")


class _ScanRecorder:
    def __init__(self, objs=None, files=None):
        self.calls = []
        self.objs = objs if objs is not None else []
        self.files = files if files is not None else []

    # separate functions to match signatures
    def scan_objects(self, csv_root: str):
        self.calls.append(("objects", csv_root))
        return self.objs

    def scan_files(self, out_dir: str):
        self.calls.append(("files", out_dir))
        return self.files


class _WriteManifestRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, path: str, manifest):
        # record for assertions; create the file so CLI success message has a path
        self.calls.append((path, manifest))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("{}", encoding="utf-8")
        return path


# ------------------------------ Tests --------------------------------


def test_manifest_offline(monkeypatch, tmp_path):
    import sfdump.command_manifest as mod

    # offline should not require API at all
    monkeypatch.setattr(mod, "SalesforceAPI", _API_Boom, raising=True)  # would explode if called
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    scans = _ScanRecorder(
        objs=[ObjectExport(name="Account", csv=str(tmp_path / "csv" / "Account.csv"), rows=2)],
        files=[
            FilesExport(
                kind="content_version",
                meta_csv=str(tmp_path / "links" / "content_versions.csv"),
                links_csv=str(tmp_path / "links" / "content_document_links.csv"),
                count=1,
                bytes=10,
                root=str(tmp_path / "files"),
            )
        ],
    )
    monkeypatch.setattr(mod, "scan_objects", scans.scan_objects, raising=True)
    monkeypatch.setattr(mod, "scan_files", scans.scan_files, raising=True)

    writer = _WriteManifestRecorder()
    monkeypatch.setattr(mod, "write_manifest", writer, raising=True)

    out_dir = tmp_path / "export"
    result = CliRunner().invoke(manifest_cmd, ["--out", str(out_dir), "--offline"])
    assert result.exit_code == 0, result.output
    assert "Wrote manifest" in result.output

    # write_manifest called once with correct path
    assert len(writer.calls) == 1
    path, mf = writer.calls[0]
    assert Path(path).name == "manifest.json"
    # offline → org fields empty
    assert mf.org_id == "" and mf.username == "" and mf.instance_url == "" and mf.api_version == ""


def test_manifest_online_happy_path(monkeypatch, tmp_path):
    import sfdump.command_manifest as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _API_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    scans = _ScanRecorder(
        objs=[ObjectExport(name="Contact", csv=str(tmp_path / "csv" / "Contact.csv"), rows=3)],
        files=[
            FilesExport(
                kind="attachment",
                meta_csv=str(tmp_path / "links" / "attachments.csv"),
                links_csv=None,
                count=5,
                bytes=1234,
                root=str(tmp_path / "files_legacy"),
            )
        ],
    )
    monkeypatch.setattr(mod, "scan_objects", scans.scan_objects, raising=True)
    monkeypatch.setattr(mod, "scan_files", scans.scan_files, raising=True)

    writer = _WriteManifestRecorder()
    monkeypatch.setattr(mod, "write_manifest", writer, raising=True)

    out_dir = tmp_path / "exp_ok"
    result = CliRunner().invoke(manifest_cmd, ["--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    assert "Wrote manifest" in result.output

    assert len(writer.calls) == 1
    path, mf = writer.calls[0]
    assert Path(path).name == "manifest.json"
    # online info is populated from API
    assert mf.org_id == "ORG123"
    assert mf.username == "user@example.com"
    assert mf.instance_url == "https://example.my.salesforce.com"
    assert mf.api_version == "v59.0"
    # scan functions invoked with expected roots
    assert scans.calls[0] == ("objects", str(Path(out_dir) / "csv"))
    assert scans.calls[1] == ("files", str(out_dir))


def test_manifest_missing_credentials_graceful_offline(monkeypatch, tmp_path):
    import sfdump.command_manifest as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _API_MissingCreds, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    scans = _ScanRecorder(objs=[], files=[])
    monkeypatch.setattr(mod, "scan_objects", scans.scan_objects, raising=True)
    monkeypatch.setattr(mod, "scan_files", scans.scan_files, raising=True)

    writer = _WriteManifestRecorder()
    monkeypatch.setattr(mod, "write_manifest", writer, raising=True)

    out_dir = tmp_path / "exp_warn"
    result = CliRunner().invoke(manifest_cmd, ["--out", str(out_dir)])
    # Should still succeed, with a warning printed to stderr
    assert result.exit_code == 0
    assert "Warning: missing credentials" in result.stderr

    # Manifest written with empty org fields
    assert len(writer.calls) == 1
    _, mf = writer.calls[0]
    assert mf.org_id == "" and mf.username == "" and mf.instance_url == "" and mf.api_version == ""


def test_manifest_login_failure_clickerror(monkeypatch, tmp_path):
    import sfdump.command_manifest as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _API_Boom, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # scan/write shouldn't be reached
    out_dir = tmp_path / "exp_fail"
    res = CliRunner().invoke(manifest_cmd, ["--out", str(out_dir)])
    assert res.exit_code != 0
    assert "Salesforce login failed:" in res.output
