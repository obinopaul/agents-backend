# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for awake sandbox command."""

import logging
from typing import Dict, Any

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)
from backend.database.db import async_db_session
from backend.app.agent.crud.crud_chat_session import chat_session_dao
from backend.src.services.sandbox_service import sandbox_service
from backend.src.sandbox.sandbox_server.models.exceptions import (
    SandboxNotFoundException,
    SandboxNotInitializedError,
)
from backend.core.conf import settings

logger = logging.getLogger(__name__)


class AwakeSandboxHandler(CommandHandler):
    """
    Handler for awake_sandbox command.
    
    "Awakens" a sandbox by connecting to it (if running) or resuming it (if paused).
    This is useful when the user returns to a session and needs to reconnect to an
    existing sandbox.
    
    NOTE: This is different from "sandbox persistence" which is a scheduled task
    that prevents E2B from deleting sandboxes after their 1-hour timeout. The
    awake handler is for user-triggered reconnection.
    
    Workflow:
    1. Look up the session to get the linked sandbox_id
    2. Call controller.connect() which:
       - If sandbox is "running": Connect to it
       - If sandbox is "paused": Resume it and connect
    3. Expose VS Code port and return the URL
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.AWAKE_SANDBOX

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle awake sandbox request.
        
        Uses the SandboxController's connect() method which handles both
        connecting to running sandboxes and resuming paused ones.
        
        :param content: Command content (not used)
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        try:
            await self.send_processing_event(
                session_uuid=session_uuid,
                message="Waking up sandbox..."
            )
            
            # Get session to find sandbox_id
            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, session_uuid)
                
                if not session:
                    await self.send_error(
                        room=sid,
                        message=f"Session {session_uuid} not found"
                    )
                    return
                
                sandbox_id = session.sandbox_id
            
            # If no sandbox linked, inform the user
            if not sandbox_id:
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_awake',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'not_linked',
                        'message': 'No sandbox linked to this session. Send a message to create one.',
                    }
                )
                return
            
            # Connect to or resume the sandbox using the controller
            try:
                controller = sandbox_service.controller
                
                # Check current status first
                status = await controller.get_sandbox_status(sandbox_id)
                logger.info(f"Sandbox {sandbox_id} current status: {status}")
                
                # connect() handles both "running" and "paused" states
                # - "running": Just connects to existing sandbox
                # - "paused": Resumes the sandbox and connects
                sandbox = await controller.connect(sandbox_id)
                
                # Get VS Code URL
                vscode_url = None
                try:
                    vscode_url = await sandbox.expose_port(settings.SANDBOX_CODE_SERVER_PORT)
                except Exception as e:
                    logger.debug(f"Could not expose VS Code port: {e}")
                
                # Get Codex URL
                codex_url = None
                try:
                    codex_url = await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT)
                except Exception as e:
                    logger.debug(f"Could not expose Codex port: {e}")
                
                # Get MCP URL
                mcp_url = None
                try:
                    mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
                except Exception as e:
                    logger.debug(f"Could not expose MCP port: {e}")
                
                # Get Excalidraw URL
                excalidraw_url = None
                try:
                    excalidraw_url = await sandbox.expose_port(settings.SANDBOX_EXCALIDRAW_PORT)
                except Exception as e:
                    logger.debug(f"Could not expose Excalidraw port: {e}")
                
                # Get LaTeX URL
                latex_url = None
                try:
                    latex_url = await sandbox.expose_port(settings.SANDBOX_LATEX_EDITOR_PORT)
                except Exception as e:
                    logger.debug(f"Could not expose LaTeX editor port: {e}")
                
                was_resumed = status == "paused"
                
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_awake',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'awake',
                        'sandbox_id': sandbox_id,
                        'was_resumed': was_resumed,
                        'message': 'Sandbox resumed' if was_resumed else 'Sandbox connected',
                        'vscode_url': vscode_url,
                        'mcp_url': mcp_url,
                        'excalidraw_url': excalidraw_url,
                        'latex_url': latex_url,
                        'codex_url': codex_url,
                    }
                )
                
                logger.info(f"Sandbox {sandbox_id} awakened for session {session_uuid} (was_resumed={was_resumed})")
                
            except SandboxNotFoundException:
                logger.warning(f"Sandbox {sandbox_id} not found in database")
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_awake',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'not_found',
                        'sandbox_id': sandbox_id,
                        'message': 'Sandbox no longer exists. Send a message to create a new one.',
                    }
                )
                
                # Clear the sandbox_id from the session since it's invalid
                async with async_db_session() as db:
                    session = await chat_session_dao.get_by_uuid(db, session_uuid)
                    if session:
                        session.sandbox_id = None
                        await db.commit()
                
            except SandboxNotInitializedError as e:
                logger.warning(f"Sandbox {sandbox_id} in invalid state: {e}")
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_awake',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'invalid_state',
                        'sandbox_id': sandbox_id,
                        'error': str(e),
                        'message': 'Sandbox is in an invalid state. Send a message to create a new one.',
                    }
                )
                
            except Exception as e:
                logger.warning(f"Could not awake sandbox {sandbox_id}: {e}")
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_awake',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'error',
                        'sandbox_id': sandbox_id,
                        'error': str(e),
                    }
                )
            
        except Exception as e:
            logger.error(f"Error awakening sandbox: {e}", exc_info=True)
            await self.send_error(
                room=sid,
                message=f"Failed to awake sandbox: {str(e)}"
            )
