"""MCP Settings service layer.

Handles business logic for Codex, Claude Code, and custom MCP configurations.
"""

import time
from typing import Any, Optional, Sequence

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.crud.crud_mcp_setting import mcp_setting_dao
from backend.app.agent.model.mcp_setting import MCPSetting
from backend.app.agent.schema.mcp_setting import (
    CodexConfigureRequest,
    ClaudeCodeConfigureRequest,
    CustomMCPConfigureRequest,
    MCPToolType,
)
from backend.common.exception import errors
from backend.common.log import log


# ==============================================================================
# Claude Code OAuth Configuration
# ==============================================================================
# These are Anthropic's OFFICIAL public OAuth values for CLI applications.
# They are intentionally hardcoded - not secrets.
#
# - Client ID: Public client identifier for Claude Code CLI apps
# - Redirect URI: Anthropic's console callback (shows user a code to copy)
# - Token URL: Endpoint to exchange authorization code for tokens
#
# This is the same approach used by the official `claude` CLI.
# See: https://github.com/anthropics/claude-code
# ==============================================================================
CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_CODE_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
CLAUDE_CODE_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"


class MCPSettingService:
    """Service for managing MCP settings."""

    # =========================================================================
    # Codex Configuration
    # =========================================================================

    @staticmethod
    async def configure_codex(
        *,
        db: AsyncSession,
        user_id: int,
        request: CodexConfigureRequest
    ) -> MCPSetting:
        """
        Configure Codex MCP for a user.
        
        :param db: Database session
        :param user_id: User ID
        :param request: Codex configuration request
        :return: Created/updated MCP setting
        """
        # Validate: need either auth_json or apikey
        auth_json = request.auth_json or {}
        if request.apikey:
            auth_json["OPENAI_API_KEY"] = request.apikey
        
        if not auth_json:
            raise errors.RequestError(msg="Either auth_json or apikey is required")

        # Build MCP server configuration for codex-as-mcp
        uvx_args = [
            "--from", 
            "git+https://github.com/Intelligent-Internet/codex-as-mcp.git@main",
            "codex-as-mcp",
        ]
        
        server_args = ["--yolo"]
        if request.model:
            server_args.append(f"--model={request.model}")
        if request.model_reasoning_effort:
            server_args.append(f"--model_reasoning_effort={request.model_reasoning_effort}")
        if request.search:
            server_args.append("--search")

        mcp_config = {
            "mcpServers": {
                "codex-as-mcp": {
                    "command": "uvx",
                    "type": "stdio",
                    "args": uvx_args + server_args,
                }
            }
        }

        # Store additional metadata
        metadata_json = {
            "model": request.model,
            "model_reasoning_effort": request.model_reasoning_effort,
            "search": request.search,
        }

        result = await mcp_setting_dao.create_or_update(
            db=db,
            user_id=user_id,
            tool_type=MCPToolType.CODEX,
            mcp_config=mcp_config,
            auth_json=auth_json,
            metadata_json=metadata_json,
            store_path="~/.codex",
            is_active=True
        )

        log.info(f"Configured Codex MCP for user {user_id}")
        return result

    # =========================================================================
    # Claude Code Configuration
    # =========================================================================

    @staticmethod
    async def exchange_claude_code_tokens(code: str, verifier: str) -> dict[str, Any]:
        """
        Exchange OAuth authorization code for Claude Code tokens.
        
        :param code: Authorization code
        :param verifier: PKCE code verifier
        :return: Token response with access_token, refresh_token, expires_in
        :raises: HTTPException if exchange fails
        """
        # Handle code that might include state after #
        code_parts = code.split("#")
        actual_code = code_parts[0]
        state = code_parts[1] if len(code_parts) > 1 else verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(
                CLAUDE_CODE_TOKEN_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "code": actual_code,
                    "state": state,
                    "grant_type": "authorization_code",
                    "client_id": CLAUDE_CODE_CLIENT_ID,
                    "redirect_uri": CLAUDE_CODE_REDIRECT_URI,
                    "code_verifier": verifier,
                },
                timeout=30.0
            )

        if not response.is_success:
            log.error(f"Claude Code token exchange failed: {response.text}")
            raise errors.RequestError(
                msg=f"Failed to exchange authorization code: {response.text}"
            )

        data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data["expires_in"],
        }

    @staticmethod
    async def configure_claude_code(
        *,
        db: AsyncSession,
        user_id: int,
        request: ClaudeCodeConfigureRequest
    ) -> MCPSetting:
        """
        Configure Claude Code MCP for a user via OAuth.
        
        :param db: Database session
        :param user_id: User ID
        :param request: Claude Code configuration request
        :return: Created/updated MCP setting
        """
        # Parse authorization code (format: code#verifier)
        parts = request.authorization_code.split("#")
        if len(parts) != 2:
            raise errors.RequestError(
                msg="Invalid authorization code format. Expected: code#verifier"
            )
        
        code, verifier = parts

        # Exchange code for tokens
        tokens = await MCPSettingService.exchange_claude_code_tokens(code, verifier)

        # Build auth_json in Claude Code format
        auth_json = {
            "claudeAiOauth": {
                "accessToken": tokens["access_token"],
                "refreshToken": tokens["refresh_token"],
                "expiresAt": int(time.time() * 1000) + tokens["expires_in"] * 1000,
                "scopes": ["user:inference", "user:profile"],
            }
        }

        # Build MCP config for claude-code-mcp
        mcp_config = {
            "mcpServers": {
                "claude-code-mcp": {
                    "command": "npx",
                    "args": ["-y", "@steipete/claude-code-mcp@latest"],
                }
            }
        }

        result = await mcp_setting_dao.create_or_update(
            db=db,
            user_id=user_id,
            tool_type=MCPToolType.CLAUDE_CODE,
            mcp_config=mcp_config,
            auth_json=auth_json,
            store_path="~/.claude",
            is_active=True
        )

        log.info(f"Configured Claude Code MCP for user {user_id}")
        return result

    # =========================================================================
    # Custom MCP Configuration
    # =========================================================================

    @staticmethod
    async def configure_custom_mcp(
        *,
        db: AsyncSession,
        user_id: int,
        request: CustomMCPConfigureRequest
    ) -> MCPSetting:
        """
        Configure a custom MCP server for a user.
        
        :param db: Database session
        :param user_id: User ID
        :param request: Custom MCP configuration request
        :return: Created/updated MCP setting
        """
        mcp_config = {
            "mcpServers": {
                request.name: {
                    "command": request.command,
                    "args": request.args,
                    "type": request.transport,
                }
            }
        }

        if request.env:
            mcp_config["mcpServers"][request.name]["env"] = request.env

        result = await mcp_setting_dao.create_or_update(
            db=db,
            user_id=user_id,
            tool_type=f"custom:{request.name}",
            mcp_config=mcp_config,
            is_active=True
        )

        log.info(f"Configured custom MCP '{request.name}' for user {user_id}")
        return result

    # =========================================================================
    # General Operations
    # =========================================================================

    @staticmethod
    async def get_user_settings(
        *,
        db: AsyncSession,
        user_id: int,
        only_active: bool = False
    ) -> Sequence[MCPSetting]:
        """
        Get all MCP settings for a user.
        
        :param db: Database session
        :param user_id: User ID
        :param only_active: Only return active settings
        :return: List of MCP settings
        """
        return await mcp_setting_dao.get_by_user_id(db, user_id, only_active)

    @staticmethod
    async def get_setting_by_type(
        *,
        db: AsyncSession,
        user_id: int,
        tool_type: str
    ) -> Optional[MCPSetting]:
        """
        Get specific MCP setting by tool type.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :return: MCP setting or None
        """
        return await mcp_setting_dao.get_by_user_and_type(db, user_id, tool_type)

    @staticmethod
    async def delete_setting(
        *,
        db: AsyncSession,
        user_id: int,
        tool_type: str
    ) -> bool:
        """
        Delete MCP setting.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :return: True if deleted
        """
        result = await mcp_setting_dao.delete_by_user_and_type(db, user_id, tool_type)
        if result:
            log.info(f"Deleted MCP setting {tool_type} for user {user_id}")
        return result

    @staticmethod
    async def toggle_setting(
        *,
        db: AsyncSession,
        user_id: int,
        tool_type: str,
        is_active: bool
    ) -> Optional[MCPSetting]:
        """
        Toggle active status of MCP setting.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :param is_active: Active status
        :return: Updated setting or None
        """
        return await mcp_setting_dao.set_active(db, user_id, tool_type, is_active)

    # =========================================================================
    # Sandbox Credential Helpers
    # =========================================================================

    @staticmethod
    def get_credential_files(setting: MCPSetting) -> list[tuple[str, str]]:
        """
        Get list of credential files to write to sandbox.
        
        :param setting: MCP setting
        :return: List of (path, content) tuples
        """
        import json
        
        files = []
        
        if not setting.auth_json:
            return files

        if setting.tool_type == MCPToolType.CLAUDE_CODE:
            # Write Claude Code OAuth credentials
            files.append((
                "/home/pn/.claude/.credentials.json",
                json.dumps(setting.auth_json, indent=2)
            ))
        elif setting.tool_type == MCPToolType.CODEX:
            # Write Codex auth
            files.append((
                "/home/pn/.codex/auth.json",
                json.dumps(setting.auth_json, indent=2)
            ))

        return files


# Singleton instance
mcp_setting_service: MCPSettingService = MCPSettingService()
