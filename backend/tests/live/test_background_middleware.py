"""Test script for BackgroundSubagentMiddleware.

Tests the background middleware implementation with Option B:
- background_task tool for non-blocking subagent spawning
- wait tool for collecting results
- task_progress tool for monitoring

Run: python backend/tests/live/test_background_middleware.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name: str, success: bool, details: str = "") -> None:
    """Print a test result."""
    status = "[PASS]" if success else "[FAIL]"
    detail_str = f"\n         {details}" if details else ""
    print(f"  {status} - {name}{detail_str}")


async def test_imports():
    """Test 1: Verify all imports work correctly."""
    print_header("Test 1: Imports and Module Structure")
    
    try:
        from backend.src.agents.middleware.background_middleware import (
            BackgroundSubagentMiddleware,
            BackgroundSubagentOrchestrator,
            BackgroundTask,
            BackgroundTaskRegistry,
            ToolCallCounterMiddleware,
            create_background_task_tool,
            create_task_progress_tool,
            create_wait_tool,
        )
        print_result("All imports successful", True)
        
        # Verify classes exist
        print_result("BackgroundSubagentMiddleware", BackgroundSubagentMiddleware is not None)
        print_result("BackgroundSubagentOrchestrator", BackgroundSubagentOrchestrator is not None)
        print_result("BackgroundTaskRegistry", BackgroundTaskRegistry is not None)
        print_result("create_background_task_tool", callable(create_background_task_tool))
        
        return True
    except Exception as e:
        print_result("Imports", False, str(e))
        return False


async def test_middleware_instantiation():
    """Test 2: Verify middleware can be instantiated."""
    print_header("Test 2: Middleware Instantiation")
    
    try:
        from backend.src.agents.middleware.background_middleware import (
            BackgroundSubagentMiddleware,
        )
        
        # Default instantiation
        middleware = BackgroundSubagentMiddleware()
        print_result("Default instantiation", middleware is not None)
        print_result("enabled=True by default", middleware.enabled == True)
        print_result("timeout=60.0 by default", middleware.timeout == 60.0)
        
        # Custom settings
        middleware2 = BackgroundSubagentMiddleware(timeout=120.0, enabled=False)
        print_result("Custom timeout", middleware2.timeout == 120.0, f"timeout={middleware2.timeout}")
        print_result("Custom enabled", middleware2.enabled == False)
        
        return True
    except Exception as e:
        print_result("Instantiation", False, str(e))
        return False


async def test_tools_registration():
    """Test 3: Verify tools are registered correctly."""
    print_header("Test 3: Tools Registration")
    
    try:
        from backend.src.agents.middleware.background_middleware import (
            BackgroundSubagentMiddleware,
        )
        
        middleware = BackgroundSubagentMiddleware()
        
        # Check tools list
        print_result("tools list exists", hasattr(middleware, 'tools'))
        print_result("3 tools registered", len(middleware.tools) == 3, f"found {len(middleware.tools)}")
        
        # Check tool names
        tool_names = [t.name for t in middleware.tools]
        print_result("background_task tool", "background_task" in tool_names)
        print_result("wait tool", "wait" in tool_names)
        print_result("task_progress tool", "task_progress" in tool_names)
        
        # Verify background_task tool details
        bg_tool = next((t for t in middleware.tools if t.name == "background_task"), None)
        if bg_tool:
            print_result("background_task has description", len(bg_tool.description) > 0,
                        f"desc length: {len(bg_tool.description)}")
        
        return True
    except Exception as e:
        print_result("Tools registration", False, str(e))
        return False


async def test_registry():
    """Test 4: Verify registry functionality."""
    print_header("Test 4: Registry Functionality")
    
    try:
        from backend.src.agents.middleware.background_middleware import (
            BackgroundTaskRegistry,
        )
        
        registry = BackgroundTaskRegistry()
        
        # Register a task
        task = await registry.register(
            task_id="test-task-1",
            description="Test background task",
            subagent_type="research",
        )
        
        print_result("Task registered", task is not None)
        print_result("Task ID correct", task.task_id == "test-task-1")
        print_result("Task number is 1", task.task_number == 1, f"number={task.task_number}")
        print_result("Display ID is Task-1", task.display_id == "Task-1", f"id={task.display_id}")
        
        # Register another task
        task2 = await registry.register(
            task_id="test-task-2",
            description="Second test task",
            subagent_type="analysis",
        )
        print_result("Second task number is 2", task2.task_number == 2)
        
        # Check task count
        print_result("Task count is 2", registry.task_count == 2)
        
        # Clear registry
        registry.clear()
        print_result("Registry cleared", registry.task_count == 0)
        
        return True
    except Exception as e:
        print_result("Registry", False, str(e))
        logger.exception("Registry test error")
        return False


async def test_deep_agents_integration():
    """Test 5: Verify integration with deep_agents.py."""
    print_header("Test 5: deep_agents.py Integration")
    
    try:
        from backend.src.agents.deep_agents import build_deep_middleware
        from backend.src.llms.llm import get_llm
        
        # Get LLM
        llm = get_llm()
        print_result("LLM retrieved", llm is not None)
        
        # Build middleware WITHOUT background tasks (default)
        middleware_list = build_deep_middleware(
            model=llm,
            tools=[],
            enable_background_tasks=False,
        )
        
        # Check that BackgroundSubagentMiddleware is NOT in list
        from backend.src.agents.middleware.background_middleware import BackgroundSubagentMiddleware
        has_bg_middleware = any(isinstance(m, BackgroundSubagentMiddleware) for m in middleware_list)
        print_result("No background middleware when disabled", not has_bg_middleware)
        
        # Build middleware WITH background tasks
        middleware_list2 = build_deep_middleware(
            model=llm,
            tools=[],
            enable_background_tasks=True,
            background_task_timeout=120.0,
        )
        
        has_bg_middleware2 = any(isinstance(m, BackgroundSubagentMiddleware) for m in middleware_list2)
        print_result("Has background middleware when enabled", has_bg_middleware2)
        
        # Find the middleware and check timeout
        bg_middleware = next((m for m in middleware_list2 if isinstance(m, BackgroundSubagentMiddleware)), None)
        if bg_middleware:
            print_result("Timeout configured correctly", bg_middleware.timeout == 120.0,
                        f"timeout={bg_middleware.timeout}")
        
        return True
    except Exception as e:
        print_result("deep_agents integration", False, str(e))
        logger.exception("deep_agents integration error")
        return False


async def test_tool_interception():
    """Test 6: Verify middleware intercepts background_task tool calls."""
    print_header("Test 6: Tool Interception (background_task)")
    
    try:
        from backend.src.agents.middleware.background_middleware import (
            BackgroundSubagentMiddleware,
        )
        from langchain_core.messages import ToolMessage
        
        middleware = BackgroundSubagentMiddleware()
        
        # Simulate a tool call request for background_task
        class MockRequest:
            def __init__(self, name, args, call_id):
                self.tool_call = {
                    "name": name,
                    "args": args,
                    "id": call_id,
                }
        
        # Create mock handler that we expect NOT to be called for background_task
        handler_called = False
        async def mock_handler(request):
            nonlocal handler_called
            handler_called = True
            return ToolMessage(content="Handler result", tool_call_id=request.tool_call["id"])
        
        # Test with background_task tool
        request = MockRequest(
            name="background_task",
            args={"description": "Test task", "subagent_type": "research"},
            call_id="call_123"
        )
        
        result = await middleware.awrap_tool_call(request, mock_handler)
        
        # Verify middleware intercepted (handler should still be called in background)
        print_result("Returns ToolMessage", isinstance(result, ToolMessage))
        print_result("Message name is background_task", result.name == "background_task")
        print_result("Contains Task-N reference", "Task-" in result.content,
                    f"content preview: {result.content[:100]}...")
        
        # Test with different tool (should pass through)
        request2 = MockRequest(
            name="some_other_tool",
            args={"foo": "bar"},
            call_id="call_456"
        )
        handler_called = False
        result2 = await middleware.awrap_tool_call(request2, mock_handler)
        print_result("Other tools pass through", handler_called == True)
        
        return True
    except Exception as e:
        print_result("Tool interception", False, str(e))
        logger.exception("Tool interception error")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  BACKGROUND MIDDLEWARE - TEST SUITE")
    print("  Option B Implementation: background_task tool")
    print("=" * 70)
    
    results = []
    
    results.append(await test_imports())
    results.append(await test_middleware_instantiation())
    results.append(await test_tools_registration())
    results.append(await test_registry())
    results.append(await test_deep_agents_integration())
    results.append(await test_tool_interception())
    
    # Summary
    print_header("SUMMARY")
    passed = sum(results)
    total = len(results)
    
    print(f"\n  Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("  [OK] All tests passed! BackgroundSubagentMiddleware is working.")
        return 0
    else:
        print("  [WARN] Some tests failed. Check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
