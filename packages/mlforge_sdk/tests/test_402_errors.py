"""Tests for 402 Payment Required (quota exceeded) error handling."""
import json
from unittest.mock import Mock, patch

import pytest
import requests

from mlforge_sdk.http import ApiError, HttpClient


class TestApiError:
    """Test ApiError exception class."""

    def test_api_error_basic(self):
        """Test basic ApiError creation."""
        error = ApiError("Test error", status=500)
        assert error.status == 500
        assert str(error) == "API 500: Test error"

    def test_api_error_with_payload(self):
        """Test ApiError with payload."""
        payload = {"detail": "error details"}
        error = ApiError("Test", status=400, payload=payload)
        assert error.payload == payload

    def test_api_error_no_status(self):
        """Test ApiError without status."""
        error = ApiError("Just a message")
        assert error.status == 0
        assert str(error) == "Just a message"


class TestQuotaExceededHandling:
    """Test 402 Payment Required handling."""

    def test_402_with_quota_details(self):
        """Test 402 error with quota information."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 402
        mock_response.ok = False
        mock_response.text = "Payment required"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "resource": "training_runs",
            "used": 5,
            "limit": 3,
            "upgrade_url": "https://mlforge.in/upgrade",
        }

        client = HttpClient("http://localhost:8005")

        with pytest.raises(ApiError) as exc_info:
            client._handle(mock_response)

        error = exc_info.value
        assert error.status == 402
        assert "training_runs" in str(error)
        assert "5/3" in str(error)
        assert error.payload["upgrade_url"] == "https://mlforge.in/upgrade"

    def test_402_without_quota_details(self):
        """Test 402 error without detailed payload."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 402
        mock_response.ok = False
        mock_response.text = "Payment required"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)

        client = HttpClient("http://localhost:8005")

        with pytest.raises(ApiError) as exc_info:
            client._handle(mock_response)

        error = exc_info.value
        assert error.status == 402
        assert "Limit exceeded" in str(error)

    def test_other_errors_unchanged(self):
        """Test that other errors still work correctly."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.ok = False
        mock_response.text = "Internal Server Error"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)

        client = HttpClient("http://localhost:8005")

        with pytest.raises(ApiError) as exc_info:
            client._handle(mock_response)

        error = exc_info.value
        assert error.status == 500
        assert "Internal Server Error" in str(error)

    def test_success_response_unchanged(self):
        """Test that success responses work unchanged."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"result": "ok"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}

        client = HttpClient("http://localhost:8005")
        result = client._handle(mock_response)

        assert result == {"result": "ok"}

    def test_204_no_content_unchanged(self):
        """Test that 204 No Content still returns None."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 204
        mock_response.ok = True

        client = HttpClient("http://localhost:8005")
        result = client._handle(mock_response)

        assert result is None
