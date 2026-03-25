# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for ping command."""

import logging
from typing import Dict, Any

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)

logger = logging.getLogger(__name__)


class PingHandler(CommandHandler):
    """
    Handler for ping command.
    
    Responds with a pong event to verify connection is alive.
    This can be used by the frontend for keepalive and latency measurement.
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.PING

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle ping message by responding with pong.
        
        :param content: May contain 'timestamp' for latency measurement
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        timestamp = content.get('timestamp')
        
        await self.emit_to_sid(
            sid=sid,
            event_type='pong',
            content={
                'timestamp': timestamp,
                'session_uuid': session_uuid,
            }
        )
        
        logger.debug(f"Pong sent to {sid} for session {session_uuid}")
