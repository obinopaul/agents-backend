"""
Tests for the premature streaming stop fix.

Root cause: QueryHandler.handle() finally block unconditionally sent
status_update with status='idle', causing the frontend to set isLoading=false
before the COMPLETE event was processed. This created a race condition where
the ThinkingMessage indicator vanished prematurely during agent mode streaming.

Fix:
  - Backend: Removed send_status_update('idle') from the finally block.
  - Frontend: STATUS_UPDATE handler only sets isLoading=true on 'running',
    ignoring 'idle'. COMPLETE/ERROR/INTERRUPTED are the authoritative signals
    for ending the loading state.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Simulated frontend event state machine
# ---------------------------------------------------------------------------

class FrontendStreamState:
    """
    Simulates the Redux state machine for agent streaming in the frontend.
    Mirrors the logic in use-app-events.tsx handleEvent().
    """

    def __init__(self):
        self.is_loading = False
        self.is_completed = False
        self.is_stopped = False
        self.events_received: List[Dict[str, Any]] = []

    @property
    def thinking_visible(self) -> bool:
        """Whether ThinkingMessage component would render."""
        return self.is_loading and not self.is_stopped and not self.is_completed

    def handle_event(self, event_type: str, content: dict):
        """Process a chat_event exactly as the frontend does."""
        self.events_received.append({"type": event_type, "content": content})

        if event_type == "status_update":
            status = content.get("status")
            if isinstance(status, str) and status == "running":
                self.is_loading = True
            # 'idle' and other statuses are intentionally ignored.
            # COMPLETE/ERROR/INTERRUPTED are the authoritative stream-end signals.

        elif event_type == "complete":
            self.is_completed = True
            self.is_loading = False

        elif event_type == "error":
            self.is_loading = False

        elif event_type == "agent_response_interrupted":
            self.is_loading = False
            self.is_stopped = True


# ---------------------------------------------------------------------------
# Tests: FrontendStreamState (simulated frontend)
# ---------------------------------------------------------------------------

class TestFrontendStreamState:
    """Test the frontend event state machine with the fix applied."""

    def test_status_running_sets_loading(self):
        """STATUS_UPDATE with status='running' should enable loading."""
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})
        assert state.is_loading is True
        assert state.thinking_visible is True

    def test_status_idle_does_not_clear_loading(self):
        """
        STATUS_UPDATE with status='idle' must NOT clear loading.
        This was the root cause of the premature streaming stop.
        """
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})
        assert state.is_loading is True

        # Idle should be ignored
        state.handle_event("status_update", {"status": "idle"})
        assert state.is_loading is True
        assert state.thinking_visible is True

    def test_complete_clears_loading(self):
        """COMPLETE event should authoritatively end loading."""
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})
        state.handle_event("complete", {"message": "done"})
        assert state.is_loading is False
        assert state.is_completed is True
        assert state.thinking_visible is False

    def test_error_clears_loading(self):
        """ERROR event should clear loading even without COMPLETE."""
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})
        state.handle_event("error", {"message": "something failed"})
        assert state.is_loading is False
        assert state.thinking_visible is False

    def test_interrupted_clears_loading(self):
        """AGENT_RESPONSE_INTERRUPTED should clear loading and set stopped."""
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})
        state.handle_event("agent_response_interrupted", {})
        assert state.is_loading is False
        assert state.is_stopped is True
        assert state.thinking_visible is False

    def test_full_agent_session_no_premature_stop(self):
        """
        Simulate a complete agent session with the race condition scenario:
        running → stream events → complete → idle (from finally block).

        Before the fix: idle would arrive and kill ThinkingMessage.
        After the fix: idle is ignored, COMPLETE is authoritative.
        """
        state = FrontendStreamState()

        # 1. Backend sends running status
        state.handle_event("status_update", {"status": "running"})
        assert state.thinking_visible is True

        # 2. Agent streams content events
        state.handle_event("agent_response", {"content": "Let me search..."})
        assert state.thinking_visible is True  # Still streaming

        state.handle_event("tool_call", {"tool": "web_search", "args": {}})
        assert state.thinking_visible is True

        state.handle_event("tool_result", {"result": "search results..."})
        assert state.thinking_visible is True

        state.handle_event("agent_response", {"content": "Based on results..."})
        assert state.thinking_visible is True

        # 3. Agent completes
        state.handle_event("complete", {"message": "Stream completed"})
        assert state.thinking_visible is False
        assert state.is_completed is True

        # 4. Finally block sends idle (now harmless)
        state.handle_event("status_update", {"status": "idle"})
        assert state.is_loading is False  # Already false from COMPLETE
        assert state.is_completed is True

    def test_race_condition_idle_before_complete(self):
        """
        Simulate the exact race condition that caused the bug:
        idle arrives BEFORE complete due to async Socket.IO timing.

        Before fix: ThinkingMessage vanishes at step 3, user sees premature stop.
        After fix: idle is ignored, ThinkingMessage stays until COMPLETE.
        """
        state = FrontendStreamState()

        # 1. Start streaming
        state.handle_event("status_update", {"status": "running"})
        assert state.thinking_visible is True

        # 2. Some events stream in
        state.handle_event("agent_response", {"content": "Processing..."})
        assert state.thinking_visible is True

        # 3. RACE CONDITION: idle arrives before complete
        state.handle_event("status_update", {"status": "idle"})
        # CRITICAL: ThinkingMessage must STILL be visible!
        assert state.thinking_visible is True, \
            "ThinkingMessage vanished on idle - race condition NOT fixed!"

        # 4. COMPLETE arrives (the authoritative signal)
        state.handle_event("complete", {"message": "done"})
        assert state.thinking_visible is False

    def test_billing_failure_path(self):
        """
        Billing check failure sends ERROR then IDLE.
        ERROR should clear loading; idle is harmless.
        """
        state = FrontendStreamState()

        # Start
        state.handle_event("status_update", {"status": "running"})
        assert state.is_loading is True

        # Billing error
        state.handle_event("error", {"message": "Insufficient credits"})
        assert state.is_loading is False

        # Idle follows (harmless)
        state.handle_event("status_update", {"status": "idle"})
        assert state.is_loading is False

    def test_unknown_status_ignored(self):
        """Unknown status strings should not affect loading state."""
        state = FrontendStreamState()

        state.handle_event("status_update", {"status": "running"})
        assert state.is_loading is True

        # Unknown statuses should not change loading
        for status in ["processing", "thinking", "queued", "", None]:
            state.handle_event("status_update", {"status": status} if status else {})
            assert state.is_loading is True, \
                f"Loading was changed by unknown status: {status!r}"


# ---------------------------------------------------------------------------
# Tests: Backend query_handler finally block
# ---------------------------------------------------------------------------

class TestQueryHandlerFinallyBlock:
    """
    Test that the finally block in QueryHandler.handle() does NOT send
    status_update with status='idle'.
    """

    def test_finally_block_no_idle_status(self):
        """
         Verify that reading the query_handler source confirms no idle
         in the finally block.
        """
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "common", "socketio", "command", "query_handler.py"
        )
        handler_path = os.path.normpath(handler_path)

        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the finally block
        finally_idx = source.rfind("finally:")
        assert finally_idx != -1, "Could not find 'finally:' block"

        # Get content after the finally block (until end of method or next def)
        after_finally = source[finally_idx:]

        # Find the end of the finally block (next unindented line or next method)
        lines = after_finally.split("\n")
        finally_body = []
        for i, line in enumerate(lines):
            if i == 0:
                continue  # skip "finally:" line
            # Empty lines are ok
            if line.strip() == "":
                finally_body.append(line)
                continue
            # If indented (part of finally body), include it
            if line.startswith("        ") or line.startswith("\t\t"):
                finally_body.append(line)
            else:
                break

        finally_content = "\n".join(finally_body)

        # The finally block should NOT contain send_status_update calls
        # (comments mentioning 'idle' are fine — we only care about actual code)
        assert "send_status_update" not in finally_content, \
            f"Finally block still contains send_status_update!\n{finally_content}"

    def test_finally_block_still_clears_task(self):
        """
        Verify set_task_running is still called in the finally block
        to properly clean up task state.
        """
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "backend", "common", "socketio", "command", "query_handler.py"
        )
        handler_path = os.path.normpath(handler_path)

        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        finally_idx = source.rfind("finally:")
        assert finally_idx != -1

        after_finally = source[finally_idx:finally_idx + 500]

        assert "set_task_running" in after_finally, \
            "Finally block must still call set_task_running to clean up task state"


# ---------------------------------------------------------------------------
# Tests: Frontend STATUS_UPDATE handler source verification
# ---------------------------------------------------------------------------

class TestFrontendStatusUpdateHandler:
    """
    Verify the frontend STATUS_UPDATE handler source code matches
    the expected fix pattern.
    """

    def test_status_update_handler_no_idle_setloading_false(self):
        """
        The STATUS_UPDATE handler in use-app-events.tsx should NOT call
        setLoading(false) or setLoading(status === 'running') which would
        evaluate to false for 'idle'.
        """
        import os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..",
            "frontend", "src", "hooks", "use-app-events.tsx"
        )
        handler_path = os.path.normpath(handler_path)

        with open(handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find STATUS_UPDATE case
        status_idx = source.find("case AgentEvent.STATUS_UPDATE:")
        assert status_idx != -1, "Could not find STATUS_UPDATE handler"

        # Get the handler body (until next case or break)
        handler_body = source[status_idx:status_idx + 1000]
        # Trim to next 'case' or 'default:'
        for marker in ["case AgentEvent.", "default:"]:
            next_case = handler_body.find(marker, 30)  # skip our own case
            if next_case != -1:
                handler_body = handler_body[:next_case]

        # Should NOT contain the old pattern that sets loading to false on idle
        assert "setLoading(status ===" not in handler_body or "setLoading(true)" in handler_body, \
            "Old pattern 'setLoading(status === ...)' still present without setLoading(true) guard"

        # Should contain the guard: if (status === 'running') { setLoading(true) }
        # Note: frontend may use single or double quotes
        has_running_check = ("status === 'running'" in handler_body or
                            'status === "running"' in handler_body)
        assert has_running_check, \
            f"Running status check not found in handler:\n{handler_body}"
        assert "setLoading(true)" in handler_body, \
            f"setLoading(true) not found in STATUS_UPDATE handler:\n{handler_body}"


# ---------------------------------------------------------------------------
# Integration test: Event sequence simulation
# ---------------------------------------------------------------------------

class TestEventSequenceIntegration:
    """Integration tests simulating real event sequences."""

    def test_long_agent_session_stays_visible(self):
        """
        Long-running agent sessions with many nodes should keep
        ThinkingMessage visible throughout.
        """
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})

        # Simulate 10 node transitions (multi-node agent workflow)
        for i in range(10):
            state.handle_event("agent_response", {"content": f"Step {i}..."})
            state.handle_event("tool_call", {"tool": f"tool_{i}"})
            state.handle_event("tool_result", {"result": f"result_{i}"})

            # ThinkingMessage must remain visible throughout
            assert state.thinking_visible is True, \
                f"ThinkingMessage vanished at step {i}!"

        # Only COMPLETE should end visibility
        state.handle_event("complete", {"message": "done"})
        assert state.thinking_visible is False

    def test_multiple_status_updates_during_stream(self):
        """
        Internal status updates (processing, sandbox_ready) should
        not affect loading state.
        """
        state = FrontendStreamState()
        state.handle_event("status_update", {"status": "running"})

        # Various internal status events
        state.handle_event("status_update", {"status_type": "processing"})
        assert state.thinking_visible is True

        state.handle_event("status_update", {"status_type": "sandbox_ready"})
        assert state.thinking_visible is True

        state.handle_event("status_update", {"status_type": "complete"})
        assert state.thinking_visible is True  # status_type != status

        state.handle_event("complete", {"message": "done"})
        assert state.thinking_visible is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
