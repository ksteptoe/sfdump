"""Tests for sfdump.api module."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from sfdump.api import SalesforceAPI, SFConfig
from sfdump.exceptions import MissingCredentialsError


class TestSFConfig:
    """Tests for SFConfig dataclass."""

    def test_default_values(self):
        """Creates config with default values."""
        cfg = SFConfig()

        assert cfg.auth_flow == "client_credentials"
        assert cfg.login_url == "https://login.salesforce.com"
        assert cfg.client_id is None
        assert cfg.client_secret is None

    def test_from_env(self):
        """Loads config from environment variables."""
        env = {
            "SF_AUTH_FLOW": "client_credentials",
            "SF_LOGIN_URL": "https://test.salesforce.com",
            "SF_CLIENT_ID": "test_client_id",
            "SF_CLIENT_SECRET": "test_secret",
            "SF_ACCESS_TOKEN": "existing_token",
            "SF_INSTANCE_URL": "https://myorg.my.salesforce.com",
            "SF_API_VERSION": "v60.0",
        }

        with patch.dict(os.environ, env, clear=False):
            cfg = SFConfig.from_env()

        assert cfg.login_url == "https://test.salesforce.com"
        assert cfg.client_id == "test_client_id"
        assert cfg.client_secret == "test_secret"
        assert cfg.access_token == "existing_token"
        assert cfg.instance_url == "https://myorg.my.salesforce.com"
        assert cfg.api_version == "v60.0"

    def test_from_env_defaults(self):
        """Uses defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = SFConfig.from_env()

        assert cfg.auth_flow == "client_credentials"
        assert cfg.login_url == "https://login.salesforce.com"


class TestSalesforceAPIInit:
    """Tests for SalesforceAPI initialization."""

    def test_init_with_config(self):
        """Initializes with provided config."""
        cfg = SFConfig(
            client_id="my_id",
            client_secret="my_secret",
        )

        api = SalesforceAPI(cfg)

        assert api.cfg == cfg
        assert api.access_token is None
        assert api.instance_url is None

    def test_init_without_config(self):
        """Initializes with config from environment."""
        with patch.dict(os.environ, {"SF_CLIENT_ID": "env_id"}, clear=False):
            api = SalesforceAPI()

        assert api.cfg.client_id == "env_id"


class TestSalesforceAPIConnect:
    """Tests for SalesforceAPI.connect method."""

    def test_connect_with_existing_token(self):
        """Uses existing token when provided."""
        cfg = SFConfig(
            access_token="existing_token",
            instance_url="https://myorg.my.salesforce.com/",
            api_version="v60.0",
        )
        api = SalesforceAPI(cfg)

        api.connect()

        assert api.access_token == "existing_token"
        assert api.instance_url == "https://myorg.my.salesforce.com"
        assert api.api_version == "v60.0"
        assert "Authorization" in api.session.headers

    def test_connect_discovers_api_version(self):
        """Discovers latest API version when not provided."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
        )
        api = SalesforceAPI(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"version": "58.0", "url": "/services/data/v58.0"},
            {"version": "60.0", "url": "/services/data/v60.0"},
            {"version": "59.0", "url": "/services/data/v59.0"},
        ]
        mock_response.status_code = 200

        with patch.object(api.session, "request", return_value=mock_response):
            api.connect()

        assert api.api_version == "v60.0"

    def test_connect_raises_without_auth(self):
        """Raises error when auth fails."""
        cfg = SFConfig()
        api = SalesforceAPI(cfg)

        with pytest.raises(MissingCredentialsError):
            api.connect()


class TestSalesforceAPIClientCredentials:
    """Tests for client credentials login flow."""

    def test_missing_credentials_raises(self):
        """Raises MissingCredentialsError for missing credentials."""
        cfg = SFConfig(client_id=None, client_secret=None)
        api = SalesforceAPI(cfg)

        with pytest.raises(MissingCredentialsError) as exc_info:
            api._client_credentials_login()

        assert "SF_CLIENT_ID" in str(exc_info.value)
        assert "SF_CLIENT_SECRET" in str(exc_info.value)

    def test_successful_login(self):
        """Successfully logs in with client credentials."""
        cfg = SFConfig(
            client_id="test_id",
            client_secret="test_secret",
            login_url="https://login.salesforce.com",
        )
        api = SalesforceAPI(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "instance_url": "https://myorg.my.salesforce.com",
        }
        mock_response.status_code = 200

        with patch.object(api.session, "request", return_value=mock_response):
            api._client_credentials_login()

        assert api.access_token == "new_token"
        assert api.instance_url == "https://myorg.my.salesforce.com"


class TestSalesforceAPIQuery:
    """Tests for SOQL query methods."""

    @pytest.fixture
    def connected_api(self):
        """Return a pre-connected API instance."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
            api_version="v60.0",
        )
        api = SalesforceAPI(cfg)
        api.access_token = "token"
        api.instance_url = "https://myorg.my.salesforce.com"
        api.api_version = "v60.0"
        return api

    def test_query(self, connected_api):
        """Executes SOQL query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "records": [{"Id": "001", "Name": "Test"}],
            "totalSize": 1,
            "done": True,
        }
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            result = connected_api.query("SELECT Id, Name FROM Account")

        assert result["totalSize"] == 1
        assert result["records"][0]["Name"] == "Test"

    def test_query_all_iter(self, connected_api):
        """Iterates through paginated query results."""
        # First page
        page1 = MagicMock()
        page1.json.return_value = {
            "records": [{"Id": "001"}],
            "nextRecordsUrl": "/services/data/v60.0/query/next",
        }
        page1.status_code = 200

        # Second page
        page2 = MagicMock()
        page2.json.return_value = {
            "records": [{"Id": "002"}],
            "nextRecordsUrl": None,
        }
        page2.status_code = 200

        with patch.object(connected_api.session, "request", side_effect=[page1, page2]):
            results = list(connected_api.query_all_iter("SELECT Id FROM Account"))

        assert len(results) == 2
        assert results[0]["Id"] == "001"
        assert results[1]["Id"] == "002"

    def test_iter_query_delegates(self, connected_api):
        """iter_query delegates to query_all_iter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"records": [{"Id": "001"}]}
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            results = list(connected_api.iter_query("SELECT Id FROM Account"))

        assert len(results) == 1


class TestSalesforceAPIDescribe:
    """Tests for describe methods."""

    @pytest.fixture
    def connected_api(self):
        """Return a pre-connected API instance."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
            api_version="v60.0",
        )
        api = SalesforceAPI(cfg)
        api.access_token = "token"
        api.instance_url = "https://myorg.my.salesforce.com"
        api.api_version = "v60.0"
        return api

    def test_describe_global(self, connected_api):
        """Returns global sobjects describe."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sobjects": [
                {"name": "Account", "label": "Account"},
                {"name": "Contact", "label": "Contact"},
            ]
        }
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            result = connected_api.describe_global()

        assert len(result["sobjects"]) == 2

    def test_describe_object(self, connected_api):
        """Returns object describe."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "Account",
            "fields": [{"name": "Id"}, {"name": "Name"}],
        }
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            result = connected_api.describe_object("Account")

        assert result["name"] == "Account"
        assert len(result["fields"]) == 2


class TestSalesforceAPIDownload:
    """Tests for download_path_to_file method."""

    def test_download_requires_connection(self):
        """Raises error when not connected."""
        api = SalesforceAPI(SFConfig())

        with pytest.raises(RuntimeError, match="Not connected"):
            api.download_path_to_file("/path", "/target")

    def test_download_file(self, tmp_path):
        """Downloads file to target path."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
        )
        api = SalesforceAPI(cfg)
        api.instance_url = "https://myorg.my.salesforce.com"
        api.access_token = "token"

        target = tmp_path / "subdir" / "file.pdf"
        content = b"PDF content here"

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [content]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(api.session, "get", return_value=mock_response):
            bytes_written = api.download_path_to_file(
                "/services/data/v60.0/sobjects/ContentVersion/CV001/VersionData", str(target)
            )

        assert bytes_written == len(content)
        assert target.exists()
        assert target.read_bytes() == content


class TestSalesforceAPIRetry:
    """Tests for HTTP retry logic."""

    @pytest.fixture
    def connected_api(self):
        """Return a pre-connected API instance."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
            api_version="v60.0",
        )
        api = SalesforceAPI(cfg)
        api.access_token = "token"
        api.instance_url = "https://myorg.my.salesforce.com"
        api.api_version = "v60.0"
        return api

    def test_retries_on_500_error(self, connected_api):
        """Retries on 500 error then succeeds."""
        fail_response = MagicMock()
        fail_response.status_code = 500

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}

        with patch.object(
            connected_api.session, "request", side_effect=[fail_response, success_response]
        ):
            with patch("time.sleep"):  # Don't actually sleep
                result = connected_api._get("https://example.com/test")

        assert result.json()["success"] is True

    def test_retries_on_429_rate_limit(self, connected_api):
        """Retries on 429 rate limit error."""
        fail_response = MagicMock()
        fail_response.status_code = 429

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": "ok"}

        with patch.object(
            connected_api.session, "request", side_effect=[fail_response, success_response]
        ):
            with patch("time.sleep"):
                result = connected_api._get("https://example.com/test")

        assert result.json()["data"] == "ok"

    def test_raises_after_max_retries(self, connected_api):
        """Raises after max retries exhausted."""
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.json.return_value = {"error": "Server Error"}
        fail_response.text = "Server Error"
        fail_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

        with patch.object(connected_api.session, "request", return_value=fail_response):
            with patch("time.sleep"):
                with pytest.raises(requests.HTTPError):
                    connected_api._request("GET", "https://example.com/test", retries=3)

    def test_retries_on_request_exception(self, connected_api):
        """Retries on network errors."""
        success_response = MagicMock()
        success_response.status_code = 200

        with patch.object(
            connected_api.session,
            "request",
            side_effect=[
                requests.ConnectionError("Network error"),
                success_response,
            ],
        ):
            with patch("time.sleep"):
                result = connected_api._request("GET", "https://example.com/test")

        assert result.status_code == 200


class TestSalesforceAPILimits:
    """Tests for limits and whoami methods."""

    @pytest.fixture
    def connected_api(self):
        """Return a pre-connected API instance."""
        cfg = SFConfig(
            access_token="token",
            instance_url="https://myorg.my.salesforce.com",
            api_version="v60.0",
            login_url="https://login.salesforce.com",
        )
        api = SalesforceAPI(cfg)
        api.access_token = "token"
        api.instance_url = "https://myorg.my.salesforce.com"
        api.api_version = "v60.0"
        return api

    def test_limits(self, connected_api):
        """Returns API limits."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"DailyApiRequests": {"Max": 100000, "Remaining": 99000}}
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            result = connected_api.limits()

        assert result["DailyApiRequests"]["Max"] == 100000

    def test_whoami(self, connected_api):
        """Returns user identity info."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "email": "user@example.com",
            "user_id": "005ABC",
        }
        mock_response.status_code = 200

        with patch.object(connected_api.session, "request", return_value=mock_response):
            result = connected_api.whoami()

        assert result["email"] == "user@example.com"


class TestSalesforceAPIAuthFlow:
    """Tests for auth flow selection."""

    def test_unsupported_auth_flow_raises(self):
        """Raises error for unsupported auth flow."""
        cfg = SFConfig(auth_flow="unsupported_flow")
        api = SalesforceAPI(cfg)

        with pytest.raises(RuntimeError, match="Unsupported SF_AUTH_FLOW"):
            api._login_via_auth_flow()
