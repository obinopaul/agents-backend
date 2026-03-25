# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Pydantic schemas for Chat Session API.

Defines request/response models for chat session management endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# =============================================================================
# Session Schemas
# =============================================================================

class ChatSessionCreate(BaseModel):
    """Request schema for creating a new chat session."""
    
    name: Optional[str] = Field(None, max_length=255, description="Session name")
    agent_type: Optional[str] = Field("general", description="Agent type")
    llm_setting_id: Optional[str] = Field(None, description="LLM configuration ID")


class ChatSessionUpdate(BaseModel):
    """Request schema for updating a chat session."""
    
    name: Optional[str] = Field(None, max_length=255)
    agent_type: Optional[str] = None
    llm_setting_id: Optional[str] = None
    status: Optional[str] = None


class ChatSessionInfo(BaseModel):
    """Response schema for chat session information."""
    
    id: str = Field(..., description="Session UUID")
    user_id: int = Field(..., description="Owner user ID")
    name: Optional[str] = Field(None, description="Session name")
    description: Optional[str] = Field(None, description="Session description")
    status: str = Field(..., description="Session status")
    agent_type: Optional[str] = Field(None, description="Agent type")
    sandbox_id: Optional[str] = Field(None, description="Linked sandbox ID")
    workspace_dir: Optional[str] = Field(None, description="Workspace directory")
    is_public: bool = Field(False, description="Whether session is public")
    public_slug: Optional[str] = Field(None, description="Public URL slug")
    message_count: int = Field(0, description="Number of messages")
    total_tokens: int = Field(0, description="Total tokens used")
    total_credits_used: float = Field(0.0, description="Credits consumed")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatSessionList(BaseModel):
    """Response schema for paginated session list."""
    
    sessions: List[ChatSessionInfo]
    total: int
    page: int
    per_page: int
    pages: int


class ChatSessionPublish(BaseModel):
    """Request schema for publishing a session."""
    
    public_slug: Optional[str] = Field(
        None, 
        max_length=64,
        description="Custom URL slug for public access"
    )


# =============================================================================
# Event Schemas
# =============================================================================

class ChatEventInfo(BaseModel):
    """Response schema for chat event information."""
    
    id: str = Field(..., description="Event UUID")
    session_id: Optional[str] = Field(None, description="Session UUID")
    type: str = Field(..., description="Event type")
    role: Optional[str] = Field(None, description="Message role")
    content: Dict[str, Any] = Field(default_factory=dict, description="Event content")
    text: Optional[str] = Field(None, description="Plain text content")
    run_id: Optional[str] = Field(None, description="Agent run ID")
    tool_name: Optional[str] = Field(None, description="Tool name for tool events")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID")
    file_ids: Optional[List[str]] = Field(None, description="Attached file IDs")
    tokens: Optional[Dict[str, int]] = Field(None, description="Token usage")
    model: Optional[str] = Field(None, description="LLM model used")
    latency_ms: Optional[int] = Field(None, description="Processing latency")
    error: Optional[Dict[str, str]] = Field(None, description="Error info")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatEventList(BaseModel):
    """Response schema for paginated event list."""
    
    events: List[ChatEventInfo]
    total: int
    page: int
    per_page: int


# =============================================================================
# Message Schemas (for II-Agent compatibility)
# =============================================================================

class SessionInfoCompat(BaseModel):
    """
    II-Agent compatible SessionInfo format.
    
    This matches the format expected by the II-Agent frontend.
    """
    
    id: str
    user_id: str
    name: Optional[str] = None
    status: str = "active"
    sandbox_id: Optional[str] = None
    agent_type: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    workspace_dir: Optional[str] = None
    is_public: bool = False
    token_usage: Optional[Dict[str, int]] = None


# =============================================================================
# Message History Schemas (for frontend ChatHistoryResponse compatibility)
# =============================================================================

class ContentPart(BaseModel):
    """A content part matching the frontend ContentPart type."""
    type: str = "text"
    text: Optional[str] = None


class FileInfo(BaseModel):
    """File attachment info for messages."""
    id: str
    file_name: str
    file_size: int = 0
    content_type: str = "application/octet-stream"
    created_at: Optional[str] = None


class ChatHistoryMessage(BaseModel):
    """
    Message format matching the frontend ChatHistoryMessage type.

    This is what the frontend expects from the /messages endpoint:
    - content: ContentPart[] (array of {type, text})
    - role: 'user' | 'assistant'
    - files: FileInfo[]
    """
    id: str
    role: str
    content: List[ContentPart]
    usage: Optional[Dict[str, Any]] = None
    tokens: Optional[int] = None
    model: Optional[str] = None
    created_at: Optional[str] = None
    files: List[FileInfo] = Field(default_factory=list)
    finish_reason: Optional[str] = None


class ChatHistoryMessageList(BaseModel):
    """
    Response matching the frontend ChatHistoryResponse type.

    Fields: messages, has_more, total_count
    """
    messages: List[ChatHistoryMessage]
    has_more: bool = False
    total_count: int = 0


# =============================================================================
# Response Wrappers
# =============================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    
    success: bool = True
    message: str = "Operation completed successfully"


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    
    success: bool
    deleted: bool
    session_id: str
