"""MCP Settings database model.

Stores user configurations for MCP tools like Codex and Claude Code.
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class MCPSetting(Base):
    """User MCP tool configurations (Codex, Claude Code, custom MCP servers).
    
    Each user can have multiple MCP settings (one per tool type).
    """

    __tablename__ = 'agent_mcp_settings'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # Foreign key to sys_user (same pattern as APIKey)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, 
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'), 
        index=True,
        comment='User who owns this MCP setting'
    )
    
    # Tool type identifier: 'codex', 'claude_code', or custom MCP server name
    tool_type: Mapped[str] = mapped_column(
        sa.String(64), 
        index=True,
        comment='MCP tool type (codex, claude_code, or custom)'
    )
    
    # MCP server configuration (command, args, etc.)
    # Format: {"mcpServers": {"name": {"command": "...", "args": [...]}}}
    mcp_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default_factory=dict,  # Use default_factory for mutable defaults
        comment='MCP server configuration JSON'
    )
    
    # Authentication data (OAuth tokens, API keys, etc.)
    # Format varies by tool type:
    # - codex: {"OPENAI_API_KEY": "..."}
    # - claude_code: {"claudeAiOauth": {"accessToken": "...", "refreshToken": "..."}}
    auth_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=None,
        comment='Authentication credentials JSON'
    )
    
    # Additional metadata (model preferences, settings, etc.)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=None,
        comment='Additional metadata (model, reasoning_effort, etc.)'
    )
    
    # Whether this configuration is active
    is_active: Mapped[bool] = mapped_column(
        default=True, 
        index=True,
        comment='Whether this MCP setting is active'
    )
    
    # Store path for credentials in sandbox (e.g., ~/.claude, ~/.codex)
    store_path: Mapped[str | None] = mapped_column(
        sa.String(256),
        default=None,
        comment='Path in sandbox where credentials are written'
    )

    # Unique constraint: one active setting per user per tool type
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'tool_type', name='uq_user_tool_type'),
        {'comment': 'User MCP tool configurations'}
    )
