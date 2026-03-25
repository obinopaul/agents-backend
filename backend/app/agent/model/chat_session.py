# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Chat Session model for managing agent chat conversations.

This model stores metadata about chat sessions including:
- User ownership and access control
- Agent configuration (type, LLM settings)
- Sandbox linkage for code execution
- Public sharing capability
"""

from datetime import datetime
from typing import Optional
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.database.db import uuid4_str
from backend.utils.timezone import timezone


class ChatSessionStatus(str, Enum):
    """Chat session status values."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AgentType(str, Enum):
    """
    Agent type values for chat sessions.
    
    Each type corresponds to a different LangGraph agent workflow:
    - CHAT: Basic AI chat without sandbox (uses chat.py logic)
    - GENERAL: Default MCP-enabled agent with sandbox tools
    - DEEP_RESEARCH: Deep research multi-agent workflow
    - ACADEMIC: Academic research multi-agent workflow
    - DESIGN: Design multi-agent workflow
    - DEV: Software development multi-agent workflow
    - DATA_SCIENTIST: Data scientist multi-agent workflow
    - SLIDES: Slides generation multi-agent workflow
    - DOCUMENTS: LaTeX/documents multi-agent workflow
    - QUANT: Tax/Financial multi-agent workflow
    - EXCALIDRAW: Excalidraw diagram multi-agent workflow
    """
    # No-sandbox types (use chat.py logic)
    CHAT = "chat"
    
    # Sandbox types (use agent.py logic with specific module)
    GENERAL = "general"
    DEEP_RESEARCH = "deep_research"
    ACADEMIC = "academic"
    DESIGN = "design"
    DEV = "dev"
    DATA_SCIENTIST = "data_scientist"
    SLIDES = "slides"
    DOCUMENTS = "documents"
    QUANT = "quant"
    EXCALIDRAW = "excalidraw"
    
    @property
    def requires_sandbox(self) -> bool:
        """Check if this agent type requires a sandbox environment."""
        return self != AgentType.CHAT
    
    @classmethod
    def get_sandbox_types(cls) -> list:
        """Get all agent types that require a sandbox."""
        return [t for t in cls if t.requires_sandbox]
    
    @classmethod
    def get_no_sandbox_types(cls) -> list:
        """Get all agent types that don't require a sandbox."""
        return [t for t in cls if not t.requires_sandbox]


class ChatSession(Base):
    """
    Chat session for agent conversations.
    
    A session represents a complete conversation thread between a user and the AI agent.
    Sessions can be linked to sandboxes for code execution and optionally shared publicly.
    
    Key features:
    - UUID-based external reference (for API URLs)
    - Soft delete support (deleted_at timestamp)
    - Session-to-sandbox linking for warm start optimization
    - Public sharing with separate access control
    - Event tracking via ChatEvent relationship
    """

    __tablename__ = 'agent_chat_sessions'

    # =========================================================================
    # Primary Key
    # =========================================================================
    
    id: Mapped[id_key] = mapped_column(init=False)
    
    # =========================================================================
    # Required fields (no defaults) - must come first for dataclasses
    # =========================================================================
    
    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id'),
        index=True,
        comment='User who owns this session'
    )
    
    # =========================================================================
    # Optional fields (with defaults) - must come after required fields
    # =========================================================================
    
    # Unique session identifier (for external API references)
    uuid: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        default_factory=uuid4_str,
        comment='Unique session UUID for API references'
    )
    
    # Session metadata
    name: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        default=None,
        comment='Session name/title (auto-generated from first message)'
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='Optional session description'
    )
    
    status: Mapped[str] = mapped_column(
        sa.String(50),
        default=ChatSessionStatus.ACTIVE.value,
        index=True,
        comment='Session status: active, completed, archived, deleted'
    )
    
    # Agent configuration
    agent_type: Mapped[Optional[str]] = mapped_column(
        sa.String(100),
        default=AgentType.GENERAL.value,
        index=True,
        comment='Agent type: general, scientific, academic, data_scientist, etc.'
    )
    
    llm_setting_id: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        comment='LLM configuration/model ID used for this session'
    )
    
    # Sandbox linkage (for warm start pattern)
    sandbox_id: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        index=True,
        comment='Linked sandbox ID for code execution'
    )
    
    workspace_dir: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        default=None,
        comment='Workspace directory path (typically /workspace/<session_uuid>)'
    )
    
    # Visibility & sharing
    is_public: Mapped[bool] = mapped_column(
        default=False,
        index=True,
        comment='Whether session is publicly viewable'
    )
    
    public_slug: Mapped[Optional[str]] = mapped_column(
        sa.String(64),
        default=None,
        unique=True,
        index=True,
        comment='Optional custom slug for public sharing URL'
    )
    
    # Token/credit usage tracking
    total_prompt_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Total prompt tokens used in this session'
    )
    
    total_completion_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Total completion tokens used in this session'
    )
    
    total_credits_used: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        comment='Total credits consumed in this session'
    )
    
    # Message count for quick access
    message_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Number of messages in session (for listing optimization)'
    )
    
    # Last activity tracking (for sorting, cleanup)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        TimeZone,
        default=None,
        index=True,
        comment='Last activity timestamp (message, tool use, etc.)'
    )
    
    # Soft delete timestamp
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TimeZone,
        default=None,
        index=True,
        comment='Soft delete timestamp (null = not deleted)'
    )
    
    # =========================================================================
    # Timestamps (auto-generated by Base class DateTimeMixin)
    # created_time and updated_time are inherited from Base
    # =========================================================================
    
    # =========================================================================
    # Relationships
    # =========================================================================
    
    # User relationship
    user = relationship("User", lazy="selectin")
    
    # Events relationship (for loading session history)
    events = relationship(
        "ChatEvent",
        back_populates="session",
        lazy="selectin",
        order_by="ChatEvent.created_at",
        cascade="all, delete-orphan"
    )

    # Wishlist relationship (users who have wishlisted this session)
    wishlisted_by = relationship(
        "SessionWishlist",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def is_deleted(self) -> bool:
        """Check if session is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def is_active(self) -> bool:
        """Check if session is active and not deleted."""
        return self.status == ChatSessionStatus.ACTIVE.value and not self.is_deleted
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used (prompt + completion)."""
        return self.total_prompt_tokens + self.total_completion_tokens
    
    @property
    def workspace_path(self) -> str:
        """Get the workspace path (computed if not set)."""
        if self.workspace_dir:
            return self.workspace_dir
        return f"/workspace/{self.uuid}"
    
    # =========================================================================
    # Methods
    # =========================================================================
    
    def get_workspace_dir(self) -> str:
        """Get the workspace directory path (compatible with II-Agent)."""
        return self.workspace_path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.uuid,  # Use UUID for external API
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'agent_type': self.agent_type,
            'sandbox_id': self.sandbox_id,
            'workspace_dir': self.workspace_path,
            'is_public': self.is_public,
            'public_slug': self.public_slug,
            'message_count': self.message_count,
            'total_tokens': self.total_tokens,
            'total_credits_used': self.total_credits_used,
            'created_at': self.created_time.isoformat() if self.created_time else None,
            'updated_at': self.updated_time.isoformat() if self.updated_time else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
        }
    
    def to_session_info(self) -> dict:
        """Convert to SessionInfo-compatible format for II-Agent compatibility."""
        return {
            'id': self.uuid,
            'user_id': str(self.user_id),
            'name': self.name,
            'status': self.status,
            'sandbox_id': self.sandbox_id,
            'agent_type': self.agent_type,
            'created_at': self.created_time.isoformat() if self.created_time else None,
            'updated_at': self.updated_time.isoformat() if self.updated_time else None,
            'workspace_dir': self.workspace_path,
            'is_public': self.is_public,
            'token_usage': {
                'prompt_tokens': self.total_prompt_tokens,
                'completion_tokens': self.total_completion_tokens,
                'total_tokens': self.total_tokens,
            } if self.total_tokens > 0 else None,
        }
