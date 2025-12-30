# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Models Module - Structured types for AG-UI Protocol.

This module provides Pydantic models and dataclasses for structured handling of:
- Messages (user/assistant/system)
- Tool calls and results
- Multimodal content (images, files)
- Reasoning/thinking blocks

These models are designed to:
1. Keep code structured and type-safe (inspired by II-Agent patterns)
2. Work seamlessly with LangChain v1's content_blocks format
3. Support AG-UI Protocol events for streaming

The key principle: Use structured classes for our internal representation,
but LangChain handles provider-specific format conversion.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class ContentBlockType(str, Enum):
    """Types of content blocks in messages."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class MessageRole(str, Enum):
    """Valid message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# =============================================================================
# Content Block Models (for multimodal messages)
# =============================================================================

class TextBlock(BaseModel):
    """A text content block."""
    type: Literal["text"] = "text"
    text: str = Field(..., description="The text content")


class ImageBlock(BaseModel):
    """
    An image content block.
    
    Supports both URL-based and base64-encoded images.
    LangChain v1 format compatible.
    """
    type: Literal["image"] = "image"
    url: Optional[str] = Field(None, description="URL of the image")
    data: Optional[str] = Field(None, description="Base64-encoded image data")
    mime_type: Optional[str] = Field(None, description="MIME type (e.g., 'image/jpeg')")
    detail: Optional[str] = Field("auto", description="Detail level: 'low', 'high', or 'auto'")
    
    @field_validator('data', 'url', mode='after')
    @classmethod
    def validate_source(cls, v, info):
        # At least one of url or data must be provided
        return v
    
    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain v1 multimodal format."""
        if self.url:
            return {"type": "image", "url": self.url}
        elif self.data:
            return {
                "type": "image", 
                "data": self.data,
                "mime_type": self.mime_type or "image/jpeg"
            }
        raise ValueError("ImageBlock must have either url or data")


class AudioBlock(BaseModel):
    """An audio content block."""
    type: Literal["audio"] = "audio"
    url: Optional[str] = Field(None, description="URL of the audio file")
    data: Optional[str] = Field(None, description="Base64-encoded audio data")
    mime_type: Optional[str] = Field(None, description="MIME type (e.g., 'audio/mp3')")
    
    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain v1 multimodal format."""
        if self.url:
            return {"type": "audio", "url": self.url}
        elif self.data:
            return {
                "type": "audio",
                "data": self.data,
                "mime_type": self.mime_type or "audio/mp3"
            }
        raise ValueError("AudioBlock must have either url or data")


class FileBlock(BaseModel):
    """
    A file content block for attachments.
    
    Supports various file types (PDF, documents, etc.)
    """
    type: Literal["file"] = "file"
    url: Optional[str] = Field(None, description="URL of the file")
    filepath: Optional[str] = Field(None, description="Local file path")
    data: Optional[str] = Field(None, description="Base64-encoded file data")
    mime_type: Optional[str] = Field(None, description="MIME type")
    filename: Optional[str] = Field(None, description="Original filename")


# =============================================================================
# Reasoning/Thinking Models (AG-UI Protocol)
# =============================================================================

class ReasoningBlock(BaseModel):
    """
    A reasoning/thinking content block.
    
    LangChain v1's content_blocks standardizes this across providers:
    - Anthropic's <thinking> → type: "reasoning"
    - OpenAI's reasoning_content → type: "reasoning"
    
    AG-UI Protocol events:
    - reasoning_start
    - reasoning_message_start
    - reasoning_message_content (delta)
    - reasoning_message_end
    - reasoning_end
    """
    type: Literal["reasoning"] = "reasoning"
    reasoning: str = Field(..., description="The reasoning/thinking content")
    signature: Optional[str] = Field(None, description="Signature for extended thinking (Anthropic)")
    

@dataclass
class ReasoningState:
    """
    Tracks reasoning state across streaming chunks.
    
    Used to properly emit AG-UI reasoning events.
    """
    message_id: Optional[str] = None
    is_active: bool = False
    
    def start_reasoning(self) -> str:
        """Start a new reasoning block and return its ID."""
        self.message_id = f"reasoning-{uuid4().hex[:8]}"
        self.is_active = True
        return self.message_id
    
    def end_reasoning(self) -> Optional[str]:
        """End reasoning and return the message ID."""
        msg_id = self.message_id
        self.message_id = None
        self.is_active = False
        return msg_id


# =============================================================================
# Tool Call Models (AG-UI Protocol)
# =============================================================================

class ToolCall(BaseModel):
    """
    Represents a tool call from the assistant.
    
    AG-UI Protocol events:
    - tool_call_start (toolCallId, toolCallName)
    - tool_call_args (toolCallId, delta)
    - tool_call_end (toolCallId)
    
    Works with LangChain's tool_calls from AIMessage.
    """
    tool_call_id: str = Field(..., description="Unique ID for this tool call")
    tool_name: str = Field(..., description="Name of the tool being called")
    tool_input: Union[Dict[str, Any], str] = Field(
        default_factory=dict,
        description="Tool input arguments (dict or JSON string)"
    )
    # Additional metadata
    index: Optional[int] = Field(None, description="Index for parallel tool calls")
    
    @classmethod
    def from_langchain(cls, lc_tool_call: Dict[str, Any]) -> "ToolCall":
        """Create from LangChain tool_call dict."""
        return cls(
            tool_call_id=lc_tool_call.get("id", str(uuid4())),
            tool_name=lc_tool_call.get("name", ""),
            tool_input=lc_tool_call.get("args", {}),
            index=lc_tool_call.get("index"),
        )
    
    def to_ag_ui_start_event(self) -> Dict[str, Any]:
        """Create AG-UI tool_call_start event data."""
        return {
            "toolCallId": self.tool_call_id,
            "toolCallName": self.tool_name,
        }
    
    def to_ag_ui_args_event(self, delta: str) -> Dict[str, Any]:
        """Create AG-UI tool_call_args event data."""
        return {
            "toolCallId": self.tool_call_id,
            "delta": delta,
        }
    
    def to_ag_ui_end_event(self) -> Dict[str, Any]:
        """Create AG-UI tool_call_end event data."""
        return {
            "toolCallId": self.tool_call_id,
        }


class ToolResult(BaseModel):
    """
    Represents the result of a tool execution.
    
    AG-UI Protocol event: tool_result
    """
    tool_call_id: str = Field(..., description="ID of the tool call this result is for")
    tool_name: str = Field(..., description="Name of the tool")
    output: Union[str, List[Dict[str, Any]]] = Field(
        ..., 
        description="Tool output (string or list for multimodal results)"
    )
    is_error: bool = Field(default=False, description="Whether the result is an error")
    
    def to_ag_ui_event(self) -> Dict[str, Any]:
        """Create AG-UI tool_result event data."""
        return {
            "toolCallId": self.tool_call_id,
            "content": self.output if isinstance(self.output, str) else self.output,
        }


@dataclass
class ToolCallState:
    """
    Tracks tool call state across streaming chunks.
    
    Handles proper event emission for parallel tool calls.
    """
    active_calls: Dict[str, ToolCall] = field(default_factory=dict)
    completed_calls: set = field(default_factory=set)
    args_buffers: Dict[str, str] = field(default_factory=dict)
    
    def start_tool_call(self, tool_call: ToolCall) -> None:
        """Register a new tool call."""
        self.active_calls[tool_call.tool_call_id] = tool_call
        self.args_buffers[tool_call.tool_call_id] = ""
    
    def append_args(self, tool_call_id: str, args_delta: str) -> None:
        """Append arguments to a tool call."""
        if tool_call_id in self.args_buffers:
            self.args_buffers[tool_call_id] += args_delta
    
    def complete_tool_call(self, tool_call_id: str) -> Optional[ToolCall]:
        """Mark a tool call as complete and return it."""
        if tool_call_id in self.active_calls:
            tool_call = self.active_calls.pop(tool_call_id)
            # Update with complete args
            if tool_call_id in self.args_buffers:
                tool_call.tool_input = self.args_buffers.pop(tool_call_id)
            self.completed_calls.add(tool_call_id)
            return tool_call
        return None
    
    def is_active(self, tool_call_id: str) -> bool:
        """Check if a tool call is still active."""
        return tool_call_id in self.active_calls


# =============================================================================
# Message Models
# =============================================================================

# Union type for all content block types
ContentBlock = Union[TextBlock, ImageBlock, AudioBlock, FileBlock, ReasoningBlock]


class AgentMessage(BaseModel):
    """
    Represents a single message in the agent conversation.
    
    Supports both simple text messages and multimodal messages.
    Content can be:
    - A string (simple text message)
    - A list of ContentBlock objects (multimodal)
    - A list of dicts (LangChain v1 raw format)
    
    Example multimodal content:
    ```python
    AgentMessage(
        role="user",
        content=[
            TextBlock(text="What's in this image?"),
            ImageBlock(url="https://example.com/photo.jpg")
        ]
    )
    ```
    """
    role: MessageRole = Field(..., description="Message role")
    content: Union[str, List[ContentBlock], List[Dict[str, Any]]] = Field(
        ..., 
        description="Message content"
    )
    name: Optional[str] = Field(None, description="Optional name of the sender")
    
    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to format suitable for LangChain."""
        result = {"role": self.role.value}
        
        if isinstance(self.content, str):
            result["content"] = self.content
        elif isinstance(self.content, list):
            # Convert content blocks to dicts
            converted = []
            for item in self.content:
                if isinstance(item, BaseModel):
                    # Pydantic model -> dict
                    if hasattr(item, 'to_langchain_format'):
                        converted.append(item.to_langchain_format())
                    else:
                        converted.append(item.model_dump())
                else:
                    # Already a dict
                    converted.append(item)
            result["content"] = converted
        
        if self.name:
            result["name"] = self.name
            
        return result


class ChatMessage(AgentMessage):
    """
    Alias for AgentMessage for chat endpoints.
    
    Same structure, different name for semantic clarity.
    """
    pass


# =============================================================================
# Request Models
# =============================================================================

class AgentRequest(BaseModel):
    """Request model for agent streaming endpoint."""
    messages: List[AgentMessage] = Field(..., description="Conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for continuity")
    max_plan_iterations: int = Field(default=1, ge=1, le=10)
    max_step_num: int = Field(default=3, ge=1, le=10)
    max_search_results: int = Field(default=3, ge=1, le=20)
    auto_accepted_plan: bool = Field(default=True)
    interrupt_feedback: Optional[str] = Field(None)
    enable_background_investigation: bool = Field(default=True)
    enable_web_search: bool = Field(default=True)
    enable_deep_thinking: bool = Field(default=False)
    locale: str = Field(default="en-US")
    
    # Optional: RAG resources (import as needed)
    # resources: List[Resource] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Request model for chat streaming endpoint."""
    messages: List[ChatMessage] = Field(..., description="Conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for continuity")
    max_plan_iterations: int = Field(default=1, ge=1, le=10)
    max_step_num: int = Field(default=3, ge=1, le=10)
    max_search_results: int = Field(default=3, ge=1, le=20)
    auto_accepted_plan: bool = Field(default=True)
    interrupt_feedback: Optional[str] = Field(None)
    enable_background_investigation: bool = Field(default=True)
    enable_web_search: bool = Field(default=True)
    enable_deep_thinking: bool = Field(default=False)
    enable_clarification: bool = Field(default=False)
    max_clarification_rounds: int = Field(default=3, ge=1, le=10)
    locale: str = Field(default="en-US")
    interrupt_before_tools: Optional[List[str]] = Field(None)


# =============================================================================
# AG-UI Event Helpers
# =============================================================================

def make_ag_ui_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Create an AG-UI Protocol SSE event.
    
    Event types:
    - tool_call_start, tool_call_args, tool_call_end, tool_result
    - reasoning_start, reasoning_message_start, reasoning_message_content, 
      reasoning_message_end, reasoning_end
    - message_chunk, status, error, etc.
    """
    import json
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def extract_reasoning_from_content_blocks(content_blocks: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract reasoning content from LangChain v1 content_blocks.
    
    LangChain v1 standardizes reasoning across providers:
    - Anthropic thinking → {"type": "reasoning", "reasoning": "..."}
    - OpenAI reasoning → {"type": "reasoning", "reasoning": "..."}
    """
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'reasoning':
            # Try various field names that might contain the reasoning
            return (
                block.get('reasoning') or 
                block.get('thinking') or 
                block.get('text', '')
            )
    return None


# =============================================================================
# Human-in-the-Loop (HITL) Models - AG-UI Protocol
# =============================================================================

class HITLDecisionType(str, Enum):
    """
    Human decision types for Human-in-the-Loop interrupts.
    
    Based on LangChain HumanInTheLoopMiddleware and AG-UI Protocol:
    - approve: Execute the action as-is
    - edit: Execute with modifications
    - reject: Reject with feedback
    """
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    ACCEPTED = "accepted"  # Alias for approve (from your graph)
    FEEDBACK = "feedback"  # Continue with user feedback


class ActionRequest(BaseModel):
    """
    Represents a pending action that requires human review.
    
    Used in HITL interrupts when the agent needs approval before executing.
    Maps to AG-UI's action_requests in interrupt events.
    """
    name: str = Field(..., description="Name of the tool/action pending review")
    action_id: str = Field(default_factory=lambda: f"action-{uuid4().hex[:8]}")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    description: Optional[str] = Field(None, description="Human-readable description of the action")
    
    def to_ag_ui_format(self) -> Dict[str, Any]:
        """Convert to AG-UI protocol format."""
        return {
            "actionId": self.action_id,
            "name": self.name,
            "arguments": self.arguments,
            "description": self.description or f"Tool execution: {self.name}",
        }


class ReviewConfig(BaseModel):
    """
    Configuration for how an action can be reviewed.
    
    Specifies which decision types are allowed for a given action.
    """
    action_name: str = Field(..., description="Name of the action this config applies to")
    allowed_decisions: List[HITLDecisionType] = Field(
        default_factory=lambda: [HITLDecisionType.APPROVE, HITLDecisionType.REJECT],
        description="Which decisions are allowed for this action"
    )
    requires_reason: bool = Field(
        default=False,
        description="Whether rejection requires a reason"
    )
    editable_fields: Optional[List[str]] = Field(
        None,
        description="Which argument fields can be edited (None = all)"
    )
    
    def to_ag_ui_format(self) -> Dict[str, Any]:
        """Convert to AG-UI protocol format."""
        return {
            "actionName": self.action_name,
            "allowedDecisions": [d.value for d in self.allowed_decisions],
            "requiresReason": self.requires_reason,
            "editableFields": self.editable_fields,
        }


class HITLDecision(BaseModel):
    """
    A human's decision on a pending action.
    
    Used to resume workflow after an interrupt.
    """
    action_id: str = Field(..., description="ID of the action this decision is for")
    decision_type: HITLDecisionType = Field(..., description="The decision made")
    edited_arguments: Optional[Dict[str, Any]] = Field(
        None,
        description="Modified arguments (for 'edit' decisions)"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for rejection or feedback"
    )
    
    def to_langraph_command(self) -> Dict[str, Any]:
        """Convert to LangGraph Command resume format."""
        decision = {"type": self.decision_type.value}
        
        if self.decision_type == HITLDecisionType.EDIT and self.edited_arguments:
            decision["args"] = self.edited_arguments
        
        if self.reason:
            decision["reason"] = self.reason
            
        return decision


class HITLRequest(BaseModel):
    """
    A Human-in-the-Loop request sent when the agent needs human input.
    
    Contains pending actions and their review configurations.
    This is what gets sent in the AG-UI `interrupt` event.
    
    AG-UI Event: interrupt
    """
    interrupt_id: str = Field(default_factory=lambda: f"interrupt-{uuid4().hex[:8]}")
    action_requests: List[ActionRequest] = Field(
        default_factory=list,
        description="Actions pending review"
    )
    review_configs: List[ReviewConfig] = Field(
        default_factory=list,
        description="Review configurations for each action"
    )
    prompt: Optional[str] = Field(
        None,
        description="Custom prompt to display to the user"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context (e.g., steps, state)"
    )
    
    @classmethod
    def from_langraph_interrupt(cls, interrupt_value: Any, thread_id: str = "") -> "HITLRequest":
        """
        Create from a LangGraph interrupt value.
        
        Handles various formats:
        - String prompt (simple feedback request)
        - Dict with action_requests (HITL middleware format)
        - Dict with steps (custom node format like yours)
        """
        interrupt_id = f"interrupt-{uuid4().hex[:8]}"
        
        # Simple string prompt (your human_feedback_node style)
        if isinstance(interrupt_value, str):
            return cls(
                interrupt_id=interrupt_id,
                prompt=interrupt_value,
                action_requests=[],
                review_configs=[],
            )
        
        # Dict with structured data
        if isinstance(interrupt_value, dict):
            # Check for HITL middleware format
            if "action_requests" in interrupt_value:
                action_requests = [
                    ActionRequest(**ar) if isinstance(ar, dict) else ar
                    for ar in interrupt_value.get("action_requests", [])
                ]
                review_configs = [
                    ReviewConfig(**rc) if isinstance(rc, dict) else rc
                    for rc in interrupt_value.get("review_configs", [])
                ]
                return cls(
                    interrupt_id=interrupt_id,
                    action_requests=action_requests,
                    review_configs=review_configs,
                    prompt=interrupt_value.get("description"),
                )
            
            # Custom format (e.g., steps for plan approval)
            return cls(
                interrupt_id=interrupt_id,
                prompt=interrupt_value.get("prompt") or interrupt_value.get("message"),
                context=interrupt_value,
                action_requests=[],
                review_configs=[],
            )
        
        # Fallback
        return cls(
            interrupt_id=interrupt_id,
            prompt=str(interrupt_value) if interrupt_value else None,
        )
    
    def to_ag_ui_event(self, thread_id: str = "") -> Dict[str, Any]:
        """
        Create AG-UI interrupt event data.
        
        Compatible with the frontend interrupt handler.
        """
        # Build options based on review configs
        options = []
        
        if not self.action_requests:
            # Simple feedback mode (your graph style)
            options = [
                {"text": "Accept", "value": "accepted"},
                {"text": "Provide feedback", "value": "feedback"},
            ]
        else:
            # HITL middleware style with actions
            all_allowed = set()
            for rc in self.review_configs:
                all_allowed.update(rc.allowed_decisions)
            
            if HITLDecisionType.APPROVE in all_allowed:
                options.append({"text": "Approve", "value": "approve"})
            if HITLDecisionType.EDIT in all_allowed:
                options.append({"text": "Edit", "value": "edit"})
            if HITLDecisionType.REJECT in all_allowed:
                options.append({"text": "Reject", "value": "reject"})
        
        event_data = {
            "id": self.interrupt_id,
            "thread_id": thread_id,
            "role": "assistant",
            "finish_reason": "interrupt",
            "options": options,
        }
        
        # Add prompt/content
        if self.prompt:
            event_data["content"] = self.prompt
        elif self.action_requests:
            # Generate content from action requests
            actions_desc = ", ".join(ar.name for ar in self.action_requests)
            event_data["content"] = f"Pending actions require review: {actions_desc}"
        else:
            event_data["content"] = "Human feedback required"
        
        # Add action requests for frontend to display
        if self.action_requests:
            event_data["action_requests"] = [
                ar.to_ag_ui_format() for ar in self.action_requests
            ]
            event_data["review_configs"] = [
                rc.to_ag_ui_format() for rc in self.review_configs
            ]
        
        # Add context (e.g., steps, state)
        if self.context:
            event_data["context"] = self.context
        
        return event_data


class HITLResponse(BaseModel):
    """
    Response from the user after an interrupt.
    
    Used to resume the workflow with human decisions.
    """
    interrupt_id: str = Field(..., description="ID of the interrupt being responded to")
    decisions: List[HITLDecision] = Field(
        default_factory=list,
        description="Decisions for each pending action"
    )
    feedback: Optional[str] = Field(
        None,
        description="General feedback text (for simple feedback mode)"
    )
    
    def to_langraph_resume(self) -> Any:
        """
        Convert to LangGraph Command.resume format.
        
        Handles both:
        - Simple feedback (returns the feedback string)
        - HITL decisions (returns decisions dict)
        """
        if self.feedback and not self.decisions:
            # Simple feedback mode
            return self.feedback
        
        if self.decisions:
            # HITL middleware format
            return {
                "decisions": [d.to_langraph_command() for d in self.decisions]
            }
        
        # Fallback - assume acceptance
        return "ACCEPTED"


@dataclass
class HITLState:
    """
    Tracks HITL state across workflow execution.
    
    Used to manage interrupt/resume lifecycle.
    """
    pending_request: Optional[HITLRequest] = None
    is_interrupted: bool = False
    awaiting_response: bool = False
    
    def create_interrupt(
        self,
        interrupt_value: Any,
        thread_id: str = "",
    ) -> HITLRequest:
        """Create and store a new HITL request."""
        self.pending_request = HITLRequest.from_langraph_interrupt(
            interrupt_value, thread_id
        )
        self.is_interrupted = True
        self.awaiting_response = True
        return self.pending_request
    
    def resolve(self, response: HITLResponse) -> Any:
        """Resolve the interrupt with a response."""
        self.is_interrupted = False
        self.awaiting_response = False
        resume_value = response.to_langraph_resume()
        self.pending_request = None
        return resume_value
    
    def clear(self) -> None:
        """Clear the HITL state."""
        self.pending_request = None
        self.is_interrupted = False
        self.awaiting_response = False


def create_hitl_interrupt_event(
    interrupt_value: Any,
    thread_id: str,
) -> str:
    """
    Create an AG-UI interrupt event from a LangGraph interrupt.
    
    This is the main helper function for streaming endpoints.
    
    Usage in agent.py or chat.py:
        if "__interrupt__" in event_data:
            interrupt = event_data["__interrupt__"][0]
            yield create_hitl_interrupt_event(interrupt.value, thread_id)
    """
    hitl_request = HITLRequest.from_langraph_interrupt(interrupt_value, thread_id)
    return make_ag_ui_event("interrupt", hitl_request.to_ag_ui_event(thread_id))
