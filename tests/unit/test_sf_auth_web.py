"""Tests for the Web Server OAuth flow with PKCE."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from unittest.mock import MagicMock, patch

from sfdump.sf_auth_web import (
    _generate_code_challenge,
    _generate_code_verifier,
    _load_cached_token,
    _save_token,
    get_web_token,
    load_refresh_token,
)


class TestPKCE:
    def test_code_verifier_length(self):
        verifier = _generate_code_verifier()
        assert len(verifier) == 128

    def test_code_verifier_uniqueness(self):
        v1 = _generate_code_verifier()
        v2 = _generate_code_verifier()
        assert v1 != v2

    def test_code_challenge_is_s256(self):
        verifier = "test_verifier_string"
        challenge = _generate_code_challenge(verifier)
        # Verify independently
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        assert challenge == expected

    def test_code_challenge_no_padding(self):
        verifier = _generate_code_verifier()
        challenge = _generate_code_challenge(verifier)
        assert "=" not in challenge


class TestTokenPersistence:
    def test_save_and_load_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            _save_token(
                {"access_token": "tok123", "refresh_token": "ref456"},
                expires_in=3600,
            )
            cached = _load_cached_token()
            assert cached is not None
            assert cached["access_token"] == "tok123"
            assert cached["refresh_token"] == "ref456"

    def test_load_expired_token_returns_none(self, tmp_path):
        token_file = tmp_path / "token.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            data = {
                "access_token": "expired",
                "expires_at": time.time() - 100,
            }
            token_file.write_text(json.dumps(data))
            assert _load_cached_token() is None

    def test_load_missing_file_returns_none(self, tmp_path):
        token_file = tmp_path / "nonexistent.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            assert _load_cached_token() is None

    def test_load_corrupt_file_returns_none(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text("not json")
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            assert _load_cached_token() is None

    def test_load_refresh_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            _save_token(
                {"access_token": "tok", "refresh_token": "myrefresh"},
                expires_in=3600,
            )
            assert load_refresh_token() == "myrefresh"

    def test_load_refresh_token_missing_file(self, tmp_path):
        token_file = tmp_path / "nonexistent.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            assert load_refresh_token() is None


class TestGetWebToken:
    def test_returns_cached_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        with patch("sfdump.sf_auth_web.TOKEN_FILE", token_file):
            _save_token({"access_token": "cached_tok"}, expires_in=3600)
            assert get_web_token() == "cached_tok"

    def test_refreshes_expired_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        data = {
            "access_token": "expired",
            "refresh_token": "valid_refresh",
            "expires_at": time.time() - 100,
        }
        token_file.write_text(json.dumps(data))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_tok",
            "expires_in": 7200,
        }

        with (
            patch("sfdump.sf_auth_web.TOKEN_FILE", token_file),
            patch("sfdump.sf_auth_web.requests.post", return_value=mock_resp),
            patch.dict(
                "os.environ",
                {
                    "SF_LOGIN_URL": "https://test.salesforce.com",
                    "SF_CLIENT_ID": "cid",
                    "SF_CLIENT_SECRET": "csec",
                },
            ),
        ):
            token = get_web_token()
            assert token == "new_tok"

    def test_refresh_preserves_existing_refresh_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        data = {
            "access_token": "expired",
            "refresh_token": "keep_this",
            "expires_at": time.time() - 100,
        }
        token_file.write_text(json.dumps(data))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_tok",
            "expires_in": 7200,
            # No refresh_token in response
        }

        with (
            patch("sfdump.sf_auth_web.TOKEN_FILE", token_file),
            patch("sfdump.sf_auth_web.requests.post", return_value=mock_resp),
            patch.dict(
                "os.environ",
                {
                    "SF_LOGIN_URL": "https://test.salesforce.com",
                    "SF_CLIENT_ID": "cid",
                    "SF_CLIENT_SECRET": "csec",
                },
            ),
        ):
            get_web_token()
            saved = json.loads(token_file.read_text())
            assert saved["refresh_token"] == "keep_this"

    def test_refresh_failure_falls_through_to_interactive(self, tmp_path):
        token_file = tmp_path / "token.json"
        data = {
            "access_token": "expired",
            "refresh_token": "bad_refresh",
            "expires_at": time.time() - 100,
        }
        token_file.write_text(json.dumps(data))

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "invalid_grant"

        with (
            patch("sfdump.sf_auth_web.TOKEN_FILE", token_file),
            patch("sfdump.sf_auth_web.requests.post", return_value=mock_resp),
            patch(
                "sfdump.sf_auth_web.interactive_login", return_value="interactive_tok"
            ) as mock_login,
            patch.dict(
                "os.environ",
                {
                    "SF_LOGIN_URL": "https://test.salesforce.com",
                    "SF_CLIENT_ID": "cid",
                    "SF_CLIENT_SECRET": "csec",
                },
            ),
        ):
            token = get_web_token()
            assert token == "interactive_tok"
            mock_login.assert_called_once()
