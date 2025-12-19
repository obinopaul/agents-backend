"""
Tests for lgctl MCP server module.

Note: These tests require the 'mcp' optional dependency to be installed.
Run: pip install lgctl[mcp] or pip install mcp
"""

import json
from unittest.mock import patch

import pytest

# Check if mcp module is available
try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Skip all tests in this module if mcp is not installed
pytestmark = pytest.mark.skipif(not HAS_MCP, reason="mcp package not installed")


class TestMCPTools:
    """Tests for MCP tool functions."""

    @pytest.fixture
    def setup_mocks(self, mock_client):
        """Set up mocks for MCP server."""
        with patch("lgctl.mcp_server.get_lgctl_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            yield mock_get_client

    @pytest.mark.asyncio
    async def test_store_list_namespaces(self, setup_mocks, mock_client):
        """Test store_list_namespaces tool."""
        from lgctl.mcp_server import store_list_namespaces

        result = await store_list_namespaces(prefix="", max_depth=3, limit=50)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_store_list_namespaces_with_prefix(self, setup_mocks, mock_client):
        """Test store_list_namespaces with prefix."""
        from lgctl.mcp_server import store_list_namespaces

        result = await store_list_namespaces(prefix="user", max_depth=2, limit=10)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_store_list_items(self, setup_mocks, mock_client):
        """Test store_list_items tool."""
        from lgctl.mcp_server import store_list_items

        result = await store_list_items(namespace="user,123", limit=20)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_store_get_existing(self, setup_mocks, mock_client):
        """Test store_get for existing item."""
        from lgctl.mcp_server import store_get

        result = await store_get(namespace="user,123", key="preferences")
        parsed = json.loads(result)
        assert "key" in parsed
        assert parsed["key"] == "preferences"

    @pytest.mark.asyncio
    async def test_store_get_nonexistent(self, setup_mocks, mock_client):
        """Test store_get for non-existent item."""
        from lgctl.mcp_server import store_get

        result = await store_get(namespace="user,123", key="nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_store_put_string(self, setup_mocks, mock_client):
        """Test store_put with string value."""
        from lgctl.mcp_server import store_put

        result = await store_put(
            namespace="user,999", key="test_key", value="test_value", is_json=False
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_store_put_json(self, setup_mocks, mock_client):
        """Test store_put with JSON value."""
        from lgctl.mcp_server import store_put

        result = await store_put(
            namespace="user,999", key="test_key", value='{"data": 123}', is_json=True
        )
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_store_put_invalid_json(self, setup_mocks, mock_client):
        """Test store_put with invalid JSON."""
        from lgctl.mcp_server import store_put

        result = await store_put(
            namespace="user,999", key="test_key", value="not valid json {", is_json=True
        )
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_store_delete(self, setup_mocks, mock_client):
        """Test store_delete tool."""
        from lgctl.mcp_server import store_delete

        result = await store_delete(namespace="user,123", key="preferences")
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_store_search(self, setup_mocks, mock_client):
        """Test store_search tool."""
        from lgctl.mcp_server import store_search

        result = await store_search(namespace="user,123", query="theme", limit=10)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_store_count(self, setup_mocks, mock_client):
        """Test store_count tool."""
        from lgctl.mcp_server import store_count

        result = await store_count(namespace="user,123")
        parsed = json.loads(result)
        assert "count" in parsed

    @pytest.mark.asyncio
    async def test_threads_list(self, setup_mocks, mock_client):
        """Test threads_list tool."""
        from lgctl.mcp_server import threads_list

        result = await threads_list(limit=20, status="")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_threads_list_with_status(self, setup_mocks, mock_client):
        """Test threads_list with status filter."""
        from lgctl.mcp_server import threads_list

        result = await threads_list(limit=20, status="idle")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_threads_get_existing(self, setup_mocks, mock_client):
        """Test threads_get for existing thread."""
        from lgctl.mcp_server import threads_get

        result = await threads_get(thread_id="thread-001")
        parsed = json.loads(result)
        assert "thread_id" in parsed

    @pytest.mark.asyncio
    async def test_threads_get_nonexistent(self, setup_mocks, mock_client):
        """Test threads_get for non-existent thread."""
        from lgctl.mcp_server import threads_get

        result = await threads_get(thread_id="nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_threads_get_state(self, setup_mocks, mock_client):
        """Test threads_get_state tool."""
        from lgctl.mcp_server import threads_get_state

        result = await threads_get_state(thread_id="thread-001")
        parsed = json.loads(result)
        assert "thread_id" in parsed or "error" in parsed

    @pytest.mark.asyncio
    async def test_threads_get_history(self, setup_mocks, mock_client):
        """Test threads_get_history tool."""
        from lgctl.mcp_server import threads_get_history

        result = await threads_get_history(thread_id="thread-001", limit=10)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_threads_create(self, setup_mocks, mock_client):
        """Test threads_create tool."""
        from lgctl.mcp_server import threads_create

        result = await threads_create(thread_id="", metadata_json="")
        parsed = json.loads(result)
        assert "thread_id" in parsed

    @pytest.mark.asyncio
    async def test_threads_create_with_metadata(self, setup_mocks, mock_client):
        """Test threads_create with metadata."""
        from lgctl.mcp_server import threads_create

        result = await threads_create(thread_id="custom-thread", metadata_json='{"user": "test"}')
        parsed = json.loads(result)
        assert "thread_id" in parsed

    @pytest.mark.asyncio
    async def test_threads_create_invalid_metadata(self, setup_mocks, mock_client):
        """Test threads_create with invalid metadata JSON."""
        from lgctl.mcp_server import threads_create

        result = await threads_create(thread_id="", metadata_json="not valid json {")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_threads_delete(self, setup_mocks, mock_client):
        """Test threads_delete tool."""
        from lgctl.mcp_server import threads_delete

        result = await threads_delete(thread_id="thread-001")
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_memory_analyze(self, setup_mocks, mock_client):
        """Test memory_analyze tool."""
        from lgctl.mcp_server import memory_analyze

        result = await memory_analyze(namespace="", detailed=False)
        parsed = json.loads(result)
        assert "total_namespaces" in parsed

    @pytest.mark.asyncio
    async def test_memory_analyze_detailed(self, setup_mocks, mock_client):
        """Test memory_analyze with detailed flag."""
        from lgctl.mcp_server import memory_analyze

        result = await memory_analyze(namespace="user", detailed=True)
        parsed = json.loads(result)
        assert "total_items" in parsed

    @pytest.mark.asyncio
    async def test_memory_stats(self, setup_mocks, mock_client):
        """Test memory_stats tool."""
        from lgctl.mcp_server import memory_stats

        result = await memory_stats()
        parsed = json.loads(result)
        assert "total_namespaces" in parsed
        assert "total_items" in parsed

    @pytest.mark.asyncio
    async def test_memory_find(self, setup_mocks, mock_client):
        """Test memory_find tool."""
        from lgctl.mcp_server import memory_find

        result = await memory_find(
            namespace="user,123", key_pattern="pref", value_contains="", limit=50
        )
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_memory_grep(self, setup_mocks, mock_client):
        """Test memory_grep tool."""
        from lgctl.mcp_server import memory_grep

        result = await memory_grep(pattern="theme", namespace="user,123", limit=50)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_memory_export(self, setup_mocks, mock_client):
        """Test memory_export tool."""
        from lgctl.mcp_server import memory_export

        result = await memory_export(namespace="user,123", format="json")
        # Should be JSON or contain data
        assert result is not None

    @pytest.mark.asyncio
    async def test_assistants_list(self, setup_mocks, mock_client):
        """Test assistants_list tool."""
        from lgctl.mcp_server import assistants_list

        result = await assistants_list(limit=20)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_assistants_get_existing(self, setup_mocks, mock_client):
        """Test assistants_get for existing assistant."""
        from lgctl.mcp_server import assistants_get

        result = await assistants_get(assistant_id="assistant-001")
        parsed = json.loads(result)
        assert "assistant_id" in parsed

    @pytest.mark.asyncio
    async def test_assistants_get_nonexistent(self, setup_mocks, mock_client):
        """Test assistants_get for non-existent assistant."""
        from lgctl.mcp_server import assistants_get

        result = await assistants_get(assistant_id="nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_runs_list(self, setup_mocks, mock_client):
        """Test runs_list tool."""
        from lgctl.mcp_server import runs_list

        result = await runs_list(thread_id="thread-001", limit=20)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_runs_get_existing(self, setup_mocks, mock_client):
        """Test runs_get for existing run."""
        from lgctl.mcp_server import runs_get

        result = await runs_get(thread_id="thread-001", run_id="run-001")
        parsed = json.loads(result)
        assert "run_id" in parsed

    @pytest.mark.asyncio
    async def test_runs_get_nonexistent(self, setup_mocks, mock_client):
        """Test runs_get for non-existent run."""
        from lgctl.mcp_server import runs_get

        result = await runs_get(thread_id="thread-001", run_id="nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed


class TestGetLGCtlClient:
    """Tests for get_lgctl_client function."""

    def test_get_client_no_url(self):
        """Test get_client raises when no URL configured."""
        # Reset global client
        import lgctl.mcp_server
        from lgctl.mcp_server import get_lgctl_client

        lgctl.mcp_server._client = None

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_lgctl_client()
            assert "No LangGraph URL configured" in str(exc_info.value)

    def test_get_client_with_env_url(self, mock_client):
        """Test get_client uses environment URL."""
        import lgctl.mcp_server
        from lgctl.mcp_server import get_lgctl_client

        lgctl.mcp_server._client = None

        with patch.dict("os.environ", {"LANGSMITH_DEPLOYMENT_URL": "http://test.example.com"}):
            with patch("lgctl.mcp_server.get_client") as mock_get:
                mock_get.return_value = mock_client
                get_lgctl_client()
                mock_get.assert_called_once()

    def test_get_client_cached(self, mock_client):
        """Test get_client returns cached client."""
        import lgctl.mcp_server
        from lgctl.mcp_server import get_lgctl_client

        lgctl.mcp_server._client = mock_client

        # Should return cached client without creating new one
        result = get_lgctl_client()
        assert result is mock_client

        # Clean up
        lgctl.mcp_server._client = None


class TestMCPServerSetup:
    """Tests for MCP server setup."""

    def test_mcp_server_created(self):
        """Test MCP server is created."""
        from lgctl.mcp_server import mcp

        assert mcp is not None
        assert mcp.name == "lgctl"

    def test_formatter_is_json(self):
        """Test formatter is JSON formatter."""
        from lgctl.formatters import JsonFormatter
        from lgctl.mcp_server import _formatter

        assert isinstance(_formatter, JsonFormatter)
