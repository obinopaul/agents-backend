"""
Tests for lgctl commands/crons module.
"""

import pytest

from lgctl.commands.crons import CronCommands


class TestCronCommands:
    """Tests for CronCommands class."""

    @pytest.fixture
    def cron_commands(self, mock_client, table_formatter):
        """Provide CronCommands instance."""
        return CronCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_basic(self, cron_commands):
        """Test basic cron listing."""
        result = await cron_commands.ls()
        assert isinstance(result, list)
        for cron in result:
            assert "cron_id" in cron
            assert "schedule" in cron

    @pytest.mark.asyncio
    async def test_ls_with_limit(self, cron_commands):
        """Test listing crons with limit."""
        result = await cron_commands.ls(limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_ls_with_offset(self, cron_commands):
        """Test listing crons with offset."""
        result = await cron_commands.ls(offset=0)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ls_with_assistant_filter(self, cron_commands):
        """Test listing crons with assistant_id filter."""
        result = await cron_commands.ls(assistant_id="assistant-001")
        assert isinstance(result, list)
        for cron in result:
            assert cron["assistant_id"] == "assistant-001"

    @pytest.mark.asyncio
    async def test_ls_with_thread_filter(self, cron_commands):
        """Test listing crons with thread_id filter."""
        result = await cron_commands.ls(thread_id="thread-001")
        assert isinstance(result, list)
        for cron in result:
            assert cron["thread_id"] == "thread-001"

    @pytest.mark.asyncio
    async def test_get_existing_cron(self, cron_commands):
        """Test getting an existing cron."""
        result = await cron_commands.get("cron-001")
        assert result is not None
        assert result["cron_id"] == "cron-001"
        assert "schedule" in result
        assert "enabled" in result

    @pytest.mark.asyncio
    async def test_get_nonexistent_cron(self, cron_commands):
        """Test getting a non-existent cron."""
        result = await cron_commands.get("nonexistent-cron")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_basic(self, cron_commands):
        """Test basic cron creation."""
        result = await cron_commands.create(
            assistant_id="assistant-001",
            schedule="0 * * * *",  # Hourly
        )
        assert result is not None
        assert "cron_id" in result
        assert result["assistant_id"] == "assistant-001"
        assert result["schedule"] == "0 * * * *"

    @pytest.mark.asyncio
    async def test_create_with_thread(self, cron_commands):
        """Test cron creation with specific thread."""
        result = await cron_commands.create(
            assistant_id="assistant-001",
            schedule="*/5 * * * *",  # Every 5 minutes
            thread_id="thread-001",
        )
        assert result is not None
        assert result["thread_id"] == "thread-001"

    @pytest.mark.asyncio
    async def test_create_with_input(self, cron_commands):
        """Test cron creation with input."""
        result = await cron_commands.create(
            assistant_id="assistant-001",
            schedule="0 0 * * *",  # Daily at midnight
            input={"action": "daily_sync"},
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, cron_commands):
        """Test cron creation with metadata."""
        result = await cron_commands.create(
            assistant_id="assistant-001",
            schedule="0 0 * * 0",  # Weekly on Sunday
            metadata={"purpose": "weekly_report"},
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_rm_cron(self, cron_commands):
        """Test deleting a cron."""
        # Create first
        created = await cron_commands.create(assistant_id="assistant-001", schedule="0 0 * * *")

        # Delete
        result = await cron_commands.rm(created["cron_id"])
        assert result["status"] == "ok"
        assert result["cron_id"] == created["cron_id"]
        assert result["action"] == "deleted"

    @pytest.mark.asyncio
    async def test_patch_schedule(self, cron_commands):
        """Test patching cron schedule."""
        result = await cron_commands.patch(
            cron_id="cron-001",
            schedule="*/10 * * * *",  # Every 10 minutes
        )
        assert result is not None
        assert result["cron_id"] == "cron-001"
        assert result["schedule"] == "*/10 * * * *"

    @pytest.mark.asyncio
    async def test_patch_input(self, cron_commands):
        """Test patching cron input."""
        result = await cron_commands.patch(cron_id="cron-001", input={"updated": True})
        assert result is not None

    @pytest.mark.asyncio
    async def test_patch_metadata(self, cron_commands):
        """Test patching cron metadata."""
        result = await cron_commands.patch(cron_id="cron-001", metadata={"version": "2.0"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_enable_cron(self, cron_commands):
        """Test enabling a cron."""
        result = await cron_commands.enable("cron-001")
        assert result["status"] == "ok"
        assert result["cron_id"] == "cron-001"
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_disable_cron(self, cron_commands):
        """Test disabling a cron."""
        result = await cron_commands.disable("cron-001")
        assert result["status"] == "ok"
        assert result["cron_id"] == "cron-001"
        assert result["enabled"] is False


class TestCronCommandsReturnFormat:
    """Tests for CronCommands return format consistency."""

    @pytest.fixture
    def cron_commands(self, mock_client, table_formatter):
        """Provide CronCommands instance."""
        return CronCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_ls_returns_expected_fields(self, cron_commands):
        """Test ls returns expected fields."""
        result = await cron_commands.ls()
        if result:
            cron = result[0]
            expected_fields = {
                "cron_id",
                "thread_id",
                "assistant_id",
                "schedule",
                "enabled",
                "next_run_at",
                "created_at",
            }
            assert expected_fields.issubset(set(cron.keys()))

    @pytest.mark.asyncio
    async def test_get_returns_expected_fields(self, cron_commands):
        """Test get returns expected fields."""
        result = await cron_commands.get("cron-001")
        expected_fields = {
            "cron_id",
            "thread_id",
            "assistant_id",
            "schedule",
            "enabled",
            "input",
            "metadata",
            "next_run_at",
            "last_run_at",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_create_returns_expected_fields(self, cron_commands):
        """Test create returns expected fields."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="0 * * * *")
        expected_fields = {
            "cron_id",
            "thread_id",
            "assistant_id",
            "schedule",
            "next_run_at",
            "created_at",
        }
        assert expected_fields.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_patch_returns_expected_fields(self, cron_commands):
        """Test patch returns expected fields."""
        result = await cron_commands.patch(cron_id="cron-001", schedule="*/15 * * * *")
        expected_fields = {"cron_id", "schedule", "next_run_at", "updated_at"}
        assert expected_fields.issubset(set(result.keys()))


class TestCronScheduleFormats:
    """Tests for cron schedule format handling."""

    @pytest.fixture
    def cron_commands(self, mock_client, table_formatter):
        """Provide CronCommands instance."""
        return CronCommands(mock_client, table_formatter)

    @pytest.mark.asyncio
    async def test_create_hourly(self, cron_commands):
        """Test creating hourly cron."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="0 * * * *")
        assert result["schedule"] == "0 * * * *"

    @pytest.mark.asyncio
    async def test_create_daily(self, cron_commands):
        """Test creating daily cron."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="0 0 * * *")
        assert result["schedule"] == "0 0 * * *"

    @pytest.mark.asyncio
    async def test_create_weekly(self, cron_commands):
        """Test creating weekly cron."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="0 0 * * 0")
        assert result["schedule"] == "0 0 * * 0"

    @pytest.mark.asyncio
    async def test_create_monthly(self, cron_commands):
        """Test creating monthly cron."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="0 0 1 * *")
        assert result["schedule"] == "0 0 1 * *"

    @pytest.mark.asyncio
    async def test_create_every_5_minutes(self, cron_commands):
        """Test creating cron every 5 minutes."""
        result = await cron_commands.create(assistant_id="assistant-001", schedule="*/5 * * * *")
        assert result["schedule"] == "*/5 * * * *"
