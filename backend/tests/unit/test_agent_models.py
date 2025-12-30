#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Unit Tests for Agent Models Module

Tests the structured Pydantic models and dataclasses for AG-UI Protocol:
- Content blocks (TextBlock, ImageBlock, etc.)
- Reasoning state tracking
- Tool call models and AG-UI event generation
- Message models

Run:
    python -m pytest backend/tests/unit/test_agent_models.py -v
    
Or directly:
    python backend/tests/unit/test_agent_models.py
"""

import json
import sys
import os
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import pytest

from backend.app.agent.models import (
    # Enums
    ContentBlockType,
    MessageRole,
    # Content Blocks
    TextBlock,
    ImageBlock,
    AudioBlock,
    FileBlock,
    ReasoningBlock,
    # State tracking
    ReasoningState,
    ToolCallState,
    # Tool models
    ToolCall,
    ToolResult,
    # Message models
    AgentMessage,
    ChatMessage,
    # Helpers
    make_ag_ui_event,
    extract_reasoning_from_content_blocks,
    # HITL models
    HITLDecisionType,
    ActionRequest,
    ReviewConfig,
    HITLDecision,
    HITLRequest,
    HITLResponse,
    HITLState,
    create_hitl_interrupt_event,
)


# =============================================================================
# Content Block Tests
# =============================================================================

class TestTextBlock:
    """Tests for TextBlock model."""
    
    def test_create_text_block(self):
        block = TextBlock(text="Hello, world!")
        assert block.type == "text"
        assert block.text == "Hello, world!"
    
    def test_text_block_serialization(self):
        block = TextBlock(text="Test content")
        data = block.model_dump()
        assert data == {"type": "text", "text": "Test content"}


class TestImageBlock:
    """Tests for ImageBlock model."""
    
    def test_create_image_block_with_url(self):
        block = ImageBlock(url="https://example.com/image.jpg")
        assert block.type == "image"
        assert block.url == "https://example.com/image.jpg"
        assert block.data is None
    
    def test_create_image_block_with_base64(self):
        block = ImageBlock(
            data="base64encodeddata",
            mime_type="image/png"
        )
        assert block.type == "image"
        assert block.data == "base64encodeddata"
        assert block.mime_type == "image/png"
    
    def test_to_langchain_format_url(self):
        block = ImageBlock(url="https://example.com/photo.jpg")
        lc_format = block.to_langchain_format()
        assert lc_format == {"type": "image", "url": "https://example.com/photo.jpg"}
    
    def test_to_langchain_format_base64(self):
        block = ImageBlock(data="abc123", mime_type="image/jpeg")
        lc_format = block.to_langchain_format()
        assert lc_format == {
            "type": "image",
            "data": "abc123",
            "mime_type": "image/jpeg"
        }


class TestAudioBlock:
    """Tests for AudioBlock model."""
    
    def test_create_audio_block_with_url(self):
        block = AudioBlock(url="https://example.com/audio.mp3")
        assert block.type == "audio"
        assert block.url == "https://example.com/audio.mp3"


class TestReasoningBlock:
    """Tests for ReasoningBlock model."""
    
    def test_create_reasoning_block(self):
        block = ReasoningBlock(reasoning="Let me think about this...")
        assert block.type == "reasoning"
        assert block.reasoning == "Let me think about this..."
    
    def test_reasoning_block_with_signature(self):
        block = ReasoningBlock(
            reasoning="Deep thoughts...",
            signature="sig123"
        )
        assert block.signature == "sig123"


# =============================================================================
# Reasoning State Tests
# =============================================================================

class TestReasoningState:
    """Tests for ReasoningState dataclass."""
    
    def test_initial_state(self):
        state = ReasoningState()
        assert state.message_id is None
        assert state.is_active is False
    
    def test_start_reasoning(self):
        state = ReasoningState()
        msg_id = state.start_reasoning()
        
        assert msg_id is not None
        assert msg_id.startswith("reasoning-")
        assert state.is_active is True
        assert state.message_id == msg_id
    
    def test_end_reasoning(self):
        state = ReasoningState()
        msg_id = state.start_reasoning()
        
        returned_id = state.end_reasoning()
        
        assert returned_id == msg_id
        assert state.is_active is False
        assert state.message_id is None
    
    def test_multiple_cycles(self):
        state = ReasoningState()
        
        # First cycle
        id1 = state.start_reasoning()
        state.end_reasoning()
        
        # Second cycle
        id2 = state.start_reasoning()
        state.end_reasoning()
        
        # IDs should be different
        assert id1 != id2


# =============================================================================
# Tool Call Tests
# =============================================================================

class TestToolCall:
    """Tests for ToolCall model."""
    
    def test_create_tool_call(self):
        tc = ToolCall(
            tool_call_id="call_123",
            tool_name="web_search",
            tool_input={"query": "weather in London"}
        )
        assert tc.tool_call_id == "call_123"
        assert tc.tool_name == "web_search"
        assert tc.tool_input == {"query": "weather in London"}
    
    def test_from_langchain(self):
        lc_tool_call = {
            "id": "call_abc",
            "name": "calculate",
            "args": {"expression": "2 + 2"}
        }
        tc = ToolCall.from_langchain(lc_tool_call)
        
        assert tc.tool_call_id == "call_abc"
        assert tc.tool_name == "calculate"
        assert tc.tool_input == {"expression": "2 + 2"}
    
    def test_to_ag_ui_start_event(self):
        tc = ToolCall(
            tool_call_id="call_xyz",
            tool_name="file_read"
        )
        event = tc.to_ag_ui_start_event()
        
        assert event == {
            "toolCallId": "call_xyz",
            "toolCallName": "file_read"
        }
    
    def test_to_ag_ui_args_event(self):
        tc = ToolCall(
            tool_call_id="call_789",
            tool_name="search"
        )
        event = tc.to_ag_ui_args_event('{"query": "test"}')
        
        assert event == {
            "toolCallId": "call_789",
            "delta": '{"query": "test"}'
        }
    
    def test_to_ag_ui_end_event(self):
        tc = ToolCall(
            tool_call_id="call_end",
            tool_name="done"
        )
        event = tc.to_ag_ui_end_event()
        
        assert event == {"toolCallId": "call_end"}


class TestToolResult:
    """Tests for ToolResult model."""
    
    def test_create_tool_result(self):
        tr = ToolResult(
            tool_call_id="call_123",
            tool_name="web_search",
            output="Search results here..."
        )
        assert tr.tool_call_id == "call_123"
        assert tr.output == "Search results here..."
        assert tr.is_error is False
    
    def test_to_ag_ui_event(self):
        tr = ToolResult(
            tool_call_id="call_456",
            tool_name="calculate",
            output="42"
        )
        event = tr.to_ag_ui_event()
        
        assert event == {
            "toolCallId": "call_456",
            "content": "42"
        }


class TestToolCallState:
    """Tests for ToolCallState dataclass."""
    
    def test_initial_state(self):
        state = ToolCallState()
        assert len(state.active_calls) == 0
        assert len(state.completed_calls) == 0
    
    def test_track_tool_call_lifecycle(self):
        state = ToolCallState()
        tc = ToolCall(
            tool_call_id="call_abc",
            tool_name="search"
        )
        
        # Start
        state.start_tool_call(tc)
        assert state.is_active("call_abc")
        
        # Append args
        state.append_args("call_abc", '{"query":')
        state.append_args("call_abc", '"test"}')
        assert state.args_buffers["call_abc"] == '{"query":"test"}'
        
        # Complete
        completed = state.complete_tool_call("call_abc")
        assert completed is not None
        assert completed.tool_input == '{"query":"test"}'
        assert not state.is_active("call_abc")
        assert "call_abc" in state.completed_calls


# =============================================================================
# Message Model Tests
# =============================================================================

class TestAgentMessage:
    """Tests for AgentMessage model."""
    
    def test_create_simple_message(self):
        msg = AgentMessage(role=MessageRole.USER, content="Hello!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
    
    def test_create_multimodal_message_with_blocks(self):
        msg = AgentMessage(
            role=MessageRole.USER,
            content=[
                TextBlock(text="What's in this image?"),
                ImageBlock(url="https://example.com/img.jpg")
            ]
        )
        assert len(msg.content) == 2
    
    def test_to_langchain_format_simple(self):
        msg = AgentMessage(role=MessageRole.USER, content="Test")
        lc = msg.to_langchain_format()
        
        assert lc == {"role": "user", "content": "Test"}
    
    def test_to_langchain_format_multimodal(self):
        msg = AgentMessage(
            role=MessageRole.USER,
            content=[
                TextBlock(text="Describe this"),
                ImageBlock(url="https://example.com/pic.jpg")
            ]
        )
        lc = msg.to_langchain_format()
        
        assert lc["role"] == "user"
        assert len(lc["content"]) == 2
        assert lc["content"][0] == {"type": "text", "text": "Describe this"}
        assert lc["content"][1] == {"type": "image", "url": "https://example.com/pic.jpg"}


class TestChatMessage:
    """Tests for ChatMessage (alias of AgentMessage)."""
    
    def test_chat_message_is_agent_message(self):
        msg = ChatMessage(role=MessageRole.ASSISTANT, content="Hi there!")
        assert isinstance(msg, AgentMessage)


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestMakeAgUiEvent:
    """Tests for make_ag_ui_event helper."""
    
    def test_basic_event(self):
        event = make_ag_ui_event("message", {"content": "Hello"})
        assert event == 'event: message\ndata: {"content": "Hello"}\n\n'
    
    def test_tool_call_start_event(self):
        event = make_ag_ui_event("tool_call_start", {
            "toolCallId": "call_123",
            "toolCallName": "search"
        })
        assert "event: tool_call_start" in event
        assert '"toolCallId": "call_123"' in event
        assert '"toolCallName": "search"' in event


class TestExtractReasoningFromContentBlocks:
    """Tests for extract_reasoning_from_content_blocks helper."""
    
    def test_extract_reasoning(self):
        blocks = [
            {"type": "reasoning", "reasoning": "Let me think..."},
            {"type": "text", "text": "The answer is 42."}
        ]
        reasoning = extract_reasoning_from_content_blocks(blocks)
        assert reasoning == "Let me think..."
    
    def test_extract_thinking_variant(self):
        blocks = [
            {"type": "reasoning", "thinking": "Hmm, interesting..."},
        ]
        reasoning = extract_reasoning_from_content_blocks(blocks)
        assert reasoning == "Hmm, interesting..."
    
    def test_no_reasoning(self):
        blocks = [
            {"type": "text", "text": "Just text here"}
        ]
        reasoning = extract_reasoning_from_content_blocks(blocks)
        assert reasoning is None
    
    def test_empty_blocks(self):
        reasoning = extract_reasoning_from_content_blocks([])
        assert reasoning is None


# =============================================================================
# Human-in-the-Loop (HITL) Model Tests
# =============================================================================

class TestHITLDecisionType:
    """Tests for HITLDecisionType enum."""
    
    def test_decision_types(self):
        assert HITLDecisionType.APPROVE.value == "approve"
        assert HITLDecisionType.EDIT.value == "edit"
        assert HITLDecisionType.REJECT.value == "reject"
        assert HITLDecisionType.ACCEPTED.value == "accepted"
        assert HITLDecisionType.FEEDBACK.value == "feedback"


class TestActionRequest:
    """Tests for ActionRequest model."""
    
    def test_create_action_request(self):
        ar = ActionRequest(
            name="web_search",
            arguments={"query": "test query"}
        )
        assert ar.name == "web_search"
        assert ar.arguments == {"query": "test query"}
        assert ar.action_id.startswith("action-")
    
    def test_to_ag_ui_format(self):
        ar = ActionRequest(
            name="execute_sql",
            arguments={"query": "SELECT * FROM users"},
            description="Execute SQL query"
        )
        data = ar.to_ag_ui_format()
        assert data["name"] == "execute_sql"
        assert data["arguments"] == {"query": "SELECT * FROM users"}
        assert data["description"] == "Execute SQL query"
        assert "actionId" in data


class TestReviewConfig:
    """Tests for ReviewConfig model."""
    
    def test_create_review_config_defaults(self):
        rc = ReviewConfig(action_name="web_search")
        assert rc.action_name == "web_search"
        assert HITLDecisionType.APPROVE in rc.allowed_decisions
        assert HITLDecisionType.REJECT in rc.allowed_decisions
        assert rc.requires_reason is False
    
    def test_create_review_config_custom(self):
        rc = ReviewConfig(
            action_name="execute_sql",
            allowed_decisions=[HITLDecisionType.APPROVE, HITLDecisionType.REJECT],
            requires_reason=True,
            editable_fields=["query"]
        )
        assert rc.requires_reason is True
        assert rc.editable_fields == ["query"]
        assert len(rc.allowed_decisions) == 2
    
    def test_to_ag_ui_format(self):
        rc = ReviewConfig(
            action_name="send_email",
            allowed_decisions=[HITLDecisionType.APPROVE, HITLDecisionType.EDIT, HITLDecisionType.REJECT]
        )
        data = rc.to_ag_ui_format()
        assert data["actionName"] == "send_email"
        assert "approve" in data["allowedDecisions"]
        assert "edit" in data["allowedDecisions"]
        assert "reject" in data["allowedDecisions"]


class TestHITLDecision:
    """Tests for HITLDecision model."""
    
    def test_create_approve_decision(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.APPROVE
        )
        assert decision.decision_type == HITLDecisionType.APPROVE
        assert decision.edited_arguments is None
    
    def test_create_edit_decision(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.EDIT,
            edited_arguments={"query": "modified query"}
        )
        assert decision.decision_type == HITLDecisionType.EDIT
        assert decision.edited_arguments == {"query": "modified query"}
    
    def test_create_reject_decision(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.REJECT,
            reason="This query is too dangerous"
        )
        assert decision.decision_type == HITLDecisionType.REJECT
        assert decision.reason == "This query is too dangerous"
    
    def test_to_langraph_command_approve(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.APPROVE
        )
        cmd = decision.to_langraph_command()
        assert cmd == {"type": "approve"}
    
    def test_to_langraph_command_edit(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.EDIT,
            edited_arguments={"query": "new query"}
        )
        cmd = decision.to_langraph_command()
        assert cmd["type"] == "edit"
        assert cmd["args"] == {"query": "new query"}
    
    def test_to_langraph_command_reject_with_reason(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.REJECT,
            reason="Not approved"
        )
        cmd = decision.to_langraph_command()
        assert cmd["type"] == "reject"
        assert cmd["reason"] == "Not approved"


class TestHITLRequest:
    """Tests for HITLRequest model."""
    
    def test_create_simple_request(self):
        req = HITLRequest(prompt="Do you approve this action?")
        assert req.prompt == "Do you approve this action?"
        assert req.interrupt_id.startswith("interrupt-")
        assert len(req.action_requests) == 0
    
    def test_create_request_with_actions(self):
        ar = ActionRequest(name="web_search", arguments={"query": "test"})
        rc = ReviewConfig(action_name="web_search")
        
        req = HITLRequest(
            action_requests=[ar],
            review_configs=[rc]
        )
        assert len(req.action_requests) == 1
        assert len(req.review_configs) == 1
    
    def test_from_langraph_interrupt_string(self):
        """Test parsing a simple string interrupt (your graph style)."""
        req = HITLRequest.from_langraph_interrupt(
            "Review the agent's response. Type 'ACCEPTED' to finish.",
            thread_id="thread-123"
        )
        assert req.prompt == "Review the agent's response. Type 'ACCEPTED' to finish."
        assert len(req.action_requests) == 0
    
    def test_from_langraph_interrupt_dict_with_steps(self):
        """Test parsing a dict interrupt with steps (plan approval style)."""
        interrupt_value = {
            "steps": [
                {"description": "Step 1", "status": "enabled"},
                {"description": "Step 2", "status": "enabled"}
            ],
            "prompt": "Review these steps"
        }
        req = HITLRequest.from_langraph_interrupt(interrupt_value, "thread-123")
        assert req.prompt == "Review these steps"
        assert req.context == interrupt_value
    
    def test_from_langraph_interrupt_hitl_middleware_format(self):
        """Test parsing HITL middleware format with action_requests."""
        interrupt_value = {
            "action_requests": [
                {"name": "execute_sql", "arguments": {"query": "DELETE FROM users"}}
            ],
            "review_configs": [
                {"action_name": "execute_sql", "allowed_decisions": ["approve", "reject"]}
            ],
            "description": "Approve this SQL query?"
        }
        req = HITLRequest.from_langraph_interrupt(interrupt_value, "thread-123")
        assert len(req.action_requests) == 1
        assert req.action_requests[0].name == "execute_sql"
        assert req.prompt == "Approve this SQL query?"
    
    def test_to_ag_ui_event_simple(self):
        """Test AG-UI event generation for simple feedback."""
        req = HITLRequest(prompt="Do you approve?")
        event = req.to_ag_ui_event("thread-123")
        
        assert event["thread_id"] == "thread-123"
        assert event["content"] == "Do you approve?"
        assert event["finish_reason"] == "interrupt"
        assert event["role"] == "assistant"
        # Simple mode should have accept/feedback options
        assert any(o["value"] == "accepted" for o in event["options"])
        assert any(o["value"] == "feedback" for o in event["options"])
    
    def test_to_ag_ui_event_with_actions(self):
        """Test AG-UI event generation with action requests."""
        ar = ActionRequest(name="send_email", arguments={"to": "test@example.com"})
        rc = ReviewConfig(
            action_name="send_email",
            allowed_decisions=[HITLDecisionType.APPROVE, HITLDecisionType.EDIT, HITLDecisionType.REJECT]
        )
        req = HITLRequest(action_requests=[ar], review_configs=[rc])
        event = req.to_ag_ui_event("thread-123")
        
        assert "action_requests" in event
        assert "review_configs" in event
        assert len(event["action_requests"]) == 1
        # Should have approve, edit, reject options
        values = [o["value"] for o in event["options"]]
        assert "approve" in values
        assert "edit" in values
        assert "reject" in values
    
    def test_to_ag_ui_event_with_context(self):
        """Test that context (like steps) is included in event."""
        req = HITLRequest(
            prompt="Review steps",
            context={"steps": [{"description": "Step 1"}]}
        )
        event = req.to_ag_ui_event("thread-123")
        
        assert "context" in event
        assert event["context"]["steps"][0]["description"] == "Step 1"


class TestHITLResponse:
    """Tests for HITLResponse model."""
    
    def test_create_feedback_response(self):
        response = HITLResponse(
            interrupt_id="interrupt-123",
            feedback="Please use a different approach"
        )
        assert response.feedback == "Please use a different approach"
        assert len(response.decisions) == 0
    
    def test_create_decision_response(self):
        decision = HITLDecision(
            action_id="action-123",
            decision_type=HITLDecisionType.APPROVE
        )
        response = HITLResponse(
            interrupt_id="interrupt-123",
            decisions=[decision]
        )
        assert len(response.decisions) == 1
    
    def test_to_langraph_resume_feedback(self):
        """Test resuming with feedback (simple mode)."""
        response = HITLResponse(
            interrupt_id="interrupt-123",
            feedback="Do it differently"
        )
        resume = response.to_langraph_resume()
        assert resume == "Do it differently"
    
    def test_to_langraph_resume_decisions(self):
        """Test resuming with decisions (HITL middleware mode)."""
        decisions = [
            HITLDecision(action_id="action-1", decision_type=HITLDecisionType.APPROVE),
            HITLDecision(action_id="action-2", decision_type=HITLDecisionType.REJECT, reason="Too risky")
        ]
        response = HITLResponse(
            interrupt_id="interrupt-123",
            decisions=decisions
        )
        resume = response.to_langraph_resume()
        
        assert "decisions" in resume
        assert len(resume["decisions"]) == 2
        assert resume["decisions"][0]["type"] == "approve"
        assert resume["decisions"][1]["type"] == "reject"
        assert resume["decisions"][1]["reason"] == "Too risky"
    
    def test_to_langraph_resume_empty(self):
        """Test resuming with no feedback or decisions (assume acceptance)."""
        response = HITLResponse(interrupt_id="interrupt-123")
        resume = response.to_langraph_resume()
        assert resume == "ACCEPTED"


class TestHITLState:
    """Tests for HITLState dataclass."""
    
    def test_initial_state(self):
        state = HITLState()
        assert state.pending_request is None
        assert state.is_interrupted is False
        assert state.awaiting_response is False
    
    def test_create_interrupt(self):
        state = HITLState()
        req = state.create_interrupt("Do you approve?", "thread-123")
        
        assert state.is_interrupted is True
        assert state.awaiting_response is True
        assert state.pending_request is not None
        assert state.pending_request.prompt == "Do you approve?"
    
    def test_resolve_interrupt(self):
        state = HITLState()
        state.create_interrupt("Do you approve?", "thread-123")
        
        response = HITLResponse(
            interrupt_id=state.pending_request.interrupt_id,
            feedback="Yes, approved"
        )
        resume_value = state.resolve(response)
        
        assert state.is_interrupted is False
        assert state.awaiting_response is False
        assert state.pending_request is None
        assert resume_value == "Yes, approved"
    
    def test_clear_state(self):
        state = HITLState()
        state.create_interrupt("Test", "thread-123")
        state.clear()
        
        assert state.pending_request is None
        assert state.is_interrupted is False
        assert state.awaiting_response is False


class TestCreateHitlInterruptEvent:
    """Tests for create_hitl_interrupt_event helper."""
    
    def test_create_event_from_string(self):
        event_str = create_hitl_interrupt_event("Review this response", "thread-123")
        
        assert event_str.startswith("event: interrupt\n")
        assert "data: " in event_str
        
        # Parse the data
        data_line = event_str.split("data: ")[1].strip()
        data = json.loads(data_line)
        
        assert data["thread_id"] == "thread-123"
        assert data["content"] == "Review this response"
        assert data["finish_reason"] == "interrupt"
    
    def test_create_event_from_dict(self):
        interrupt_value = {
            "prompt": "Review steps",
            "steps": [{"description": "Step 1", "status": "enabled"}]
        }
        event_str = create_hitl_interrupt_event(interrupt_value, "thread-456")
        
        data_line = event_str.split("data: ")[1].strip()
        data = json.loads(data_line)
        
        assert data["thread_id"] == "thread-456"
        assert data["content"] == "Review steps"
        assert "context" in data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    print("Running Agent Models Unit Tests...\n")
    
    # Run with pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
    ])
    
    sys.exit(exit_code)
