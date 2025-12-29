"""Agent models for credits, API keys, and session metrics."""

from datetime import datetime
import secrets

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.database.db import uuid4_str
from backend.utils.timezone import timezone


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


class APIKey(Base):
    """API Key for tool server authentication."""

    __tablename__ = 'agent_api_keys'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # Foreign key to user
    user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('sys_user.id'), index=True)
    
    # API key value (prefix sk_ for identification)
    api_key: Mapped[str] = mapped_column(
        sa.String(256), 
        unique=True, 
        index=True, 
        default_factory=generate_api_key,
        comment='API key token'
    )
    
    # Key metadata
    name: Mapped[str] = mapped_column(sa.String(128), default='Default', comment='Key name/label')
    is_active: Mapped[bool] = mapped_column(default=True, comment='Whether key is active')
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now, comment='Creation time'
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='Expiration time (null = never)'
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        TimeZone, init=False, default=None, comment='Last usage time'
    )
    
    # Relationship to user
    user = relationship("User", back_populates="api_keys", lazy="selectin")


class SessionMetrics(Base):
    """Track credit usage per agent session."""

    __tablename__ = 'agent_session_metrics'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # Link to user who owns this session
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, 
        sa.ForeignKey('sys_user.id'), 
        index=True,
        comment='User who owns this session'
    )
    
    # Session identifier (from agent chat)
    session_id: Mapped[str] = mapped_column(
        sa.String(64), 
        unique=True, 
        index=True,
        comment='Agent session ID'
    )
    
    # Model used for this session
    model_name: Mapped[str | None] = mapped_column(
        sa.String(64),
        default=None,
        comment='LLM model name used'
    )
    
    # Sandbox linked to this session (for session-based sandbox reuse)
    sandbox_id: Mapped[str | None] = mapped_column(
        sa.String(64),
        default=None,
        index=True,
        comment='Linked sandbox ID for this session'
    )
    
    # Credit tracking (negative values = consumption)
    credits: Mapped[float] = mapped_column(
        sa.Float, 
        default=0.0,
        comment='Total credits used in this session'
    )
    
    # Token usage statistics
    total_prompt_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Total prompt tokens used'
    )
    total_completion_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='Total completion tokens used'
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now, onupdate=timezone.now
    )

