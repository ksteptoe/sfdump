# tests/unit/test_command_files_cli.py
from __future__ import annotations

import pathlib

from click.testing import CliRunner

from sfdump import exceptions as exc
from sfdump.command_files import files_cmd

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
        raise exc.MissingCredentialsError(missing=["SF_CLIENT_ID", "SF_USERNAME"])


# We'll monkeypatch these callables inside sfdump.command_files
def _ret(kind: str, out_dir: str, count: int = 3, bytes_: int = 2048):
    # shape mirrors files.py return
    return {
        "kind": kind,
        "meta_csv": str(pathlib.Path(out_dir) / "links" / (kind + ".csv")),
        "links_csv": str(pathlib.Path(out_dir) / "links" / (kind + "_links.csv"))
        if kind == "content_version"
        else None,
        "count": count,
        "bytes": bytes_,
        "root": str(
            pathlib.Path(out_dir) / ("files" if kind == "content_version" else "files_legacy")
        ),
    }


class _Recorder:
    def __init__(self, ret_kind):
        self.calls = []
        self.ret_kind = ret_kind

    def __call__(self, api, out_dir, **kwargs):
        # record kwargs to assert propagation (where, max_workers)
        self.calls.append({"out_dir": out_dir, **kwargs})
        return _ret(self.ret_kind, out_dir)


# --- Tests -------------------------------------------------------------------


def test_files_default_runs_both(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    # monkeypatch API + Config
    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # recorders for both functions
    rec_cv = _Recorder("content_version")
    rec_att = _Recorder("attachment")
    monkeypatch.setattr(mod, "dump_content_versions", rec_cv, raising=True)
    monkeypatch.setattr(mod, "dump_attachments", rec_att, raising=True)

    # run CLI
    out_dir = tmp_path / "dump"
    result = CliRunner().invoke(files_cmd, ["--out", str(out_dir)])
    assert result.exit_code == 0, result.output

    # Output should include both summary lines and metadata hint
    out = result.output
    assert "content_version:" in out and "attachment:" in out
    assert "Metadata CSVs are under:" in out

    # Ensure functions were called with defaults (no filters) and default workers=8
    assert rec_cv.calls and rec_att.calls
    assert rec_cv.calls[0]["where"] is None
    assert rec_att.calls[0]["where"] is None
    assert rec_cv.calls[0]["max_workers"] == 8
    assert rec_att.calls[0]["max_workers"] == 8


def test_files_filters_and_workers_propagate(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    rec_cv = _Recorder("content_version")
    rec_att = _Recorder("attachment")
    monkeypatch.setattr(mod, "dump_content_versions", rec_cv, raising=True)
    monkeypatch.setattr(mod, "dump_attachments", rec_att, raising=True)

    out_dir = tmp_path / "out2"
    args = [
        "--out",
        str(out_dir),
        "--content-where",
        "FileType = 'PDF'",
        "--attachments-where",
        "CreatedDate = LAST_WEEK",
        "--max-workers",
        "3",
    ]
    result = CliRunner().invoke(files_cmd, args)
    assert result.exit_code == 0, result.output

    # Verify argument propagation
    assert rec_cv.calls[0]["where"] == "FileType = 'PDF'"
    assert rec_att.calls[0]["where"] == "CreatedDate = LAST_WEEK"
    assert rec_cv.calls[0]["max_workers"] == 3
    assert rec_att.calls[0]["max_workers"] == 3


def test_files_skip_content(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    rec_cv = _Recorder("content_version")
    rec_att = _Recorder("attachment")
    monkeypatch.setattr(mod, "dump_content_versions", rec_cv, raising=True)
    monkeypatch.setattr(mod, "dump_attachments", rec_att, raising=True)

    out_dir = tmp_path / "out3"
    result = CliRunner().invoke(files_cmd, ["--out", str(out_dir), "--no-content"])
    assert result.exit_code == 0, result.output

    # Only attachments should have been called
    assert rec_cv.calls == []
    assert len(rec_att.calls) == 1
    assert "attachment:" in result.output
    assert "content_version:" not in result.output


def test_files_skip_attachments(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    rec_cv = _Recorder("content_version")
    rec_att = _Recorder("attachment")
    monkeypatch.setattr(mod, "dump_content_versions", rec_cv, raising=True)
    monkeypatch.setattr(mod, "dump_attachments", rec_att, raising=True)

    out_dir = tmp_path / "out4"
    result = CliRunner().invoke(files_cmd, ["--out", str(out_dir), "--no-attachments"])
    assert result.exit_code == 0, result.output

    # Only content versions should have been called
    assert len(rec_cv.calls) == 1
    assert rec_att.calls == []
    assert "content_version:" in result.output
    assert "attachment:" not in result.output


def test_files_nothing_to_do_error(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_OK, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    # Don’t care about dumpers since both are disabled
    out_dir = tmp_path / "out5"
    result = CliRunner().invoke(
        files_cmd,
        ["--out", str(out_dir), "--no-content", "--no-attachments"],
    )
    assert result.exit_code != 0
    assert "Nothing to do" in result.output


def test_files_missing_credentials_clickerror(monkeypatch, tmp_path):
    import sfdump.command_files as mod

    monkeypatch.setattr(mod, "SalesforceAPI", _DummyAPI_Fail, raising=True)
    monkeypatch.setattr(mod, "SFConfig", _DummyConfig, raising=True)

    out_dir = tmp_path / "out6"
    result = CliRunner().invoke(files_cmd, ["--out", str(out_dir)])
    assert result.exit_code != 0
    out = result.output
    assert "Missing Salesforce" in out
    assert "JWT credentials" in out
