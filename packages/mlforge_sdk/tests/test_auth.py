"""Tests for OAuth authentication client."""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mlforge_sdk.auth import (
    AuthClient,
    load_token,
    save_token,
    delete_token,
    _credentials_path,
)


class TestTokenStorage:
    """Test basic token storage functions."""

    def test_save_and_load_token(self, tmp_path):
        """Test saving and loading tokens."""
        # Mock the credentials path
        test_token = "test-token-123"

        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            # Save token
            save_token(test_token)
            assert cred_file.exists()

            # Verify structure
            data = json.loads(cred_file.read_text())
            assert data["accessToken"] == test_token
            assert "expiresAt" in data

            # Load token
            loaded = load_token()
            assert loaded == test_token

    def test_load_from_env(self, tmp_path):
        """Test loading token from environment variable."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            with patch.dict("os.environ", {"MLFORGE_TOKEN": "env-token"}):
                token = load_token()
                assert token == "env-token"

    def test_delete_token(self, tmp_path):
        """Test deleting token."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            # Save then delete
            save_token("test-token")
            assert cred_file.exists()

            delete_token()
            assert not cred_file.exists()

    def test_save_empty_token_fails(self):
        """Test that saving empty token raises error."""
        with pytest.raises(ValueError, match="Token is empty"):
            save_token("")

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading when file doesn't exist."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"
            token = load_token()
            assert token is None


class TestAuthClient:
    """Test OAuth authentication client."""

    @pytest.mark.asyncio
    async def test_find_available_port(self):
        """Test finding available port."""
        port = await AuthClient._find_available_port(9999)
        assert port >= 9999
        assert port < 9999 + 3

    @pytest.mark.asyncio
    async def test_has_token_no_token(self, tmp_path):
        """Test has_token when no token exists."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"
            client = AuthClient()
            has_token = await client.has_token()
            assert has_token is False

    @pytest.mark.asyncio
    async def test_has_token_with_token(self, tmp_path):
        """Test has_token when token exists."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            # Save a token
            save_token("test-token")

            client = AuthClient()
            has_token = await client.has_token()
            assert has_token is True

    @pytest.mark.asyncio
    async def test_get_stored_token(self, tmp_path):
        """Test retrieving stored token."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            save_token("my-token")

            client = AuthClient()
            token = await client.get_stored_token()
            assert token == "my-token"

    @pytest.mark.asyncio
    async def test_logout(self, tmp_path):
        """Test logout removes token."""
        with patch("mlforge_sdk.auth._credentials_path") as mock_path:
            cred_file = tmp_path / "credentials.json"
            mock_path.return_value = cred_file

            save_token("my-token")
            assert cred_file.exists()

            client = AuthClient()
            await client.logout()
            assert not cred_file.exists()


class TestAuthClientCallback:
    """Test OAuth callback server."""

    def test_oauth_handler_success(self, tmp_path):
        """Test successful OAuth callback."""
        from mlforge_sdk.auth import AuthClient
        from urllib.parse import urlencode
        from http.client import HTTPConnection

        client = AuthClient()
        port = 9876

        # Start server in background
        client._start_callback_server(port)

        try:
            # Simulate OAuth callback
            conn = HTTPConnection("127.0.0.1", port)
            params = urlencode({"token": "oauth-test-token"})
            conn.request("GET", f"/callback?{params}")
            response = conn.getresponse()

            assert response.status == 200
            assert client._callback_token == "oauth-test-token"

        finally:
            client._stop_callback_server()

    def test_oauth_handler_error(self, tmp_path):
        """Test OAuth callback error handling."""
        from mlforge_sdk.auth import AuthClient
        from urllib.parse import urlencode
        from http.client import HTTPConnection

        client = AuthClient()
        port = 9877

        # Start server in background
        client._start_callback_server(port)

        try:
            # Simulate OAuth error
            conn = HTTPConnection("127.0.0.1", port)
            params = urlencode({"error": "access_denied"})
            conn.request("GET", f"/callback?{params}")
            response = conn.getresponse()

            assert response.status == 400
            assert client._callback_error == "access_denied"

        finally:
            client._stop_callback_server()
