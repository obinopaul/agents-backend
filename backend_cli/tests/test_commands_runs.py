"""
Tests for lgctl commands/runs module.
"""

import pytest

from lgctl.commands.runs import RunCommands


class TestRunCommands:
    """Tests for RunCommands class."""

    @pytest.fixture
    def run_commands(self, mock_client, table_formatter):
        """Provide RunCommands instance."""
        return RunCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_basic(self, run_commands):
        """Test basic run listing."""
        result = await run_commands.ls("thread-001")
        assert isinstance(result, list)
        for run in result:
            assert "run_id" in run
            assert "thread_id" in run
            assert "status" in run

    @pytest.mark.asyncio
    async def test_ls_with_limit(self, run_commands):
        """Test listing runs with limit."""
        result = await run_commands.ls("thread-001", limit=1)
        assert isinstance(result, list)
        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_ls_with_offset(self, run_commands):
        """Test listing runs with offset."""
        result = await run_commands.ls("thread-001", offset=1)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_with_status_filter(self, run_commands):
        """Test listing runs with status filter."""
        result = await run_commands.ls("thread-001", status="success")
        assert isinstance(result, list)
        for run in result:
            assert run["status"] == "success"

    @pytest.mark.asyncio
    async def test_ls_empty_for_unknown_thread(self, run_commands):
        """Test listing runs for unknown thread."""
        result = await run_commands.ls("unknown-thread")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_existing_run(self, run_commands):
        """Test getting an existing run."""
        result = await run_commands.get("thread-001", "run-001")
        assert result is not None
        assert result["run_id"] == "run-001"
        assert result["thread_id"] == "thread-001"
        assert "status" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_run(self, run_commands):
        """Test getting a non-existent run."""
        result = await run_commands.get("thread-001", "nonexistent-run")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_basic(self, run_commands):
        """Test basic run creation."""
        result = await run_commands.create(thread_id="thread-001", assistant_id="assistant-001")
        assert result is not None
        assert "run_id" in result
        assert result["thread_id"] == "thread-001"
        assert result["assistant_id"] == "assistant-001"

    @pytest.mark.asyncio
    async def test_create_with_input(self, run_commands):
        """Test run creation with input."""
        result = await run_commands.create(
            thread_id="thread-001", assistant_id="assistant-001", input={"message": "Hello"}
        )
        assert result is not None
        assert "run_id" in result

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, run_commands):
        """Test run creation with metadata."""
        result = await run_commands.create(
            thread_id="thread-001", assistant_id="assistant-001", metadata={"source": "test"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_config(self, run_commands):
        """Test run creation with config."""
        result = await run_commands.create(
            thread_id="thread-001", assistant_id="assistant-001", config={"model": "gpt-4"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_multitask_strategy(self, run_commands):
        """Test run creation with multitask strategy."""
        result = await run_commands.create(
            thread_id="thread-001", assistant_id="assistant-001", multitask_strategy="enqueue"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_interrupts(self, run_commands):
        """Test run creation with interrupt points."""
        result = await run_commands.create(
            thread_id="thread-001",
            assistant_id="assistant-001",
            interrupt_before=["agent"],
            interrupt_after=["tool"],
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_wait_basic(self, run_commands):
        """Test waiting for run completion."""
        result = await run_commands.wait(thread_id="thread-001", assistant_id="assistant-001")
        assert result is not None
        assert "status" in result

    @pytest.mark.asyncio
    async def test_wait_with_input(self, run_commands):
        """Test waiting with input."""
        result = await run_commands.wait(
            thread_id="thread-001", assistant_id="assistant-001", input={"message": "test"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_wait_with_config(self, run_commands):
        """Test waiting with config."""
        result = await run_commands.wait(
            thread_id="thread-001", assistant_id="assistant-001", config={"timeout": 30}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_cancel_run(self, run_commands):
        """Test cancelling a run."""
        result = await run_commands.cancel("thread-001", "run-001")
        assert result["status"] == "ok"
        assert result["run_id"] == "run-001"
        assert result["action"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_with_wait(self, run_commands):
        """Test cancelling a run with wait."""
        result = await run_commands.cancel("thread-001", "run-001", wait=True)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_join_run(self, run_commands):
        """Test joining a run."""
        result = await run_commands.join("thread-001", "run-001")
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_run(self, run_commands):
        """Test deleting a run."""
        result = await run_commands.delete("thread-001", "run-001")
        assert result["status"] == "ok"
        assert result["run_id"] == "run-001"
        assert result["action"] == "deleted"

    @pytest.mark.asyncio
    async def test_rm_is_delete_alias(self, run_commands):
        """Test that rm is an alias for delete."""
        assert run_commands.rm == run_commands.delete


class TestRunCommandsReturnFormat:
    """Tests for RunCommands return format consistency."""

    @pytest.fixture
    def run_commands(self, mock_client, table_formatter):
        """Provide RunCommands instance."""
        return RunCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_returns_expected_fields(self, run_commands):
        """Test ls returns expected fields."""
        result = await run_commands.ls("thread-001")
        if result:
            run = result[0]
            expected_fields = {
                "run_id",
                "thread_id",
                "assistant_id",
                "status",
                "created_at",
                "updated_at",
            }
            assert expected_fields.issubset(set(run.keys()))

    @pytest.mark.asyncio
    async def test_get_returns_expected_fields(self, run_commands):
        """Test get returns expected fields."""
        result = await run_commands.get("thread-001", "run-001")
        expected_fields = {
            "run_id",
            "thread_id",
            "assistant_id",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_create_returns_expected_fields(self, run_commands):
        """Test create returns expected fields."""
        result = await run_commands.create(thread_id="thread-001", assistant_id="assistant-001")
        expected_fields = {"run_id", "thread_id", "assistant_id", "status", "created_at"}
        assert expected_fields.issubset(set(result.keys()))


class TestRunCommandsStream:
    """Tests for RunCommands stream functionality."""

    @pytest.fixture
    def run_commands(self, mock_client, table_formatter):
        """Provide RunCommands instance."""
        return RunCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_stream_basic(self, run_commands, mock_client):
        """Test basic streaming."""

        # Set up mock stream
        async def mock_stream(*args, **kwargs):
            class MockChunk:
                def __init__(self, event, data):
                    self.event = event
                    self.data = data

            yield MockChunk("start", {"run_id": "run-001"})
            yield MockChunk("data", {"output": "result"})
            yield MockChunk("end", {})

        mock_client.runs.stream = mock_stream

        chunks = []
        async for chunk in run_commands.stream(
            thread_id="thread-001", assistant_id="assistant-001"
        ):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0]["event"] == "start"
        assert chunks[1]["event"] == "data"
        assert chunks[2]["event"] == "end"

    @pytest.mark.asyncio
    async def test_stream_with_options(self, run_commands, mock_client):
        """Test streaming with options."""

        async def mock_stream(*args, **kwargs):
            class MockChunk:
                def __init__(self, event, data):
                    self.event = event
                    self.data = data

            yield MockChunk("data", {"output": "test"})

        mock_client.runs.stream = mock_stream

        chunks = []
        async for chunk in run_commands.stream(
            thread_id="thread-001",
            assistant_id="assistant-001",
            input={"message": "test"},
            config={"model": "gpt-4"},
            stream_mode="values",
            multitask_strategy="enqueue",
        ):
            chunks.append(chunk)

        assert len(chunks) >= 1
