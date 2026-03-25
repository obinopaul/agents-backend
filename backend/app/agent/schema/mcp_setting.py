"""MCP Settings Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Tool Type Constants
# ============================================================================

class MCPToolType:
    """Constants for MCP tool types."""
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    CUSTOM = "custom"


# ============================================================================
# Request Models
# ============================================================================

class CodexConfigureRequest(BaseModel):
    """Request model for configuring Codex MCP."""
    
    auth_json: Optional[dict[str, Any]] = Field(
        None, 
        description="Codex authentication JSON (e.g., from ~/.codex/auth.json)"
    )
    apikey: Optional[str] = Field(
        None, 
        description="OpenAI API key (alternative to auth_json)"
    )
    model: Optional[str] = Field(
        "gpt-4o",
        description="Model to use with Codex"
    )
    model_reasoning_effort: Optional[str] = Field(
        "medium",
        description="Reasoning effort level: low, medium, high"
    )
    search: bool = Field(
        False,
        description="Enable search capability"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "apikey": "sk-...",
                "model": "gpt-4o",
                "model_reasoning_effort": "medium",
                "search": False
            }
        }


class ClaudeCodeConfigureRequest(BaseModel):
    """Request model for configuring Claude Code MCP via OAuth."""
    
    authorization_code: str = Field(
        ...,
        description="OAuth authorization code in format: code#verifier"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "authorization_code": "abc123#verifier456"
            }
        }


class CustomMCPConfigureRequest(BaseModel):
    """Request model for configuring a custom MCP server."""
    
    name: str = Field(..., description="Unique name for this MCP server")
    command: str = Field(..., description="Command to run (e.g., 'npx')")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    transport: str = Field("stdio", description="Transport type: stdio or sse")
    env: Optional[dict[str, str]] = Field(None, description="Environment variables")


class MCPSettingUpdate(BaseModel):
    """Request model for updating MCP settings."""
    
    mcp_config: Optional[dict[str, Any]] = Field(None, description="MCP configuration")
    auth_json: Optional[dict[str, Any]] = Field(None, description="Authentication JSON")
    metadata_json: Optional[dict[str, Any]] = Field(None, description="Additional metadata")
    is_active: Optional[bool] = Field(None, description="Whether setting is active")


# ============================================================================
# Response Models
# ============================================================================

class MCPSettingInfo(BaseModel):
    """Response model for MCP setting information."""
    
    id: int
    user_id: int
    tool_type: str
    mcp_config: dict[str, Any]
    # Note: auth_json is intentionally excluded from response for security
    metadata_json: Optional[dict[str, Any]] = None
    is_active: bool
    store_path: Optional[str] = None
    created_time: datetime
    updated_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class MCPSettingList(BaseModel):
    """Response model for list of MCP settings."""
    
    settings: list[MCPSettingInfo]
    total: int


class MCPSettingCreateResponse(BaseModel):
    """Response after creating/updating MCP setting."""
    
    id: int
    tool_type: str
    is_active: bool
    message: str


# ============================================================================
# OAuth Models
# ============================================================================

class ClaudeCodeOAuthTokens(BaseModel):
    """OAuth tokens returned from Claude Code token exchange."""
    
    access_token: str
    refresh_token: str
    expires_in: int
    expires_at: Optional[int] = None  # Computed: current_time + expires_in * 1000


class ClaudeCodeAuthJson(BaseModel):
    """Format for storing Claude Code OAuth in sandbox credentials file."""
    
    claudeAiOauth: dict[str, Any] = Field(
        ...,
        description="OAuth data with accessToken, refreshToken, expiresAt, scopes"
    )
