"""
E2E test configuration.

These tests use REAL Salesforce connections - no mocking.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_dummy_api(monkeypatch):
    """
    Override the global dummy_api fixture from tests/conftest.py.

    E2E tests need real API connections, so we explicitly do NOT patch
    the SalesforceAPI class.
    """
    # This fixture takes precedence over the one in tests/conftest.py
    # because it's in a subdirectory conftest.py
    pass


@pytest.fixture(scope="session")
def check_credentials():
    """Verify Salesforce credentials are available."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    required_vars = [
        "SF_CLIENT_ID",
        "SF_CLIENT_SECRET",
        "SF_USERNAME",
        "SF_PASSWORD",
    ]

    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Missing credentials: {', '.join(missing)}")
