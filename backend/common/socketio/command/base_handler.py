# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Base command handler for Socket.IO chat messages.

Provides the abstract base class and common functionality for all command handlers.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
import uuid
import logging

import socketio

from backend.common.log import log

logger = logging.getLogger(__name__)


class UserCommandType(str, Enum):
    """Types of commands that can be sent from the frontend."""
    
    INIT_AGENT = "init_agent"
    QUERY = "query"
    WORKSPACE_INFO = "workspace_info"
    AWAKE_SANDBOX = "awake_sandbox"
    SANDBOX_STATUS = "sandbox_status"
    PING = "ping"
    CANCEL = "cancel"
    ENHANCE_PROMPT = "enhance_prompt"
    PUBLISH_PROJECT = "publish"


class CommandHandler(ABC):
    """
    Abstract base class for command handlers.
    
    Command handlers process specific types of chat messages from the frontend.
    Each handler is responsible for:
    1. Validating the incoming command
    2. Processing the command (calling services, running agents, etc.)
    3. Sending response events back to the client
    
    Subclasses must implement:
    - get_command_type(): Return the UserCommandType this handler processes
    - handle(): Process the command
    """

    def __init__(self, sio: socketio.AsyncServer, namespace: str = '/ws') -> None:
        """
        Initialize the command handler.
        
        :param sio: Socket.IO server instance for emitting events
        :param namespace: Socket.IO namespace (default '/ws')
        """
        self.sio = sio
        self.namespace = namespace

    @abstractmethod
    def get_command_type(self) -> UserCommandType:
        """Return the command type this handler processes."""
        pass

    @abstractmethod
    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle the command with the given content and session.
        
        :param content: Command content dictionary from frontend
        :param session_uuid: Chat session UUID
        :param user_id: Authenticated user ID
        :param sid: Socket.IO session ID (for direct responses)
        """
        pass

    # =========================================================================
    # Event Emission Helpers
    # =========================================================================

    async def emit_chat_event(
        self,
        room: str,
        event_type: str,
        content: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> None:
        """
        Emit a chat event to a room (session).
        
        :param room: Room name (usually session_uuid)
        :param event_type: Event type string
        :param content: Event content
        :param run_id: Optional run ID for grouping events
        """
        event_data = {
            'type': event_type,
            'content': content,
        }
        if run_id:
            event_data['run_id'] = run_id
            
        await self.sio.emit(
            'chat_event',
            event_data,
            room=room,
            namespace=self.namespace
        )

    async def emit_to_sid(
        self,
        sid: str,
        event_type: str,
        content: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> None:
        """
        Emit an event directly to a specific SID.
        
        :param sid: Socket.IO session ID
        :param event_type: Event type string
        :param content: Event content
        :param run_id: Optional run ID
        """
        await self.emit_chat_event(
            room=sid,
            event_type=event_type,
            content=content,
            run_id=run_id
        )

    async def broadcast_to_session(
        self,
        session_uuid: str,
        event_type: str,
        content: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> None:
        """
        Broadcast an event to all clients in a session.
        
        :param session_uuid: Session UUID (room name)
        :param event_type: Event type string
        :param content: Event content
        :param run_id: Optional run ID
        """
        await self.emit_chat_event(
            room=session_uuid,
            event_type=event_type,
            content=content,
            run_id=run_id
        )

    async def send_error(
        self,
        room: str,
        message: str,
        error_type: str = "error",
        run_id: Optional[str] = None
    ) -> None:
        """
        Send an error event.
        
        :param room: Room name or SID
        :param message: Error message
        :param error_type: Error type for frontend handling
        :param run_id: Optional run ID
        """
        await self.emit_chat_event(
            room=room,
            event_type='error',
            content={
                'message': message,
                'error_type': error_type,
            },
            run_id=run_id
        )

    async def send_system_event(
        self,
        room: str,
        message: str,
        run_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Send a system event.
        
        :param room: Room name or SID
        :param message: System message
        :param run_id: Optional run ID
        :param kwargs: Additional content fields
        """
        content = {'message': message}
        content.update(kwargs)
        await self.emit_chat_event(
            room=room,
            event_type='system',
            content=content,
            run_id=run_id
        )

    async def send_status_update(
        self,
        room: str,
        status: str,
        run_id: Optional[str] = None
    ) -> None:
        """
        Send a status update event.
        
        :param room: Room name or SID
        :param status: Status string (e.g., 'running', 'idle', 'error')
        :param run_id: Optional run ID
        """
        await self.emit_chat_event(
            room=room,
            event_type='status_update',
            content={'status': status},
            run_id=run_id
        )

    async def send_processing_event(
        self,
        session_uuid: str,
        message: str,
        run_id: Optional[str] = None
    ) -> None:
        """
        Send a processing event to indicate work in progress.
        
        :param session_uuid: Session UUID
        :param message: Processing message
        :param run_id: Optional run ID
        """
        await self.broadcast_to_session(
            session_uuid=session_uuid,
            event_type='processing',
            content={'message': message},
            run_id=run_id
        )
