"""Verify install documentation is consistent with the pip-based flow."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# User-facing docs that describe installation
INSTALL_DOCS = [
    REPO_ROOT / "INSTALL.md",
    REPO_ROOT / "README.rst",
    REPO_ROOT / "docs" / "user-guide" / "getting-started.md",
    REPO_ROOT / "docs" / "user-guide" / "installation.md",
]


@pytest.fixture(params=INSTALL_DOCS, ids=lambda p: p.name)
def doc_content(request):
    path = request.param
    if not path.exists():
        pytest.skip(f"{path} not found")
    return path.read_text()


def test_no_pip_install_editable_in_user_docs(doc_content):
    """User-facing docs must not contain ``pip install -e``."""
    assert "pip install -e" not in doc_content


def test_pip_install_sfdump_present(doc_content):
    """User-facing docs should mention ``pip install sfdump``."""
    assert "pip install sfdump" in doc_content


def test_no_download_zip_instructions():
    """No user-facing doc should tell users to 'Download ZIP'."""
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        content = path.read_text()
        assert "Download ZIP" not in content, f"'Download ZIP' found in {path.name}"


def test_bootstrap_referenced_in_getting_started():
    """getting-started.md should reference bootstrap.ps1."""
    gs = REPO_ROOT / "docs" / "user-guide" / "getting-started.md"
    if not gs.exists():
        pytest.skip("getting-started.md not found")
    content = gs.read_text()
    assert "bootstrap.ps1" in content


def test_no_username_password_in_cli_simple():
    """cli_simple.py setup command must not reference SF_USERNAME / SF_PASSWORD."""
    cli_path = REPO_ROOT / "src" / "sfdump" / "cli_simple.py"
    if not cli_path.exists():
        pytest.skip("cli_simple.py not found")
    content = cli_path.read_text()
    assert "SF_USERNAME" not in content
    assert "SF_PASSWORD" not in content


def test_bootstrap_has_no_zip_download():
    """bootstrap.ps1 must not contain ZIP download or GitHub API release logic."""
    bs = REPO_ROOT / "bootstrap.ps1"
    if not bs.exists():
        pytest.skip("bootstrap.ps1 not found")
    content = bs.read_text()
    assert "Expand-Archive" not in content
    assert "zipball_url" not in content
    assert "sfdump-download.zip" not in content


def test_setup_ps1_has_no_editable_install():
    """setup.ps1 must not contain ``pip install -e``."""
    sp = REPO_ROOT / "setup.ps1"
    if not sp.exists():
        pytest.skip("setup.ps1 not found")
    content = sp.read_text()
    assert "pip install -e" not in content
