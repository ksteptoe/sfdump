"""Tests for sfdump.update_check module (PyPI-based)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfdump.update_check import _parse_version, get_latest_release, is_update_available

# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    def test_plain_version(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        assert _parse_version("v1.2.3") == (1, 2, 3)

    def test_dev_suffix(self):
        assert _parse_version("2.7.1.dev5") == (2, 7, 1)

    def test_post_suffix(self):
        assert _parse_version("2.7.1.post1") == (2, 7, 1)

    def test_local_suffix(self):
        assert _parse_version("2.7.1+g1234abc") == (2, 7, 1)

    def test_two_part(self):
        assert _parse_version("1.0") == (1, 0)

    def test_single_part(self):
        assert _parse_version("5") == (5,)

    def test_comparison_newer(self):
        assert _parse_version("2.8.0") > _parse_version("2.7.1")

    def test_comparison_same(self):
        assert _parse_version("2.7.1") == _parse_version("2.7.1")

    def test_comparison_older(self):
        assert _parse_version("2.7.0") < _parse_version("2.7.1")


# ---------------------------------------------------------------------------
# get_latest_release
# ---------------------------------------------------------------------------


class TestGetLatestRelease:
    @patch("sfdump.update_check.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"info": {"version": "3.0.0"}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_latest_release()
        assert result == {"version": "3.0.0"}
        mock_get.assert_called_once_with("https://pypi.org/pypi/sfdump/json", timeout=5)

    @patch("sfdump.update_check.requests.get")
    def test_network_error(self, mock_get):
        mock_get.side_effect = ConnectionError("no internet")

        result = get_latest_release()
        assert result is None

    @patch("sfdump.update_check.requests.get")
    def test_bad_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"bad": "data"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_latest_release()
        assert result is None

    @patch("sfdump.update_check.requests.get")
    def test_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404")
        mock_get.return_value = mock_resp

        result = get_latest_release()
        assert result is None


# ---------------------------------------------------------------------------
# is_update_available
# ---------------------------------------------------------------------------


class TestIsUpdateAvailable:
    @patch("sfdump.update_check.get_latest_release")
    @patch("sfdump.update_check.__version__", "2.7.0")
    def test_newer_available(self, mock_release):
        mock_release.return_value = {"version": "2.8.0"}

        available, current, latest = is_update_available()
        assert available is True
        assert current == "2.7.0"
        assert latest == "2.8.0"

    @patch("sfdump.update_check.get_latest_release")
    @patch("sfdump.update_check.__version__", "2.8.0")
    def test_same_version(self, mock_release):
        mock_release.return_value = {"version": "2.8.0"}

        available, current, latest = is_update_available()
        assert available is False
        assert current == "2.8.0"
        assert latest == "2.8.0"

    @patch("sfdump.update_check.get_latest_release")
    @patch("sfdump.update_check.__version__", "2.8.0")
    def test_network_error(self, mock_release):
        mock_release.return_value = None

        available, current, latest = is_update_available()
        assert available is False
        assert current == "2.8.0"
        assert latest == ""

    @patch("sfdump.update_check.get_latest_release")
    @patch("sfdump.update_check.__version__", "3.0.0")
    def test_older_on_pypi(self, mock_release):
        mock_release.return_value = {"version": "2.8.0"}

        available, current, latest = is_update_available()
        assert available is False
        assert current == "3.0.0"
        assert latest == "2.8.0"
