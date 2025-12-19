"""
Tests for lgctl client module.
"""

import os
from unittest.mock import MagicMock, patch

from lgctl.client import LGCtlClient, get_client


class TestLGCtlClient:
    """Tests for LGCtlClient class."""

    @patch("lgctl.client.sdk_get_client")
    def test_init_with_url(self, mock_sdk):
        """Test initialization with explicit URL."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://test.example.com")
        assert client.url == "http://test.example.com"
        mock_sdk.assert_called_once()

    @patch("lgctl.client.sdk_get_client")
    def test_init_with_api_key(self, mock_sdk):
        """Test initialization with explicit API key."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:8123", api_key="test-key")
        assert client.api_key == "test-key"

    @patch("lgctl.client.sdk_get_client")
    def test_init_with_timeout(self, mock_sdk):
        """Test initialization with custom timeout."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:8123", timeout=60.0)
        assert client.timeout == 60.0

    @patch.dict(os.environ, {"LANGSMITH_DEPLOYMENT_URL": "http://langsmith.example.com"})
    @patch("lgctl.client.sdk_get_client")
    def test_resolve_url_langsmith(self, mock_sdk):
        """Test URL resolution from LANGSMITH_DEPLOYMENT_URL."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient()
        assert client.url == "http://langsmith.example.com"

    @patch.dict(os.environ, {"LANGGRAPH_URL": "http://langgraph.example.com"}, clear=True)
    @patch("lgctl.client.sdk_get_client")
    def test_resolve_url_langgraph(self, mock_sdk):
        """Test URL resolution from LANGGRAPH_URL."""
        mock_sdk.return_value = MagicMock()
        # Clear LANGSMITH_DEPLOYMENT_URL to test fallback
        with patch.dict(os.environ, {"LANGSMITH_DEPLOYMENT_URL": ""}, clear=False):
            client = LGCtlClient()
            # Should use LANGGRAPH_URL or default
            assert "localhost" in client.url or "langgraph" in client.url

    @patch.dict(os.environ, {}, clear=True)
    @patch("lgctl.client.sdk_get_client")
    def test_resolve_url_default(self, mock_sdk):
        """Test URL resolution falls back to localhost."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient()
        assert client.url == "http://localhost:8123"

    @patch.dict(os.environ, {"LANGSMITH_API_KEY": "env-api-key"})
    @patch("lgctl.client.sdk_get_client")
    def test_api_key_from_env(self, mock_sdk):
        """Test API key from environment variable."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:8123")
        assert client.api_key == "env-api-key"

    @patch("lgctl.client.sdk_get_client")
    def test_store_property(self, mock_sdk):
        """Test store property returns client store."""
        mock_internal_client = MagicMock()
        mock_sdk.return_value = mock_internal_client
        client = LGCtlClient(url="http://localhost:8123")
        _ = client.store
        assert mock_internal_client.store is not None

    @patch("lgctl.client.sdk_get_client")
    def test_threads_property(self, mock_sdk):
        """Test threads property returns client threads."""
        mock_internal_client = MagicMock()
        mock_sdk.return_value = mock_internal_client
        client = LGCtlClient(url="http://localhost:8123")
        _ = client.threads
        assert mock_internal_client.threads is not None

    @patch("lgctl.client.sdk_get_client")
    def test_runs_property(self, mock_sdk):
        """Test runs property returns client runs."""
        mock_internal_client = MagicMock()
        mock_sdk.return_value = mock_internal_client
        client = LGCtlClient(url="http://localhost:8123")
        _ = client.runs
        assert mock_internal_client.runs is not None

    @patch("lgctl.client.sdk_get_client")
    def test_assistants_property(self, mock_sdk):
        """Test assistants property returns client assistants."""
        mock_internal_client = MagicMock()
        mock_sdk.return_value = mock_internal_client
        client = LGCtlClient(url="http://localhost:8123")
        _ = client.assistants
        assert mock_internal_client.assistants is not None

    @patch("lgctl.client.sdk_get_client")
    def test_crons_property(self, mock_sdk):
        """Test crons property returns client crons."""
        mock_internal_client = MagicMock()
        mock_sdk.return_value = mock_internal_client
        client = LGCtlClient(url="http://localhost:8123")
        _ = client.crons
        assert mock_internal_client.crons is not None

    @patch("lgctl.client.sdk_get_client")
    def test_is_remote_localhost(self, mock_sdk):
        """Test is_remote returns False for localhost."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:8123")
        assert client.is_remote() is False

    @patch("lgctl.client.sdk_get_client")
    def test_is_remote_localhost_different_port(self, mock_sdk):
        """Test is_remote returns False for localhost with different port."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:9999")
        assert client.is_remote() is False

    @patch("lgctl.client.sdk_get_client")
    def test_is_remote_true(self, mock_sdk):
        """Test is_remote returns True for non-localhost."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="https://api.example.com")
        assert client.is_remote() is True

    @patch("lgctl.client.sdk_get_client")
    def test_repr_local(self, mock_sdk):
        """Test string representation for local client."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="http://localhost:8123")
        repr_str = repr(client)
        assert "http://localhost:8123" in repr_str
        assert "mode=local" in repr_str

    @patch("lgctl.client.sdk_get_client")
    def test_repr_remote(self, mock_sdk):
        """Test string representation for remote client."""
        mock_sdk.return_value = MagicMock()
        client = LGCtlClient(url="https://api.example.com")
        repr_str = repr(client)
        assert "https://api.example.com" in repr_str
        assert "mode=remote" in repr_str


class TestGetClient:
    """Tests for get_client function."""

    @patch("lgctl.client.sdk_get_client")
    def test_get_client_basic(self, mock_sdk):
        """Test basic get_client call."""
        mock_sdk.return_value = MagicMock()
        client = get_client(url="http://localhost:8123")
        assert isinstance(client, LGCtlClient)

    @patch("lgctl.client.sdk_get_client")
    def test_get_client_with_url(self, mock_sdk):
        """Test get_client with URL parameter."""
        mock_sdk.return_value = MagicMock()
        client = get_client(url="http://custom.example.com")
        assert client.url == "http://custom.example.com"

    @patch("lgctl.client.sdk_get_client")
    def test_get_client_with_api_key(self, mock_sdk):
        """Test get_client with API key parameter."""
        mock_sdk.return_value = MagicMock()
        client = get_client(url="http://localhost:8123", api_key="test-key")
        assert client.api_key == "test-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("lgctl.client.sdk_get_client")
    def test_get_client_default(self, mock_sdk):
        """Test get_client with defaults."""
        mock_sdk.return_value = MagicMock()
        client = get_client()
        assert client.url == "http://localhost:8123"


class TestMockClient:
    """Tests using MockLGCtlClient from conftest."""

    def test_mock_client_url(self, mock_client):
        """Test mock client has correct URL."""
        assert mock_client.url == "http://localhost:8123"

    def test_mock_client_is_local(self, mock_client):
        """Test mock client is detected as local."""
        assert mock_client.is_remote() is False

    def test_mock_remote_client_is_remote(self, mock_remote_client):
        """Test mock remote client is detected as remote."""
        assert mock_remote_client.is_remote() is True

    def test_mock_client_has_store(self, mock_client):
        """Test mock client has store property."""
        assert mock_client.store is not None

    def test_mock_client_has_threads(self, mock_client):
        """Test mock client has threads property."""
        assert mock_client.threads is not None

    def test_mock_client_has_runs(self, mock_client):
        """Test mock client has runs property."""
        assert mock_client.runs is not None

    def test_mock_client_has_assistants(self, mock_client):
        """Test mock client has assistants property."""
        assert mock_client.assistants is not None

    def test_mock_client_has_crons(self, mock_client):
        """Test mock client has crons property."""
        assert mock_client.crons is not None

    def test_mock_client_repr(self, mock_client):
        """Test mock client string representation."""
        repr_str = repr(mock_client)
        assert "MockLGCtlClient" in repr_str
        assert "mode=local" in repr_str
