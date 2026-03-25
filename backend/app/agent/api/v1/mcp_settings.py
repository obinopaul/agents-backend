"""MCP Settings API endpoints.

Provides user-facing API for configuring MCP tools like Codex and Claude Code.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.app.admin.model import User
from backend.app.agent.model.mcp_setting import MCPSetting
from backend.app.agent.schema.mcp_setting import (
    CodexConfigureRequest,
    ClaudeCodeConfigureRequest,
    CustomMCPConfigureRequest,
    MCPSettingInfo,
    MCPSettingList,
    MCPSettingUpdate,
    MCPToolType,
)
from backend.app.agent.service.mcp_setting_service import mcp_setting_service
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession


router = APIRouter(prefix="/user-settings/mcp", tags=["User MCP Settings"])


def _to_info(setting: MCPSetting) -> MCPSettingInfo:
    """Convert MCPSetting model to MCPSettingInfo response (excludes auth_json)."""
    return MCPSettingInfo(
        id=setting.id,
        user_id=setting.user_id,
        tool_type=setting.tool_type,
        mcp_config=setting.mcp_config,
        metadata_json=setting.metadata_json,
        is_active=setting.is_active,
        store_path=setting.store_path,
        created_time=setting.created_time,
        updated_time=setting.updated_time,
    )


# =============================================================================
# List / Get All Settings
# =============================================================================

@router.get(
    "",
    response_model=MCPSettingList,
    summary="List all MCP settings",
    description="Get all MCP tool configurations for the current user.",
    dependencies=[DependsJwtAuth],
)
async def list_mcp_settings(
    db: CurrentSession,
    only_active: bool = False,
    # TODO: Replace with actual user dependency when available
    # current_user: User = Depends(get_current_user),
):
    """List all MCP settings for the current user."""
    # TODO: Get actual user_id from JWT token
    # For now, using placeholder - this should be replaced with your auth dependency
    user_id = 1  # Placeholder - replace with current_user.id
    
    settings = await mcp_setting_service.get_user_settings(
        db=db,
        user_id=user_id,
        only_active=only_active,
    )
    
    return MCPSettingList(
        settings=[_to_info(s) for s in settings],
        total=len(settings)
    )


# =============================================================================
# Codex Endpoints
# =============================================================================

@router.get(
    "/codex",
    response_model=Optional[MCPSettingInfo],
    summary="Get Codex settings",
    description="Get current Codex MCP configuration for the user.",
    dependencies=[DependsJwtAuth],
)
async def get_codex_settings(db: CurrentSession):
    """Get Codex configuration if exists."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    setting = await mcp_setting_service.get_setting_by_type(
        db=db,
        user_id=user_id,
        tool_type=MCPToolType.CODEX,
    )
    
    return _to_info(setting) if setting else None


@router.post(
    "/codex",
    response_model=MCPSettingInfo,
    summary="Configure Codex",
    description="Configure Codex MCP with authentication. Creates or updates existing config.",
    dependencies=[DependsJwtAuth],
)
async def configure_codex(
    request: CodexConfigureRequest,
    db: CurrentSession,
):
    """Configure Codex MCP for the current user."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    try:
        setting = await mcp_setting_service.configure_codex(
            db=db,
            user_id=user_id,
            request=request,
        )
        return _to_info(setting)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Claude Code Endpoints
# =============================================================================

@router.get(
    "/claude-code",
    response_model=Optional[MCPSettingInfo],
    summary="Get Claude Code settings",
    description="Get current Claude Code MCP configuration for the user.",
    dependencies=[DependsJwtAuth],
)
async def get_claude_code_settings(db: CurrentSession):
    """Get Claude Code configuration if exists."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    setting = await mcp_setting_service.get_setting_by_type(
        db=db,
        user_id=user_id,
        tool_type=MCPToolType.CLAUDE_CODE,
    )
    
    return _to_info(setting) if setting else None


@router.post(
    "/claude-code",
    response_model=MCPSettingInfo,
    summary="Configure Claude Code",
    description="Configure Claude Code via OAuth. The authorization_code should be in format: code#verifier",
    dependencies=[DependsJwtAuth],
)
async def configure_claude_code(
    request: ClaudeCodeConfigureRequest,
    db: CurrentSession,
):
    """Configure Claude Code MCP via OAuth for the current user."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    try:
        setting = await mcp_setting_service.configure_claude_code(
            db=db,
            user_id=user_id,
            request=request,
        )
        return _to_info(setting)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Custom MCP Endpoints
# =============================================================================

@router.post(
    "/custom",
    response_model=MCPSettingInfo,
    summary="Configure custom MCP",
    description="Configure a custom MCP server.",
    dependencies=[DependsJwtAuth],
)
async def configure_custom_mcp(
    request: CustomMCPConfigureRequest,
    db: CurrentSession,
):
    """Configure a custom MCP server for the current user."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    try:
        setting = await mcp_setting_service.configure_custom_mcp(
            db=db,
            user_id=user_id,
            request=request,
        )
        return _to_info(setting)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Delete / Toggle Endpoints
# =============================================================================

@router.delete(
    "/{tool_type}",
    summary="Delete MCP setting",
    description="Delete an MCP tool configuration.",
    dependencies=[DependsJwtAuth],
)
async def delete_mcp_setting(
    tool_type: str,
    db: CurrentSession,
):
    """Delete MCP setting by tool type."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    deleted = await mcp_setting_service.delete_setting(
        db=db,
        user_id=user_id,
        tool_type=tool_type,
    )
    
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP setting not found")
    
    return {"message": f"MCP setting '{tool_type}' deleted successfully"}


@router.patch(
    "/{tool_type}/toggle",
    response_model=MCPSettingInfo,
    summary="Toggle MCP setting",
    description="Toggle active status of an MCP setting.",
    dependencies=[DependsJwtAuth],
)
async def toggle_mcp_setting(
    tool_type: str,
    is_active: bool,
    db: CurrentSession,
):
    """Toggle MCP setting active status."""
    user_id = 1  # Placeholder - replace with current_user.id
    
    setting = await mcp_setting_service.toggle_setting(
        db=db,
        user_id=user_id,
        tool_type=tool_type,
        is_active=is_active,
    )
    
    if not setting:
        raise HTTPException(status_code=404, detail="MCP setting not found")
    
    return _to_info(setting)
