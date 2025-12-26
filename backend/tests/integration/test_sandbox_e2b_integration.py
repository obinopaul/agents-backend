"""
Integration tests for E2B Sandbox.

These tests require:
- Valid E2B_API_KEY environment variable
- Internet access
- Redis running (for queue operations)

WARNING: These tests will create real sandboxes and consume API credits.
"""

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock


# Skip all tests if E2B_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("E2B_API_KEY"),
    reason="E2B_API_KEY environment variable not set"
)


class TestE2BSandboxIntegration:
    """Integration tests for E2B sandbox operations."""

    @pytest.fixture
    async def sandbox_controller(self):
        """Create a real sandbox controller for testing."""
        from backend.src.sandbox.sandbox_server.config import SandboxConfig
        from backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller import SandboxController
        
        # Mock the queue scheduler to avoid Redis dependency
        with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxQueueScheduler") as MockQueue:
            mock_queue = MagicMock()
            mock_queue.setup_consumer = AsyncMock()
            mock_queue.start_consuming = AsyncMock()
            mock_queue.stop_consuming = AsyncMock()
            mock_queue.schedule_message = AsyncMock()
            mock_queue.cancel_message = AsyncMock()
            MockQueue.return_value = mock_queue
            
            # Create config with E2B settings
            with patch("backend.core.conf.settings") as mock_settings:
                mock_settings.REDIS_HOST = "localhost"
                mock_settings.REDIS_PORT = 6379
                mock_settings.REDIS_PASSWORD = ""
                mock_settings.REDIS_DATABASE = 0
                mock_settings.E2B_API_KEY = os.getenv("E2B_API_KEY")
                mock_settings.E2B_TEMPLATE_ID = "base"
                
                config = SandboxConfig()
                controller = SandboxController(config)
                await controller.start()
                
                yield controller
                
                # Cleanup
                await controller.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_create_sandbox(self, sandbox_controller):
        """Test creating an E2B sandbox."""
        sandbox = await sandbox_controller.create_sandbox(user_id="test-user")
        
        assert sandbox is not None
        assert sandbox.sandbox_id is not None
        
        # Clean up
        await sandbox_controller.delete_sandbox(sandbox.sandbox_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_run_command(self, sandbox_controller):
        """Test running a command in E2B sandbox."""
        sandbox = await sandbox_controller.create_sandbox(user_id="test-user")
        
        try:
            # Run a simple command
            result = await sandbox_controller.run_cmd(
                sandbox_id=sandbox.sandbox_id,
                command="echo 'Hello E2B'"
            )
            
            assert "Hello E2B" in result
        finally:
            await sandbox_controller.delete_sandbox(sandbox.sandbox_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_file_operations(self, sandbox_controller):
        """Test file operations in E2B sandbox."""
        sandbox = await sandbox_controller.create_sandbox(user_id="test-user")
        
        try:
            # Write a file
            await sandbox_controller.write_file(
                sandbox_id=sandbox.sandbox_id,
                file_path="/tmp/test_file.txt",
                content="Test content from integration test"
            )
            
            # Read the file back
            content = await sandbox_controller.read_file(
                sandbox_id=sandbox.sandbox_id,
                file_path="/tmp/test_file.txt"
            )
            
            assert "Test content from integration test" in content
        finally:
            await sandbox_controller.delete_sandbox(sandbox.sandbox_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_e2b_pause_resume(self, sandbox_controller):
        """Test pausing and resuming an E2B sandbox."""
        sandbox = await sandbox_controller.create_sandbox(user_id="test-user")
        
        try:
            # Pause the sandbox
            await sandbox_controller.pause_sandbox(sandbox.sandbox_id)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Resume the sandbox
            resumed = await sandbox_controller.connect(sandbox.sandbox_id)
            
            assert resumed is not None
            
            # Run a command to verify it's working
            result = await sandbox_controller.run_cmd(
                sandbox_id=sandbox.sandbox_id,
                command="echo 'Still alive'"
            )
            
            assert "Still alive" in result
        finally:
            await sandbox_controller.delete_sandbox(sandbox.sandbox_id)

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_create_directory(self, sandbox_controller):
        """Test creating a directory in E2B sandbox."""
        sandbox = await sandbox_controller.create_sandbox(user_id="test-user")
        
        try:
            # Create a directory
            await sandbox_controller.create_directory(
                sandbox_id=sandbox.sandbox_id,
                directory_path="/tmp/test_directory",
                exist_ok=True
            )
            
            # Verify directory exists by running ls
            result = await sandbox_controller.run_cmd(
                sandbox_id=sandbox.sandbox_id,
                command="ls -la /tmp/test_directory"
            )
            
            assert "test_directory" in result or "total" in result
        finally:
            await sandbox_controller.delete_sandbox(sandbox.sandbox_id)


class TestE2BSandboxProvider:
    """Test E2BSandbox provider directly."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_provider_create(self):
        """Test E2B provider create method."""
        from backend.src.sandbox.sandbox_server.sandboxes.e2b import E2BSandbox
        
        api_key = os.getenv("E2B_API_KEY")
        if not api_key:
            pytest.skip("E2B_API_KEY not set")
        
        sandbox = await E2BSandbox.create(
            api_key=api_key,
            template_id="base"
        )
        
        try:
            assert sandbox is not None
            assert sandbox.sandbox_id is not None
        finally:
            await sandbox.kill()

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_e2b_provider_run_cmd(self):
        """Test E2B provider command execution."""
        from backend.src.sandbox.sandbox_server.sandboxes.e2b import E2BSandbox
        
        api_key = os.getenv("E2B_API_KEY")
        if not api_key:
            pytest.skip("E2B_API_KEY not set")
        
        sandbox = await E2BSandbox.create(
            api_key=api_key,
            template_id="base"
        )
        
        try:
            result = await sandbox.run_cmd("echo 'test'")
            assert "test" in result
        finally:
            await sandbox.kill()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=300"])
