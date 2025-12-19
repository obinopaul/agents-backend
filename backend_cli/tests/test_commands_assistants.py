"""
Tests for lgctl commands/assistants module.
"""

import pytest

from lgctl.commands.assistants import AssistantCommands


class TestAssistantCommands:
    """Tests for AssistantCommands class."""

    @pytest.fixture
    def assistant_commands(self, mock_client, table_formatter):
        """Provide AssistantCommands instance."""
        return AssistantCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_basic(self, assistant_commands):
        """Test basic assistant listing."""
        result = await assistant_commands.ls()
        assert isinstance(result, list)
        for assistant in result:
            assert "assistant_id" in assistant
            assert "graph_id" in assistant

    @pytest.mark.asyncio
    async def test_ls_with_limit(self, assistant_commands):
        """Test listing assistants with limit."""
        result = await assistant_commands.ls(limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_ls_with_offset(self, assistant_commands):
        """Test listing assistants with offset."""
        result = await assistant_commands.ls(offset=0)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_with_graph_id_filter(self, assistant_commands):
        """Test listing assistants with graph_id filter."""
        result = await assistant_commands.ls(graph_id="graph-001")
        assert isinstance(result, list)
        for assistant in result:
            assert assistant["graph_id"] == "graph-001"

    @pytest.mark.asyncio
    async def test_ls_with_metadata_filter(self, assistant_commands):
        """Test listing assistants with metadata filter."""
        result = await assistant_commands.ls(metadata={"type": "test"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_existing_assistant(self, assistant_commands):
        """Test getting an existing assistant."""
        result = await assistant_commands.get("assistant-001")
        assert result is not None
        assert result["assistant_id"] == "assistant-001"
        assert "graph_id" in result
        assert "name" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_assistant(self, assistant_commands):
        """Test getting a non-existent assistant."""
        result = await assistant_commands.get("nonexistent-assistant")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_basic(self, assistant_commands):
        """Test basic assistant creation."""
        result = await assistant_commands.create(graph_id="test-graph")
        assert result is not None
        assert "assistant_id" in result
        assert result["graph_id"] == "test-graph"

    @pytest.mark.asyncio
    async def test_create_with_name(self, assistant_commands):
        """Test assistant creation with name."""
        result = await assistant_commands.create(graph_id="test-graph", name="My Assistant")
        assert result is not None
        assert result["name"] == "My Assistant"

    @pytest.mark.asyncio
    async def test_create_with_config(self, assistant_commands):
        """Test assistant creation with config."""
        result = await assistant_commands.create(
            graph_id="test-graph", config={"model": "gpt-4", "temperature": 0.7}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, assistant_commands):
        """Test assistant creation with metadata."""
        result = await assistant_commands.create(
            graph_id="test-graph", metadata={"owner": "test-user", "environment": "dev"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_if_exists(self, assistant_commands):
        """Test assistant creation with if_exists option."""
        result = await assistant_commands.create(graph_id="test-graph", if_exists="return")
        assert result is not None

    @pytest.mark.asyncio
    async def test_rm_assistant(self, assistant_commands):
        """Test deleting an assistant."""
        # Create first
        created = await assistant_commands.create(graph_id="test-graph")

        # Delete
        result = await assistant_commands.rm(created["assistant_id"])
        assert result["status"] == "ok"
        assert result["assistant_id"] == created["assistant_id"]
        assert result["action"] == "deleted"

    @pytest.mark.asyncio
    async def test_graph_get(self, assistant_commands):
        """Test getting assistant graph."""
        result = await assistant_commands.graph("assistant-001")
        assert result is not None
        # Graph should have nodes and edges
        assert "nodes" in result or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_schema_get(self, assistant_commands):
        """Test getting assistant schemas."""
        result = await assistant_commands.schema("assistant-001")
        assert result is not None
        # Schema should have input/output
        assert "input" in result or "output" in result or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_patch_assistant(self, assistant_commands):
        """Test patching an assistant."""
        result = await assistant_commands.patch(assistant_id="assistant-001", name="Updated Name")
        assert result is not None
        assert result["assistant_id"] == "assistant-001"

    @pytest.mark.asyncio
    async def test_patch_with_graph_id(self, assistant_commands):
        """Test patching assistant with new graph_id."""
        result = await assistant_commands.patch(assistant_id="assistant-001", graph_id="new-graph")
        assert result is not None

    @pytest.mark.asyncio
    async def test_patch_with_config(self, assistant_commands):
        """Test patching assistant with new config."""
        result = await assistant_commands.patch(
            assistant_id="assistant-001", config={"model": "gpt-4-turbo"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_patch_with_metadata(self, assistant_commands):
        """Test patching assistant with new metadata."""
        result = await assistant_commands.patch(
            assistant_id="assistant-001", metadata={"version": "2.0"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_versions_get(self, assistant_commands):
        """Test getting assistant versions."""
        result = await assistant_commands.versions("assistant-001")
        assert isinstance(result, list)
        for version in result:
            assert "version" in version
            assert "assistant_id" in version

    @pytest.mark.asyncio
    async def test_versions_with_limit(self, assistant_commands):
        """Test getting versions with limit."""
        result = await assistant_commands.versions("assistant-001", limit=2)
        assert isinstance(result, list)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_versions_with_offset(self, assistant_commands):
        """Test getting versions with offset."""
        result = await assistant_commands.versions("assistant-001", offset=1)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_versions_nonexistent_assistant(self, assistant_commands, mock_client):
        """Test getting versions of non-existent assistant."""

        # Mock to raise exception
        async def raise_error(*args, **kwargs):
            raise Exception("Not found")

        mock_client.assistants.get_versions = raise_error

        result = await assistant_commands.versions("nonexistent")
        assert result == []


class TestAssistantCommandsReturnFormat:
    """Tests for AssistantCommands return format consistency."""

    @pytest.fixture
    def assistant_commands(self, mock_client, table_formatter):
        """Provide AssistantCommands instance."""
        return AssistantCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_returns_expected_fields(self, assistant_commands):
        """Test ls returns expected fields."""
        result = await assistant_commands.ls()
        if result:
            assistant = result[0]
            expected_fields = {
                "assistant_id",
                "graph_id",
                "name",
                "version",
                "created_at",
                "updated_at",
                "metadata",
            }
            assert expected_fields.issubset(set(assistant.keys()))

    @pytest.mark.asyncio
    async def test_get_returns_expected_fields(self, assistant_commands):
        """Test get returns expected fields."""
        result = await assistant_commands.get("assistant-001")
        expected_fields = {
            "assistant_id",
            "graph_id",
            "name",
            "version",
            "config",
            "metadata",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_create_returns_expected_fields(self, assistant_commands):
        """Test create returns expected fields."""
        result = await assistant_commands.create(graph_id="test-graph")
        expected_fields = {"assistant_id", "graph_id", "name", "created_at"}
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_patch_returns_expected_fields(self, assistant_commands):
        """Test patch returns expected fields."""
        result = await assistant_commands.patch(assistant_id="assistant-001", name="Updated")
        expected_fields = {"assistant_id", "graph_id", "name", "updated_at"}
        assert expected_fields.issubset(set(result.keys()))
