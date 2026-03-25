# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Socket.IO chat handlers.

Extends the existing Socket.IO server with chat-specific event handlers:
- join_session: Join a chat session room
- leave_session: Leave a chat session room
- chat_message: Handle incoming chat messages (routed to command handlers)
"""

import logging
import uuid
from typing import Dict, Any, Optional

from backend.common.socketio.server import sio
from backend.common.socketio.session_store import session_store
from backend.common.socketio.rate_limiter import websocket_rate_limiter, init_rate_limiter
from backend.common.log import log
from backend.database.db import async_db_session
from backend.app.agent.service.chat_session_service import chat_session_service
from backend.common.security.jwt import jwt_authentication

logger = logging.getLogger(__name__)

# Command handler factory (initialized during init_chat_handlers)
_command_factory = None


class SocketIOChatManager:
    """
    Manages Socket.IO chat connections and message routing.
    
    This class extends the existing Socket.IO server with chat functionality,
    handling session management, message routing, and event broadcasting.
    """

    def __init__(self):
        self.sio = sio
        # SID to session UUID mapping (in-memory, backed by Redis via session_store)
        self.sid_session_map: Dict[str, str] = {}

    def init_handlers(self):
        """Initialize chat-specific event handlers on the existing sio server."""
        # Additional connect handler for storing auth data
        # Note: The main connect handler is in server.py
        
        # Register chat events on /ws namespace
        self.sio.on('join_session', namespace='/ws')(self.join_session)
        self.sio.on('leave_session', namespace='/ws')(self.leave_session)
        self.sio.on('chat_message', namespace='/ws')(self.chat_message)
        
        logger.info("Socket.IO chat handlers initialized")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _emit_chat_event(
        self, 
        room: str, 
        event_type: str, 
        content: Dict[str, Any],
        namespace: str = '/ws'
    ) -> None:
        """Helper to emit chat events in standard format."""
        await self.sio.emit(
            'chat_event',
            {
                'type': event_type,
                'content': content,
            },
            room=room,
            namespace=namespace
        )

    async def _emit_error(self, room: str, message: str) -> None:
        """Emit an error event."""
        await self._emit_chat_event(room, 'error', {'message': message})

    async def _emit_system_event(self, room: str, message: str, **kwargs) -> None:
        """Emit a system event."""
        content = {'message': message}
        content.update(kwargs)
        await self._emit_chat_event(room, 'system', content)

    async def _emit_status_update(self, room: str, status: str) -> None:
        """Emit a status update event."""
        await self._emit_chat_event(room, 'status_update', {'status': status})

    async def _get_user_id_from_session(self, sid: str) -> Optional[int]:
        """Extract user_id from Socket.IO session data."""
        try:
            session_data = await self.sio.get_session(sid, namespace='/ws')
            if session_data and session_data.get('authenticated'):
                return session_data.get('user_id')
        except Exception as e:
            logger.warning(f"Failed to get user_id from session for {sid}: {e}")
            
        # Fallback: Check manual Redis key
        try:
            from backend.database.redis import redis_client
            import json
            fallback_key = f"agents:auth:{sid}"
            data_str = await redis_client.get(fallback_key)
            if data_str:
                data = json.loads(data_str)
                if data.get('authenticated'):
                    return data.get('user_id')
        except Exception as ex:
            logger.warning(f"Fallback auth check failed for {sid}: {ex}")
            
        return None

    async def _require_session(self, session_uuid: str, sid: str) -> Optional[dict]:
        """
        Validate that a chat session exists in the database and return session info.

        This follows the II-Agent pattern of validating session existence rather than
        re-checking user authentication on every message. Authentication is already
        verified at connect time and in join_session.

        Args:
            session_uuid: Session UUID from the message
            sid: Socket.IO session ID for error emission

        Returns:
            Session info dict with 'id', 'user_id', 'uuid', etc. or None if not found
        """
        if not session_uuid:
            logger.error(f"No session_uuid provided for {sid}")
            return None

        try:
            async with async_db_session() as db:
                session = await chat_session_service.find_by_uuid(db, session_uuid)
                if session:
                    return {
                        'id': session.id,
                        'user_id': session.user_id,
                        'uuid': session.uuid,
                        'name': session.name,
                        'agent_type': session.agent_type,
                        'sandbox_id': session.sandbox_id,
                    }
                else:
                    logger.warning(f"Session {session_uuid} not found in database")
                    return None
        except Exception as e:
            logger.error(f"Error looking up session {session_uuid}: {e}")
            return None

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def join_session(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle join_session event.
        
        Creates or joins a chat session room and stores session mappings.
        
        Expected data:
        {
            "session_uuid": "uuid-string" (optional, will create if not provided)
        }
        """
        try:
            # Get stored session data for user authentication
            session_data = await self.sio.get_session(sid, namespace='/ws')
            if not session_data or not session_data.get('authenticated'):
                # Try Fallback Auth
                from backend.database.redis import redis_client
                import json
                try:
                    fallback_key = f"agents:auth:{sid}"
                    data_str = await redis_client.get(fallback_key)
                    if data_str:
                        fallback_data = json.loads(data_str)
                        if fallback_data.get('authenticated'):
                            session_data = fallback_data
                            logger.info(f"Fallback auth success for join_session: {sid}")
                except Exception as ex:
                    logger.warning(f"Fallback auth check failed in join_session for {sid}: {ex}")

            if not session_data or not session_data.get('authenticated'):
                logger.error(f"No valid session data found for {sid}")
                await self._emit_error(sid, "Not authenticated")
                # Emit idle status to stop the frontend spinner
                await self._emit_status_update(sid, 'idle')
                return

            user_id = session_data.get('user_id')
            session_uuid = data.get('session_uuid')
            
            logger.info(f"Joining session for user {user_id}, session: {session_uuid or 'new'}")

            # Get or create chat session in database
            async with async_db_session() as db:
                session, created = await chat_session_service.get_or_create(
                    db=db,
                    session_uuid=session_uuid,
                    user_id=user_id
                )
                await db.commit()
                
                session_uuid = session.uuid
                session_info = session.to_session_info()

            # Emit system event with session info
            await self._emit_system_event(
                sid, 
                "Session created" if created else "Session joined",
                session_id=session_uuid,
                session_info=session_info
            )

            logger.info(
                f"Chat session {session_uuid} {'created' if created else 'joined'} for user {user_id}: {sid}"
            )

            # Join the Socket.IO room for this session
            await self.sio.enter_room(sid, session_uuid, namespace='/ws')
            self.sid_session_map[sid] = session_uuid

            # Add SID to session mapping in Redis
            await session_store.add_sid_to_session(session_uuid, sid)

            # Get connection count
            sids = await session_store.get_session_sids(session_uuid)
            logger.debug(f"Socket {sid} joined room {session_uuid}, connection count: {len(sids)}")

            # Emit connection established event
            await self._emit_chat_event(
                room=sid,
                event_type='connection_established',
                content={
                    'message': 'Connected to Chat Session',
                    'session_id': session_uuid,
                    'workspace_path': session_info.get('workspace_dir'),
                }
            )

        except Exception as e:
            logger.error(f"Error joining session for {sid}: {e}", exc_info=True)
            await self._emit_error(sid, f"Session initialization failed: {str(e)}")

    async def leave_session(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle leave_session event.
        
        Removes the client from the session room and cleans up mappings.
        """
        logger.info(f"Socket.IO client leaving session: {sid}")
        
        session_uuid = self.sid_session_map.pop(sid, None)
        if not session_uuid:
            session_uuid = data.get('session_uuid')
        
        if session_uuid:
            await self.sio.leave_room(sid, session_uuid, namespace='/ws')
            await session_store.remove_sid_from_session(session_uuid, sid)
            
            # Check if we need to clean up (all clients disconnected)
            is_empty = await session_store.is_session_empty(session_uuid)
            if is_empty:
                logger.info(f"Session {session_uuid} is now empty")
                # Could trigger sandbox cleanup here if needed

    async def chat_message(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle incoming chat messages.

        Routes messages to appropriate command handlers based on message type.

        Expected data:
        {
            "session_uuid": "uuid-string",
            "type": "query|cancel|ping|sandbox_status|...",
            "content": { ... }
        }
        """
        global _command_factory

        logger.info(f"Received chat message from {sid}: type={data.get('type')}")

        session_uuid = data.get('session_uuid')
        if not session_uuid:
            # Try to get from mapping
            session_uuid = self.sid_session_map.get(sid)

        if not session_uuid:
            logger.error(f"No session_uuid provided for message from {sid}")
            await self._emit_error(sid, "session_uuid is required")
            return

        # Get user_id from Socket.IO session (saved during connect)
        # This is the authoritative source - the user was authenticated during connect
        user_id = await self._get_user_id_from_session(sid)
        if not user_id:
            logger.error(f"No authenticated user_id for {sid}")
            await self._emit_error(sid, "Not authenticated. Please refresh the page.")
            await self._emit_status_update(sid, 'idle')
            return

        # Try to find existing session first (fast path)
        try:
            async with async_db_session() as db:
                session = await chat_session_service.find_by_uuid(db, session_uuid)
                
                # If not found, try get_or_create (slow path with locking/creation)
                if not session:
                     try:
                        session, created = await chat_session_service.get_or_create(
                            db=db,
                            session_uuid=session_uuid,
                            user_id=user_id
                        )
                        await db.commit()
                        
                        if created:
                            logger.info(f"Created session {session_uuid} via chat_message for user {user_id}")
                            # Also update the SID mapping
                            self.sid_session_map[sid] = session_uuid
                            await session_store.add_sid_to_session(session_uuid, sid)
                            
                     except Exception as e:
                        # Handle race condition where join_session created it in parallel
                         logger.warning(f"Race condition in chat_message for {session_uuid}: {e}")
                         # Retry find
                         session = await chat_session_service.find_by_uuid(db, session_uuid)
                         if not session:
                             raise e # Real error if still not found

        except Exception as e:
            logger.error(f"Failed to get/create session {session_uuid}: {e}")
            await self._emit_error(sid, "Session initialization failed. Please refresh the page.")
            await self._emit_status_update(sid, 'idle')
            return

        message_type = data.get('type')
        content = data.get('content', {})

        # Check rate limit before processing
        is_allowed, rate_info = await websocket_rate_limiter.check_limit(
            message_type=message_type,
            user_id=user_id,
            session_uuid=session_uuid
        )

        if not is_allowed:
            error_content = websocket_rate_limiter.create_error_content(rate_info)
            await self._emit_chat_event(
                room=sid,
                event_type='error',
                content=error_content
            )
            logger.warning(
                f"Rate limit blocked message from user {user_id}, "
                f"session {session_uuid}, type {message_type}"
            )
            return

        try:
            logger.debug(f"Processing message of type: {message_type}")

            # Route to command handler
            if _command_factory:
                handler = _command_factory.get_handler_by_string(message_type)
                if handler:
                    # Pass session info to handler
                    await handler.handle(
                        content=content,
                        session_uuid=session_uuid,
                        user_id=user_id,
                        sid=sid
                    )
                else:
                    await self._emit_chat_event(
                        sid,
                        'error',
                        {'message': f"Unknown message type: {message_type}"}
                    )
            else:
                # No command factory initialized yet, handle basic types
                if message_type == 'ping':
                    await self._emit_chat_event(
                        sid, 
                        'pong', 
                        {'timestamp': data.get('content', {}).get('timestamp')}
                    )
                else:
                    await self._emit_error(
                        sid, 
                        f"Command handlers not initialized. Message type: {message_type}"
                    )
                    
        except Exception as e:
            logger.error(f"Error handling chat message from {sid}: {e}", exc_info=True)
            await self._emit_error(sid, f"Error processing message: {str(e)}")

    async def disconnect_handler(self, sid: str) -> None:
        """
        Handle Socket.IO disconnection cleanup.
        
        This should be called from the main disconnect handler or integrated
        with it to clean up chat session mappings.
        """
        logger.info(f"Cleaning up chat session for disconnecting client: {sid}")
        
        session_uuid = self.sid_session_map.pop(sid, None)
        
        if session_uuid:
            try:
                await self.sio.leave_room(sid, session_uuid, namespace='/ws')
                await session_store.remove_sid_from_session(session_uuid, sid)
                
                # Check if session is now empty
                is_empty = await session_store.is_session_empty(session_uuid)
                if is_empty:
                    logger.info(f"Session {session_uuid} is now empty after disconnect")
                    
            except Exception as e:
                logger.warning(f"Error cleaning up session {session_uuid} for {sid}: {e}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def broadcast_to_session(
        self, 
        session_uuid: str, 
        event_type: str, 
        content: Dict[str, Any]
    ) -> None:
        """
        Broadcast a chat event to all clients in a session.
        
        :param session_uuid: Session UUID (room name)
        :param event_type: Event type string
        :param content: Event content dict
        """
        await self._emit_chat_event(
            room=session_uuid,
            event_type=event_type,
            content=content
        )

    async def get_session_connection_count(self, session_uuid: str) -> int:
        """Get the number of active connections for a session."""
        try:
            sids = await session_store.get_session_sids(session_uuid)
            return len(sids)
        except Exception as e:
            logger.error(f"Failed to get connection count for session {session_uuid}: {e}")
            return 0


# Global instance
chat_manager = SocketIOChatManager()


async def init_chat_handlers():
    """
    Initialize Socket.IO chat handlers.

    Call this during application startup (in registrar.py) after the
    Socket.IO server is configured.

    Note: This is now async to support rate limiter initialization.
    """
    global _command_factory

    chat_manager.init_handlers()

    # Initialize rate limiter
    try:
        await init_rate_limiter()
        logger.info("WebSocket rate limiter initialized")
    except Exception as e:
        logger.warning(f"Rate limiter initialization failed (will use fallback): {e}")

    # Initialize command handlers (lazy import to avoid circular deps)
    try:
        from backend.common.socketio.command import CommandHandlerFactory
        _command_factory = CommandHandlerFactory(sio)
        logger.info("Socket.IO command handlers initialized")
    except ImportError as e:
        logger.warning(f"Command handlers not available (will be added later): {e}")

    log.info("Socket.IO chat handlers initialized successfully")


def init_chat_handlers_sync():
    """
    Synchronous wrapper for init_chat_handlers.

    For backward compatibility with sync initialization code.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        # Already in async context, schedule as task
        asyncio.create_task(init_chat_handlers())
    except RuntimeError:
        # No running loop, create one
        asyncio.run(init_chat_handlers())


def get_chat_manager() -> SocketIOChatManager:
    """Get the global chat manager instance."""
    return chat_manager
