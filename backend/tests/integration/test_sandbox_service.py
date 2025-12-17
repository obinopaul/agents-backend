import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.src.services.sandbox_service import SandboxService
from backend.src.sandbox.sandbox_server.config import SandboxConfig

@pytest.mark.asyncio
async def test_sandbox_service_lifecycle():
    """
    Test the full lifecycle of the SandboxService with mocked E2B provider.
    Verifies: Initialize -> Create Sandbox -> Run Command -> Shutdown
    """
    
    # Define a dummy class for isinstance check
    class MockCommandResultClass:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""
            self.error = None
            self.exit_code = 0

    # 1. Mock the E2B AsyncSandbox and CommandResult
    with patch("backend.src.sandbox.sandbox_server.sandboxes.e2b.AsyncSandbox") as MockAsyncSandbox, \
         patch("backend.src.sandbox.sandbox_server.sandboxes.e2b.CommandResult", new=MockCommandResultClass):
        
        # Mock the sandbox instance interactions
        mock_sandbox_instance = AsyncMock()
        mock_sandbox_instance.sandbox_id = "mock-e2b-id"
        
        # Mock connection and creation returns - MUST BE ASYNC MOCKS
        MockAsyncSandbox.create = AsyncMock(return_value=mock_sandbox_instance)
        MockAsyncSandbox.connect = AsyncMock(return_value=mock_sandbox_instance)
        MockAsyncSandbox.resume = AsyncMock(return_value=mock_sandbox_instance)
        
        # Mock command execution - Must be a MockCommandResult instance
        mock_cmd_result = MockCommandResultClass()
        mock_cmd_result.stdout = "Hello Sandbox"
        mock_cmd_result.stderr = ""
        mock_cmd_result.error = None
        mock_cmd_result.exit_code = 0
        
        # Ensure 'un' (run) is an AsyncMock so it can be awaited
        mock_sandbox_instance.commands.run = AsyncMock(return_value=mock_cmd_result)
        
        # Mock file operations
        mock_sandbox_instance.files.write.return_value = None
        mock_sandbox_instance.files.read.return_value = "file content"

        # 2. Initialize Service
        service = SandboxService()
        
        # Mock Config to avoid Env errors - Patching where it is USED
        with patch("backend.src.services.sandbox_service.SandboxConfig") as MockConfig:
            mock_conf = MockConfig.return_value
            mock_conf.provider_type = "e2b"
            mock_conf.e2b_api_key = "mock_key"
            mock_conf.e2b_template_id = "mock_template"
            mock_conf.redis_url = "redis://mock"
            
            # Mock Queue Scheduler (avoid Redis connection)
            with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.SandboxQueueScheduler") as MockQueueClass:
                mock_queue_instance = MockQueueClass.return_value
                mock_queue_instance.setup_consumer = AsyncMock()
                mock_queue_instance.start_consuming = AsyncMock()
                mock_queue_instance.stop_consuming = AsyncMock()
                mock_queue_instance.schedule_message = AsyncMock()
                mock_queue_instance.cancel_message = AsyncMock()

                print("\n[Test] Initializing Sandbox Service...")
                await service.initialize()
                assert service._controller is not None
                print("[Test] Service Initialized.")

                # 3. Create Sandbox
                print("[Test] Creating Sandbox...")
                # We need to bypass the database call in Controller.create_sandbox since we don't have a DB here
                # So we verify the provider call directly mocking the controller's internal calls?
                # Better: Mock the DB Sandboxes manager
                with patch("backend.src.sandbox.sandbox_server.lifecycle.sandbox_controller.Sandboxes") as MockDB:
                    MockDB.create_sandbox = AsyncMock()
                    MockDB.get_sandbox_by_id = AsyncMock()
                    MockDB.update_last_activity = AsyncMock()
                    MockDB.delete_sandbox = AsyncMock()
                    MockDB.update_sandbox_status = AsyncMock()
                    # Mock finding the sandbox for connect/run_cmd
                    mock_db_sandbox = MagicMock()
                    mock_db_sandbox.status = "running"
                    mock_db_sandbox.provider_sandbox_id = "mock-e2b-id"
                    MockDB.get_sandbox_by_id.return_value = mock_db_sandbox

                    sandbox_wrapper = await service.get_or_create_sandbox(user_id="test_user")
                    print(f"[Test] Sandbox Created: {sandbox_wrapper.sandbox_id}")
                    
                    # Verify E2B create was called
                    MockAsyncSandbox.create.assert_called_once()

                    # 4. Run Command
                    print("[Test] Running Command...")
                    output = await service.run_cmd(sandbox_wrapper.sandbox_id, "echo 'Hello Sandbox'")
                    print(f"[Test] Command Output: {output}")
                    
                    assert output == "Hello Sandbox"
                    mock_sandbox_instance.commands.run.assert_called_with("echo 'Hello Sandbox'", background=False)

                    # 5. Shutdown
                    print("[Test] Shutting Down...")
                    await service.shutdown()
                    print("[Test] Verification Complete.")

if __name__ == "__main__":
    if asyncio.get_event_loop_policy().__class__.__name__ == 'WindowsProactorEventLoopPolicy':
         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_sandbox_service_lifecycle())
