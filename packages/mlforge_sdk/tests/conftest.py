import pytest
from unittest.mock import MagicMock
from mlforge_sdk.http import HttpClient

@pytest.fixture
def mock_http():
    return MagicMock(spec=HttpClient)
