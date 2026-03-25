"""
Unit tests for SandboxController.

Tests the lifecycle management of sandboxes including creation, connection,
pause, resume, delete, and command execution - all with mocked providers.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


class TestSandboxControllerLifecycle:
    """Test SandboxController lifecycle operations with mocked provider."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock SandboxConfig."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxConfig") as MockConfig:
            config = MagicMock()
            config.provider_type = "e2b"
            config.e2b_api_key = "test_api_key"
            config.e2b_template_id = "base"
            config.redis_url = "redis://localhost:6379"
            config.queue_name = "test_queue"
            config.timeout_seconds = 3600
            config.pause_before_timeout_seconds = 600
            config.timeout_buffer_seconds = 600
            config.has_queue_provider = True
            yield config

    @pytest.fixture
    def mock_sandbox_instance(self):
        """Create a mock sandbox instance."""
        sandbox = AsyncMock()
        sandbox.sandbox_id = "test-sandbox-id"
        sandbox.provider_sandbox_id = "e2b-provider-id"
        sandbox.status = "running"
        return sandbox

    @pytest.fixture
    def mock_queue_scheduler(self):
        """Create a mock queue scheduler."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxQueueScheduler") as MockQueue:
            scheduler = MagicMock()
            scheduler.setup_consumer = AsyncMock()
            scheduler.start_consuming = AsyncMock()
            scheduler.stop_consuming = AsyncMock()
            scheduler.schedule_message = AsyncMock()
            scheduler.cancel_message = AsyncMock()
            MockQueue.return_value = scheduler
            yield scheduler

    @pytest.fixture
    def mock_db(self):
        """Create mock database operations."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.Sandboxes") as MockDB:
            MockDB.create_sandbox = AsyncMock()
            MockDB.get_sandbox_by_id = AsyncMock()
            MockDB.update_last_activity = AsyncMock()
            MockDB.delete_sandbox = AsyncMock()
            MockDB.update_sandbox_status = AsyncMock()
            MockDB.get_sandbox_by_user_id = AsyncMock(return_value=None)
            yield MockDB

    @pytest.mark.asyncio
    async def test_controller_initialization(self, mock_config, mock_queue_scheduler):
        """Test that SandboxController initializes correctly."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            assert controller is not None
            assert controller.sandbox_config == mock_config

    @pytest.mark.asyncio
    async def test_start_controller(self, mock_config, mock_queue_scheduler):
        """Test starting the sandbox controller."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            await controller.start()
            
            # Verify queue consumer setup was called
            mock_queue_scheduler.setup_consumer.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sandbox_success(self, mock_config, mock_queue_scheduler, mock_db, mock_sandbox_instance):
        """Test successful sandbox creation."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            mock_provider_class = MagicMock()
            mock_provider_class.create = AsyncMock(return_value=mock_sandbox_instance)
            MockFactory.get_provider.return_value = mock_provider_class
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            await controller.start()
            
            result = await controller.create_sandbox(user_id="test-user")
            
            # Verify provider create was called
            mock_provider_class.create.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_connect_to_running_sandbox(self, mock_config, mock_queue_scheduler, mock_db, mock_sandbox_instance):
        """Test connecting to an existing running sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            mock_provider_class = MagicMock()
            mock_provider_class.connect = AsyncMock(return_value=mock_sandbox_instance)
            MockFactory.get_provider.return_value = mock_provider_class
            
            # Setup mock DB to return existing sandbox
            mock_db_sandbox = MagicMock()
            mock_db_sandbox.status = "running"
            mock_db_sandbox.provider_sandbox_id = "e2b-provider-id"
            mock_db_sandbox.sandbox_id = "test-sandbox-id"
            mock_db.get_sandbox_by_id.return_value = mock_db_sandbox
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            await controller.start()
            
            result = await controller.connect(sandbox_id="test-sandbox-id")
            
            mock_provider_class.connect.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_pause_sandbox(self, mock_config, mock_queue_scheduler, mock_db, mock_sandbox_instance):
        """Test pausing a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            mock_provider_class = MagicMock()
            mock_provider_class.pause = AsyncMock()
            MockFactory.get_provider.return_value = mock_provider_class
            
            # Setup mock DB to return existing sandbox
            mock_db_sandbox = MagicMock()
            mock_db_sandbox.status = "running"
            mock_db_sandbox.provider_sandbox_id = "e2b-provider-id"
            mock_db.get_sandbox_by_id.return_value = mock_db_sandbox
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            mock_sandbox_instance.pause = AsyncMock()
            
            await controller.pause_sandbox(sandbox_id="test-sandbox-id")
            
            mock_db.update_sandbox_status.assert_called()

    @pytest.mark.asyncio
    async def test_delete_sandbox(self, mock_config, mock_queue_scheduler, mock_db, mock_sandbox_instance):
        """Test deleting a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            mock_provider_class = MagicMock()
            MockFactory.get_provider.return_value = mock_provider_class
            
            # Setup mock DB to return existing sandbox
            mock_db_sandbox = MagicMock()
            mock_db_sandbox.status = "running"
            mock_db_sandbox.provider_sandbox_id = "e2b-provider-id"
            mock_db.get_sandbox_by_id.return_value = mock_db_sandbox
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            mock_sandbox_instance.kill = AsyncMock()
            
            await controller.delete_sandbox(sandbox_id="test-sandbox-id")
            
            mock_db.delete_sandbox.assert_called()

    @pytest.mark.asyncio
    async def test_run_cmd_success(self, mock_config, mock_queue_scheduler, mock_db, mock_sandbox_instance):
        """Test running a command in a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            mock_sandbox_instance.run_cmd = AsyncMock(return_value="command output")
            
            result = await controller.run_cmd(sandbox_id="test-sandbox-id", command="echo 'hello'")
            
            mock_sandbox_instance.run_cmd.assert_called_once_with("echo 'hello'", background=False)
            assert result == "command output"

    @pytest.mark.asyncio
    async def test_write_file(self, mock_config, mock_queue_scheduler, mock_sandbox_instance):
        """Test writing a file to a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            mock_sandbox_instance.write_file = AsyncMock()
            
            await controller.write_file(
                sandbox_id="test-sandbox-id",
                file_path="/test/file.txt",
                content="test content"
            )
            
            mock_sandbox_instance.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_file(self, mock_config, mock_queue_scheduler, mock_sandbox_instance):
        """Test reading a file from a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            mock_sandbox_instance.read_file = AsyncMock(return_value="file content")
            
            result = await controller.read_file(
                sandbox_id="test-sandbox-id",
                file_path="/test/file.txt"
            )
            
            assert result == "file content"

    @pytest.mark.asyncio
    async def test_schedule_timeout(self, mock_config, mock_queue_scheduler, mock_sandbox_instance):
        """Test scheduling a timeout for a sandbox."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            controller._sandboxes = {"test-sandbox-id": mock_sandbox_instance}
            
            await controller.schedule_timeout(sandbox_id="test-sandbox-id", timeout_seconds=3600)
            
            mock_queue_scheduler.schedule_message.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_config, mock_queue_scheduler):
        """Test shutting down the controller."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory:
            MockFactory.get_provider.return_value = MagicMock()
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            
            controller = SandboxController(mock_config)
            await controller.start()
            await controller.shutdown()
            
            mock_queue_scheduler.stop_consuming.assert_called_once()


class TestSandboxControllerExceptions:
    """Test SandboxController exception handling."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock SandboxConfig."""
        config = MagicMock()
        config.provider_type = "e2b"
        config.e2b_api_key = "test_api_key"
        config.has_queue_provider = True
        config.redis_url = "redis://localhost:6379"
        return config

    @pytest.mark.asyncio
    async def test_sandbox_not_found_exception(self, mock_config):
        """Test that accessing non-existent sandbox raises exception."""
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxFactory") as MockFactory, \
             patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxQueueScheduler") as MockQueue, \
             patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.Sandboxes") as MockDB:
            
            MockFactory.get_provider.return_value = MagicMock()
            MockQueue.return_value = MagicMock(
                setup_consumer=AsyncMock(),
                start_consuming=AsyncMock()
            )
            MockDB.get_sandbox_by_id.return_value = None
            
            from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
            from backend.src.sandbox.sandbox_server.models.exceptions import SandboxNotFoundException
            
            controller = SandboxController(mock_config)
            
            with pytest.raises(SandboxNotFoundException):
                await controller.run_cmd(sandbox_id="nonexistent", command="echo test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
