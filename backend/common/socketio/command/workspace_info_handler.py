# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for workspace info command."""

import logging
from typing import Dict, Any

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)
from backend.database.db import async_db_session
from backend.app.agent.crud.crud_chat_session import chat_session_dao

logger = logging.getLogger(__name__)


class WorkspaceInfoHandler(CommandHandler):
    """
    Handler for workspace_info command.
    
    Returns the workspace directory path for a session.
    This is used by the frontend to know where files are stored.
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.WORKSPACE_INFO

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle workspace info request.
        
        :param content: Command content (not used)
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        try:
            # Get session to find workspace path
            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, session_uuid)
                
                if not session:
                    await self.send_error(
                        room=sid,
                        message=f"Session {session_uuid} not found"
                    )
                    return
                
                workspace_path = session.workspace_path
            
            await self.emit_to_sid(
                sid=sid,
                event_type='workspace_info',
                content={
                    'session_uuid': session_uuid,
                    'workspace_path': workspace_path,
                }
            )
            
            logger.debug(f"Workspace info sent: {workspace_path}")
            
        except Exception as e:
            logger.error(f"Error getting workspace info: {e}", exc_info=True)
            await self.send_error(
                room=sid,
                message=f"Failed to get workspace info: {str(e)}"
            )
