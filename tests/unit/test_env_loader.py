import sys
import types
from pathlib import Path

from sfdump.env_loader import load_env_files


def test_load_env_files_loads_first_existing(tmp_path, monkeypatch):
    """load_env_files should call load_dotenv on the first existing candidate."""
    # Create two candidate files; only the first needs to exist.
    env1 = tmp_path / ".env"
    env2 = tmp_path / ".dotenv"
    env1.write_text("SF_CLIENT_ID=dummy\n")
    env2.write_text("SHOULD_NOT_BE_USED=1\n")

    calls = []

    def fake_load_dotenv(path):
        calls.append(Path(path))
        return True

    # Install a dummy `dotenv` module so the import inside load_env_files uses it
    dummy_dotenv = types.ModuleType("dotenv")
    dummy_dotenv.load_dotenv = fake_load_dotenv
    sys.modules["dotenv"] = dummy_dotenv

    # Call with explicit candidates so we don't depend on cwd
    load_env_files(candidates=[env1, env2], quiet=True)

    # Only the first existing path should have been used
    assert calls == [env1]


def test_load_env_files_no_existing_files(tmp_path, monkeypatch):
    """If no candidate exists, load_dotenv should never be called."""
    missing = tmp_path / "missing.env"

    calls = []

    def fake_load_dotenv(path):
        calls.append(Path(path))
        return True

    dummy_dotenv = types.ModuleType("dotenv")
    dummy_dotenv.load_dotenv = fake_load_dotenv
    sys.modules["dotenv"] = dummy_dotenv

    load_env_files(candidates=[missing], quiet=True)

    # We shouldn't have attempted to load anything
    assert calls == []
