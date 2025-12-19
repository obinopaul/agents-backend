"""
Tests for lgctl commands/threads module.
"""

import pytest

from lgctl.commands.threads import ThreadCommands


class TestThreadCommands:
    """Tests for ThreadCommands class."""

    @pytest.fixture
    def thread_commands(self, mock_client, table_formatter):
        """Provide ThreadCommands instance."""
        return ThreadCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_basic(self, thread_commands):
        """Test basic thread listing."""
        result = await thread_commands.ls()
        assert isinstance(result, list)
        assert len(result) > 0
        for thread in result:
            assert "thread_id" in thread
            assert "status" in thread

    @pytest.mark.asyncio
    async def test_ls_with_limit(self, thread_commands):
        """Test listing threads with limit."""
        result = await thread_commands.ls(limit=1)
        assert isinstance(result, list)
        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_ls_with_offset(self, thread_commands):
        """Test listing threads with offset."""
        result = await thread_commands.ls(offset=1)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_with_status_filter(self, thread_commands):
        """Test listing threads with status filter."""
        result = await thread_commands.ls(status="idle")
        assert isinstance(result, list)
        for thread in result:
            assert thread["status"] == "idle"

    @pytest.mark.asyncio
    async def test_ls_with_metadata_filter(self, thread_commands):
        """Test listing threads with metadata filter."""
        result = await thread_commands.ls(metadata={"user_id": "123"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_existing_thread(self, thread_commands):
        """Test getting an existing thread."""
        result = await thread_commands.get("thread-001")
        assert result is not None
        assert result["thread_id"] == "thread-001"
        assert "status" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, thread_commands):
        """Test getting a non-existent thread."""
        result = await thread_commands.get("nonexistent-thread")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_basic(self, thread_commands):
        """Test basic thread creation."""
        result = await thread_commands.create()
        assert result is not None
        assert "thread_id" in result
        assert "status" in result
        assert result["status"] == "idle"

    @pytest.mark.asyncio
    async def test_create_with_id(self, thread_commands):
        """Test thread creation with custom ID."""
        result = await thread_commands.create(thread_id="custom-thread-id")
        assert result["thread_id"] == "custom-thread-id"

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, thread_commands):
        """Test thread creation with metadata."""
        metadata = {"user_id": "test-user", "session": "abc123"}
        result = await thread_commands.create(metadata=metadata)
        assert result is not None
        assert "thread_id" in result

    @pytest.mark.asyncio
    async def test_create_if_exists_raise(self, thread_commands):
        """Test thread creation with if_exists=raise."""
        result = await thread_commands.create(if_exists="raise")
        assert result is not None

    @pytest.mark.asyncio
    async def test_rm_thread(self, thread_commands):
        """Test deleting a thread."""
        # Create a thread first
        await thread_commands.create(thread_id="thread-to-delete")

        # Delete it
        result = await thread_commands.rm("thread-to-delete")
        assert result["status"] == "ok"
        assert result["thread_id"] == "thread-to-delete"
        assert result["action"] == "deleted"

    @pytest.mark.asyncio
    async def test_state_basic(self, thread_commands):
        """Test getting thread state."""
        result = await thread_commands.state("thread-001")
        assert result is not None
        assert result["thread_id"] == "thread-001"
        assert "values" in result
        assert "checkpoint_id" in result

    @pytest.mark.asyncio
    async def test_state_with_checkpoint(self, thread_commands):
        """Test getting thread state with checkpoint."""
        result = await thread_commands.state("thread-001", checkpoint_id="cp-001")
        assert result is not None

    @pytest.mark.asyncio
    async def test_state_with_subgraphs(self, thread_commands):
        """Test getting thread state with subgraphs."""
        result = await thread_commands.state("thread-001", subgraphs=True)
        assert result is not None

    @pytest.mark.asyncio
    async def test_state_nonexistent_thread(self, thread_commands):
        """Test getting state of non-existent thread."""
        result = await thread_commands.state("nonexistent-thread")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_state(self, thread_commands):
        """Test updating thread state."""
        values = {"messages": ["new message"], "counter": 1}
        result = await thread_commands.update_state("thread-001", values)
        assert result["status"] == "ok"
        assert result["thread_id"] == "thread-001"
        assert "checkpoint_id" in result

    @pytest.mark.asyncio
    async def test_update_state_with_as_node(self, thread_commands):
        """Test updating thread state with as_node."""
        result = await thread_commands.update_state(
            "thread-001", {"value": "test"}, as_node="agent"
        )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_update_state_with_checkpoint(self, thread_commands):
        """Test updating thread state with checkpoint."""
        result = await thread_commands.update_state(
            "thread-001", {"value": "test"}, checkpoint_id="cp-001"
        )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_history_basic(self, thread_commands):
        """Test getting thread history."""
        result = await thread_commands.history("thread-001")
        assert isinstance(result, list)
        for entry in result:
            assert "checkpoint_id" in entry

    @pytest.mark.asyncio
    async def test_history_with_limit(self, thread_commands):
        """Test getting thread history with limit."""
        result = await thread_commands.history("thread-001", limit=2)
        assert isinstance(result, list)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_history_with_before(self, thread_commands):
        """Test getting thread history with before filter."""
        result = await thread_commands.history("thread-001", before="2024-01-15T00:00:00Z")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_history_with_checkpoint(self, thread_commands):
        """Test getting thread history starting from checkpoint."""
        result = await thread_commands.history("thread-001", checkpoint_id="cp-001")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_cp_thread(self, thread_commands):
        """Test copying a thread."""
        result = await thread_commands.cp("thread-001")
        assert result["status"] == "ok"
        assert result["action"] == "copied"
        assert result["from_thread"] == "thread-001"
        assert "to_thread" in result

    @pytest.mark.asyncio
    async def test_cp_thread_with_dst_id(self, thread_commands):
        """Test copying a thread with destination ID."""
        result = await thread_commands.cp("thread-001", dst_thread_id="thread-copy")
        assert result["status"] == "ok"
        assert result["to_thread"] == "thread-copy"

    @pytest.mark.asyncio
    async def test_cp_thread_with_checkpoint(self, thread_commands):
        """Test copying a thread from specific checkpoint."""
        result = await thread_commands.cp("thread-001", checkpoint_id="cp-001")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_cp_nonexistent_thread(self, thread_commands):
        """Test copying non-existent thread raises error."""
        with pytest.raises(ValueError) as exc_info:
            await thread_commands.cp("nonexistent-thread")
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_patch_thread(self, thread_commands):
        """Test patching thread metadata."""
        new_metadata = {"updated": True, "version": 2}
        result = await thread_commands.patch("thread-001", metadata=new_metadata)
        assert "thread_id" in result
        assert result["thread_id"] == "thread-001"

    @pytest.mark.asyncio
    async def test_patch_thread_no_changes(self, thread_commands):
        """Test patching thread with no changes."""
        result = await thread_commands.patch("thread-001")
        assert "thread_id" in result


class TestThreadCommandsReturnFormat:
    """Tests for ThreadCommands return format consistency."""

    @pytest.fixture
    def thread_commands(self, mock_client, table_formatter):
        """Provide ThreadCommands instance."""
        return ThreadCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_returns_expected_fields(self, thread_commands):
        """Test ls returns expected fields."""
        result = await thread_commands.ls()
        if result:
            thread = result[0]
            expected_fields = {"thread_id", "status", "created_at", "updated_at", "metadata"}
            assert expected_fields.issubset(set(thread.keys()))

    @pytest.mark.asyncio
    async def test_get_returns_expected_fields(self, thread_commands):
        """Test get returns expected fields."""
        result = await thread_commands.get("thread-001")
        expected_fields = {"thread_id", "status", "created_at", "updated_at", "metadata", "values"}
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_create_returns_expected_fields(self, thread_commands):
        """Test create returns expected fields."""
        result = await thread_commands.create()
        expected_fields = {"thread_id", "status", "created_at"}
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_state_returns_expected_fields(self, thread_commands):
        """Test state returns expected fields."""
        result = await thread_commands.state("thread-001")
        expected_fields = {"thread_id", "checkpoint_id", "values", "next", "tasks"}
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_history_returns_expected_fields(self, thread_commands):
        """Test history returns expected fields."""
        result = await thread_commands.history("thread-001")
        if result:
            entry = result[0]
            expected_fields = {"checkpoint_id", "thread_id", "created_at", "next"}
            assert expected_fields.issubset(set(entry.keys()))
