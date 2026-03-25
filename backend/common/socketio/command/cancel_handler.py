# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for cancel command."""

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

# Store for tracking running agent tasks by session
# In production, this should be stored in Redis for multi-process support
_running_tasks: Dict[str, bool] = {}


def set_task_running(session_uuid: str, running: bool) -> None:
    """Mark a task as running or not running."""
    _running_tasks[session_uuid] = running


def is_task_running(session_uuid: str) -> bool:
    """Check if a task is running for a session."""
    return _running_tasks.get(session_uuid, False)


def should_cancel(session_uuid: str) -> bool:
    """Check if a running task should be cancelled."""
    # If task is not marked as running, it means cancel was requested
    return not _running_tasks.get(session_uuid, True)


class CancelHandler(CommandHandler):
    """
    Handler for cancel command.
    
    Cancels a running agent task for a session.
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.CANCEL

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle cancel request.
        
        :param content: May contain 'run_id' to cancel specific run
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        try:
            run_id = content.get('run_id')
            
            logger.info(f"Cancel requested for session {session_uuid}, run_id: {run_id}")
            
            # Check if there's actually a running task
            if not is_task_running(session_uuid):
                await self.emit_to_sid(
                    sid=sid,
                    event_type='cancel_acknowledged',
                    content={
                        'session_uuid': session_uuid,
                        'status': 'no_task',
                        'message': 'No running task to cancel',
                    }
                )
                return
            
            # Set the flag to trigger cancellation
            # The agent loop should check should_cancel() periodically
            set_task_running(session_uuid, False)
            
            # Notify the frontend
            await self.broadcast_to_session(
                session_uuid=session_uuid,
                event_type='cancel_acknowledged',
                content={
                    'session_uuid': session_uuid,
                    'status': 'cancelling',
                    'message': 'Cancellation requested',
                    'run_id': run_id,
                },
                run_id=run_id
            )
            
            # Send status update
            await self.send_status_update(
                room=session_uuid,
                status='cancelling',
                run_id=run_id
            )
            
            logger.info(f"Cancel acknowledged for session {session_uuid}")
            
        except Exception as e:
            logger.error(f"Error handling cancel: {e}", exc_info=True)
            await self.send_error(
                room=sid,
                message=f"Failed to cancel: {str(e)}"
            )
