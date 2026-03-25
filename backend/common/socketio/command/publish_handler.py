# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Handler for publishing a project to Vercel.

This handler enables users to deploy their projects to Vercel directly from the sandbox.
It communicates with the sandbox's MCP server to execute Vercel CLI commands.

Based on the ii-agent pattern but adapted for our infrastructure using:
- Our MCPClient from backend.src.tool_server.mcp.client
- Our sandbox_service from backend.src.services.sandbox_service
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import logging
from typing import Any, Dict, Optional

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)
from backend.src.services.sandbox_service import sandbox_service
from backend.src.tool_server.mcp.client import MCPClient
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.app.agent.crud.crud_chat_session import chat_session_dao

logger = logging.getLogger(__name__)


class PublishProjectHandler(CommandHandler):
    """
    Handler for publishing a project to Vercel.
    
    This handler:
    1. Gets the sandbox associated with the session
    2. Connects to the MCP server in the sandbox
    3. Runs Vercel CLI commands to deploy the project
    4. Sends status updates and deployment URL back to the client
    
    Requires:
    - An active sandbox for the session
    - Vercel API key from the user
    - A project to deploy in the sandbox workspace
    """

    # Success marker to detect command completion
    _SUCCESS_MARKER = "__PUBLISH_SUCCESS__"

    def __init__(self, sio: socketio.AsyncServer) -> None:
        """Initialize the publish project handler."""
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.PUBLISH_PROJECT

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle project deployment to Vercel.
        
        Expected content:
        {
            "project_path": "/workspace/my-app",  # Optional, defaults to workspace
            "project_name": "my-app",  # Optional, derived from path
            "vercel_api_key": "xxx",  # Required
            "credentials": {"vercel_api_key": "xxx"}  # Alternative location
        }
        """
        # Get session workspace info
        async with async_db_session() as db:
            session = await chat_session_dao.get_by_uuid(db, session_uuid)
            if not session:
                await self.send_error(
                    room=sid,
                    message="Session not found"
                )
                return
            
            workspace_dir = session.workspace_dir or "/workspace"
            sandbox_id = session.sandbox_id
        
        if not sandbox_id:
            await self.send_error(
                room=session_uuid,
                message="No sandbox associated with this session. Start a conversation first.",
                error_type="no_sandbox"
            )
            return
        
        # Resolve project path
        project_path = self._resolve_project_path(content.get("project_path"), workspace_dir)
        if not project_path:
            await self.send_error(
                room=session_uuid,
                message="Project path is required to publish the project.",
                error_type="missing_project_path"
            )
            return

        # Resolve project name
        project_name = self._resolve_project_name(
            content.get("project_name"), project_path
        )
        
        # Extract Vercel API key
        vercel_api_key = self._extract_api_key(content)
        if not vercel_api_key:
            await self.send_error(
                room=session_uuid,
                message="Vercel API key is required for deployment. Provide it in 'vercel_api_key' or 'credentials.vercel_api_key'.",
                error_type="missing_credentials"
            )
            return

        # Create unique project ID for Vercel
        session_id_hash = hashlib.sha256(session_uuid.encode()).hexdigest()[:8]
        project_id = f"{project_name}-{session_id_hash}"
        shell_session_name = f"deploy-{session_id_hash}"

        # Get sandbox and MCP URL
        try:
            sandbox = sandbox_service.controller.sandboxes.get(sandbox_id)
            if not sandbox:
                await self.send_error(
                    room=session_uuid,
                    message="Sandbox not found or has been terminated.",
                    error_type="sandbox_not_found"
                )
                return
            
            mcp_port = settings.MCP_PORT if hasattr(settings, 'MCP_PORT') else 6060
            sandbox_url = await sandbox.expose_port(mcp_port)
            
        except Exception as e:
            logger.error(f"Failed to get sandbox for deployment: {e}")
            await self.send_error(
                room=session_uuid,
                message=f"Failed to access sandbox: {str(e)}",
                error_type="sandbox_error"
            )
            return

        # Connect to MCP and run deployment
        try:
            async with MCPClient(sandbox_url) as client:
                # Initialize shell session
                await self._ensure_shell_session(
                    client,
                    shell_session_name,
                    project_path,
                )

                # Step 1: Link project with Vercel
                await self.broadcast_to_session(
                    session_uuid=session_uuid,
                    event_type='status_update',
                    content={
                        'status': 'deploying',
                        'message': f"Linking {project_id} with Vercel..."
                    }
                )

                link_command = self._append_success_marker(
                    f"cd {self._shell_quote(project_path)} && "
                    f"vercel link --yes --project {self._shell_quote(project_id)} "
                    f"--token {self._shell_quote(vercel_api_key)}"
                )

                try:
                    link_output = await self._run_shell_command(
                        client,
                        shell_session_name,
                        link_command,
                        description="Link Vercel project",
                        timeout=180,
                    )
                except Exception as exc:
                    await self.send_error(
                        room=session_uuid,
                        message=f"Failed to link project with Vercel: {str(exc)}",
                        error_type="deploy_link_failed"
                    )
                    return

                if not self._command_succeeded(link_output):
                    await self.send_error(
                        room=session_uuid,
                        message=f"Failed to link project with Vercel: {self._cleanup_output(link_output) or 'No output returned.'}",
                        error_type="deploy_link_failed"
                    )
                    return

                await self.broadcast_to_session(
                    session_uuid=session_uuid,
                    event_type='system',
                    content={'message': "Project linked successfully."}
                )

                # Step 2: Deploy to production
                await self.broadcast_to_session(
                    session_uuid=session_uuid,
                    event_type='status_update',
                    content={
                        'status': 'deploying',
                        'message': "Running production deployment..."
                    }
                )

                deploy_command = self._append_success_marker(
                    f"cd {self._shell_quote(project_path)} && "
                    f"vercel --prod --token {self._shell_quote(vercel_api_key)} -y"
                )

                try:
                    deploy_output = await self._run_shell_command(
                        client,
                        shell_session_name,
                        deploy_command,
                        description="Deploy project to Vercel",
                        timeout=300,  # 5 minute timeout for deployment
                    )
                except Exception as exc:
                    await self.send_error(
                        room=session_uuid,
                        message=f"Vercel deployment failed: {str(exc)}",
                        error_type="deploy_failed"
                    )
                    return

                if not self._command_succeeded(deploy_output):
                    await self.send_error(
                        room=session_uuid,
                        message=f"Vercel deployment failed: {self._cleanup_output(deploy_output) or 'No output returned.'}",
                        error_type="deploy_failed"
                    )
                    return

                # Extract deployment URL
                cleaned_output = self._cleanup_output(deploy_output)
                deployment_url = self._extract_deployment_url(cleaned_output, project_id)

            # Send success event
            await self.broadcast_to_session(
                session_uuid=session_uuid,
                event_type='system',
                content={
                    'message': f"Deployment live at {deployment_url}",
                    'deployment_url': deployment_url,
                    'project_id': project_id,
                    'project_name': project_name,
                    'deployment': {
                        'url': deployment_url,
                        'project_id': project_id,
                        'project_name': project_name,
                    }
                }
            )

            await self.send_status_update(
                room=session_uuid,
                status='idle'
            )

        except Exception as e:
            logger.error(f"Deployment error: {e}", exc_info=True)
            await self.send_error(
                room=session_uuid,
                message=f"Deployment failed: {str(e)}",
                error_type="deploy_error"
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _resolve_project_path(
        self, project_path: Optional[str], workspace_dir: str
    ) -> Optional[str]:
        """Resolve the project path relative to workspace."""
        if isinstance(project_path, str) and project_path.strip():
            project_path = project_path.strip()
        else:
            project_path = workspace_dir

        if not isinstance(project_path, str) or not project_path:
            return None

        if project_path.startswith("./"):
            project_path = project_path[2:]

        if not os.path.isabs(project_path):
            project_path = os.path.join(workspace_dir, project_path)

        return project_path.rstrip()

    def _resolve_project_name(
        self, provided_name: Any, project_path: str
    ) -> str:
        """Resolve project name from provided name or path."""
        if isinstance(provided_name, str) and provided_name.strip():
            candidate = provided_name.strip()
        else:
            candidate = os.path.basename(project_path.rstrip(os.sep)) or "project"

        # Sanitize for Vercel project name requirements
        sanitized = re.sub(r"[^a-zA-Z0-9-]+", "-", candidate)
        sanitized = sanitized.strip("-")
        return sanitized.lower() or "project"

    def _extract_api_key(self, content: Dict[str, Any]) -> Optional[str]:
        """Extract Vercel API key from content."""
        # Direct key
        key = content.get("vercel_api_key")
        if isinstance(key, str) and key.strip():
            return key.strip()

        # From credentials dict
        credentials = content.get("credentials")
        if isinstance(credentials, dict):
            key_candidate = credentials.get("vercel_api_key")
            if isinstance(key_candidate, str) and key_candidate.strip():
                return key_candidate.strip()

        # Fallback to generic token
        token = content.get("token")
        if isinstance(token, str) and token.strip():
            return token.strip()

        return None

    async def _ensure_shell_session(
        self,
        client: MCPClient,
        session_name: str,
        start_directory: str,
    ) -> None:
        """Initialize a shell session in the sandbox."""
        try:
            # Use BashInit tool if available
            await client.call_tool("BashInit", {
                "session_name": session_name,
            })
        except Exception as e:
            logger.warning(f"BashInit not available, continuing: {e}")
            # Continue anyway - some sandboxes may not have BashInit

    async def _run_shell_command(
        self,
        client: MCPClient,
        session_name: str,
        command: str,
        *,
        description: str,
        timeout: int = 600,
        wait_for_output: bool = True,
    ) -> str:
        """Run a shell command in the sandbox via MCP."""
        # Try the Bash tool
        result = await client.call_tool("Bash", {
            "session_name": session_name,
            "command": command,
            "description": description,
            "timeout": timeout,
            "wait_for_output": wait_for_output,
        })
        
        return self._extract_tool_output(result)

    def _extract_tool_output(self, result: Any) -> str:
        """Extract text output from MCP tool result."""
        # Handle different result types
        if hasattr(result, 'structured_content') and result.structured_content:
            display = result.structured_content.get("user_display_content")
            if isinstance(display, str):
                return display
            if isinstance(display, list):
                return "\n".join(str(item) for item in display)

        if hasattr(result, 'content'):
            texts = []
            for block in result.content:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    texts.append(text)
            return "\n".join(texts)
        
        # Fallback
        return str(result) if result else ""

    def _append_success_marker(self, command: str) -> str:
        """Append success marker to command for completion detection."""
        return f"{command} && echo {self._SUCCESS_MARKER}"

    def _command_succeeded(self, output: str) -> bool:
        """Check if command succeeded based on output."""
        return bool(output and self._SUCCESS_MARKER in output)

    def _cleanup_output(self, output: str) -> str:
        """Remove success marker from output."""
        if not output:
            return ""
        return output.replace(self._SUCCESS_MARKER, "").strip()

    def _extract_deployment_url(self, output: str, project_id: str) -> str:
        """Extract deployment URL from Vercel output."""
        if output:
            # Try to find Production URL first
            production_match = re.search(
                r"Production:\s*(https://[^\s\]]+)", output, re.IGNORECASE
            )
            if production_match:
                return production_match.group(1)
            
            # Try vercel.app URL
            vercel_match = re.search(
                r"https://[^\s\]]+vercel\.app", output, re.IGNORECASE
            )
            if vercel_match:
                return vercel_match.group(0)
            
            # Try any HTTPS URL
            generic_match = re.search(r"https://[^\s\]]+", output)
            if generic_match:
                return generic_match.group(0)
        
        # Fallback to constructed URL
        return f"https://{project_id}.vercel.app"

    def _shell_quote(self, value: str) -> str:
        """Safely quote a shell argument."""
        return shlex.quote(value)
