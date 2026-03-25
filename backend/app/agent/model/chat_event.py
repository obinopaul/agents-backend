# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Chat Event model for storing session events (messages, tool calls, etc.).

Events represent individual interactions within a chat session:
- User messages
- Agent responses
- Tool calls and results
- System events (sandbox status, errors, etc.)
"""

from datetime import datetime
from typing import Optional
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from backend.common.model import Base, TimeZone, id_key
from backend.database.db import uuid4_str
from backend.utils.timezone import timezone


class ChatEventType(str, Enum):
    """Event types matching II-Agent and AG-UI Protocol."""
    
    # Connection & System
    CONNECTION_ESTABLISHED = "connection_established"
    SYSTEM = "system"
    ERROR = "error"
    
    # Agent lifecycle
    AGENT_INITIALIZED = "agent_initialized"
    PROCESSING = "processing"
    STATUS_UPDATE = "status_update"
    
    # Messages
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    
    # Tool operations
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # Reasoning (for AG-UI Protocol)
    REASONING_START = "reasoning_start"
    REASONING_CONTENT = "reasoning_content"
    REASONING_END = "reasoning_end"
    
    # Sandbox
    SANDBOX_STATUS = "sandbox_status"
    WORKSPACE_INFO = "workspace_info"
    
    # Other
    PONG = "pong"
    PROMPT_GENERATED = "prompt_generated"
    FILE_UPLOAD = "file_upload"


class ChatEvent(Base):
    """
    Event in a chat session.
    
    Events are immutable records of all interactions in a session.
    They provide:
    - Complete conversation history for replay
    - Tool call tracking for debugging
    - Token usage per event for billing
    - Run ID grouping for multi-step agent operations
    
    The content field stores event-specific data as JSONB for flexibility.
    """

    __tablename__ = 'agent_chat_events'

    # =========================================================================
    # Primary Key
    # =========================================================================
    
    id: Mapped[id_key] = mapped_column(init=False)
    
    # =========================================================================
    # Required fields (no defaults) - must come first for dataclasses
    # =========================================================================
    
    # Foreign key to session
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_chat_sessions.id', ondelete='CASCADE'),
        index=True,
        comment='Parent chat session ID'
    )
    
    # Event type (required)
    event_type: Mapped[str] = mapped_column(
        sa.String(50),
        index=True,
        comment='Event type: user_message, agent_message, tool_call, etc.'
    )
    
    # =========================================================================
    # Optional fields (with defaults) - must come after required fields
    # =========================================================================
    
    # Unique event identifier (for external API references)
    uuid: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        default_factory=uuid4_str,
        comment='Unique event UUID for API references'
    )
    
    # Run ID for grouping related events (one agent run = multiple events)
    run_id: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        index=True,
        comment='Agent run ID for grouping related events'
    )
    
    # Parent event ID (for tool results referencing tool calls)
    parent_event_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_chat_events.id', ondelete='SET NULL'),
        default=None,
        index=True,
        comment='Parent event ID (e.g., tool_result -> tool_call)'
    )
    
    # Event role (for message events)
    role: Mapped[Optional[str]] = mapped_column(
        sa.String(50),
        default=None,
        index=True,
        comment='Message role: user, assistant, system, tool'
    )
    
    # Event content as flexible JSON
    content: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        comment='Event content as JSON (structure depends on event_type)'
    )
    
    # Raw content for messages (plain text for searchability)
    text_content: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='Plain text content for full-text search'
    )
    
    # Tool-specific fields
    tool_name: Mapped[Optional[str]] = mapped_column(
        sa.String(128),
        default=None,
        index=True,
        comment='Tool name for tool_call events'
    )
    
    tool_call_id: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        index=True,
        comment='Tool call ID (links call to result)'
    )
    
    # Token tracking per event
    prompt_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Prompt tokens for this event'
    )
    
    completion_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Completion tokens for this event'
    )
    
    # Processing metadata
    model_name: Mapped[Optional[str]] = mapped_column(
        sa.String(128),
        default=None,
        comment='LLM model used for this event'
    )
    
    latency_ms: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        default=None,
        comment='Processing latency in milliseconds'
    )
    
    # Error tracking
    error_type: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        comment='Error type for error events'
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='Error message for error events'
    )
    
    # File attachments (for messages with files)
    file_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        default=None,
        comment='List of attached file IDs'
    )
    
    # Timestamp (auto-generated)
    created_at: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        index=True,
        comment='Event creation timestamp'
    )
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    # Session relationship
    session = relationship(
        "ChatSession",
        back_populates="events",
        lazy="selectin"
    )
    
    # Parent event relationship (for tool results)
    parent_event = relationship(
        "ChatEvent",
        remote_side="ChatEvent.id",
        lazy="selectin"
    )
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens for this event."""
        return self.prompt_tokens + self.completion_tokens
    
    @property
    def is_message(self) -> bool:
        """Check if this is a message event."""
        return self.event_type in (
            ChatEventType.USER_MESSAGE.value,
            ChatEventType.AGENT_MESSAGE.value
        )
    
    @property
    def is_tool_event(self) -> bool:
        """Check if this is a tool-related event."""
        return self.event_type in (
            ChatEventType.TOOL_CALL.value,
            ChatEventType.TOOL_RESULT.value
        )
    
    @property
    def is_error(self) -> bool:
        """Check if this is an error event."""
        return self.event_type == ChatEventType.ERROR.value
    
    # =========================================================================
    # Methods
    # =========================================================================
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.uuid,
            'session_id': self.session.uuid if self.session else None,
            'type': self.event_type,
            'role': self.role,
            'content': self.content,
            'text': self.text_content,
            'run_id': self.run_id,
            'tool_name': self.tool_name,
            'tool_call_id': self.tool_call_id,
            'file_ids': self.file_ids,
            'tokens': {
                'prompt': self.prompt_tokens,
                'completion': self.completion_tokens,
                'total': self.total_tokens,
            } if self.total_tokens > 0 else None,
            'model': self.model_name,
            'latency_ms': self.latency_ms,
            'error': {
                'type': self.error_type,
                'message': self.error_message,
            } if self.is_error else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def to_realtime_event(self) -> dict:
        """Convert to II-Agent RealtimeEvent-compatible format."""
        return {
            'type': self.event_type,
            'session_id': self.session.uuid if self.session else None,
            'run_id': self.run_id,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def from_realtime_event(
        cls,
        session_id: int,
        event_type: str,
        content: dict,
        run_id: Optional[str] = None,
        **kwargs
    ) -> "ChatEvent":
        """Create ChatEvent from II-Agent RealtimeEvent data."""
        # Extract text content if present
        text_content = None
        if 'text' in content:
            text_content = content['text']
        elif 'message' in content:
            text_content = content['message']
        
        # Determine role from event type
        role = None
        if event_type == ChatEventType.USER_MESSAGE.value:
            role = 'user'
        elif event_type == ChatEventType.AGENT_MESSAGE.value:
            role = 'assistant'
        elif event_type == ChatEventType.SYSTEM.value:
            role = 'system'
        elif event_type in (ChatEventType.TOOL_CALL.value, ChatEventType.TOOL_RESULT.value):
            role = 'tool'
        
        # Extract tool info if present
        tool_name = content.get('tool_name') or kwargs.get('tool_name')
        tool_call_id = content.get('tool_call_id') or kwargs.get('tool_call_id')
        
        return cls(
            session_id=session_id,
            event_type=event_type,
            run_id=run_id,
            role=role,
            content=content,
            text_content=text_content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            **kwargs
        )
