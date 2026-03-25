# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for sandbox status command."""

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


class SandboxStatusHandler(CommandHandler):
    """
    Handler for sandbox_status command.
    
    Returns the current status of the sandbox linked to a session,
    including the VS Code URL if available.
    
    Sandbox statuses:
    - "running": Sandbox is active and ready
    - "paused": Sandbox is paused (can be resumed)
    - "not_linked": No sandbox linked to this session
    - "no_session": Session not found
    - "error": Error getting status
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.SANDBOX_STATUS

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle sandbox status request.
        
        Uses the SandboxController to get sandbox status from the database,
        and exposes VS Code port if sandbox is running.
        
        :param content: Command content (not used)
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        try:
            # Get session to find sandbox_id
            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, session_uuid)
                
                if not session:
                    await self.emit_to_sid(
                        sid=sid,
                        event_type='sandbox_status',
                        content={
                            'session_uuid': session_uuid,
                            'status': 'no_session',
                            'sandbox_id': None,
                            'vscode_url': None,
                        }
                    )
                    return
                
                sandbox_id = session.sandbox_id
            
            if not sandbox_id:
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_status',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'not_linked',
                        'sandbox_id': None,
                        'vscode_url': None,
                    }
                )
                return
            
            # Get sandbox status using the controller
            try:
                controller = sandbox_service.controller
                
                # Get status from database
                status = await controller.get_sandbox_status(sandbox_id)
                
                # Get full sandbox info for additional details
                sandbox_info = await controller.get_sandbox_info(sandbox_id)
                
                # Try to get VS Code URL if sandbox is running
                vscode_url = None
                if status == "running":
                    try:
                        vscode_url = await controller.expose_port(
                            sandbox_id, 
                            settings.SANDBOX_CODE_SERVER_PORT
                        )
                    except Exception as e:
                        logger.debug(f"Could not expose VS Code port: {e}")
                
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_status',
                    content={
                        'session_uuid': session_uuid,
                        'status': status,
                        'sandbox_id': sandbox_id,
                        'vscode_url': vscode_url,
                        'provider_sandbox_id': str(sandbox_info.provider_sandbox_id) if sandbox_info else None,
                        'created_at': sandbox_info.created_at.isoformat() if sandbox_info and sandbox_info.created_at else None,
                        'last_activity_at': sandbox_info.last_activity_at.isoformat() if sandbox_info and sandbox_info.last_activity_at else None,
                    }
                )
                
            except SandboxNotFoundException:
                logger.warning(f"Sandbox {sandbox_id} not found in database")
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_status',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'not_found',
                        'sandbox_id': sandbox_id,
                        'vscode_url': None,
                    }
                )
                
            except Exception as e:
                logger.warning(f"Could not get sandbox status for {sandbox_id}: {e}")
                await self.emit_to_sid(
                    sid=sid,
                    event_type='sandbox_status',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'error',
                        'sandbox_id': sandbox_id,
                        'error': str(e),
                    }
                )
            
        except Exception as e:
            logger.error(f"Error getting sandbox status: {e}", exc_info=True)
            await self.send_error(
                room=sid,
                message=f"Failed to get sandbox status: {str(e)}"
            )
