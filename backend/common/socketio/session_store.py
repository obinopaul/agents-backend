# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Session store for managing Socket.IO SID to chat session mappings.

Uses Redis for session storage with TTL-based cleanup.
This enables tracking which Socket.IO connections belong to which chat sessions.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Set, Optional

from backend.database.redis import redis_client
from backend.common.log import log

logger = logging.getLogger(__name__)


class SessionStore(ABC):
    """Abstract base class for session storage."""

    @abstractmethod
    async def add_sid_to_session(self, session_uuid: str, sid: str) -> None:
        """Add a SID to a session's SID set."""
        pass

    @abstractmethod
    async def remove_sid_from_session(self, session_uuid: str, sid: str) -> None:
        """Remove a SID from a session's SID set."""
        pass

    @abstractmethod
    async def get_session_sids(self, session_uuid: str) -> Set[str]:
        """Get all SIDs for a session."""
        pass

    @abstractmethod
    async def get_all_session_sids(self) -> Dict[str, Set[str]]:
        """Get all session SID mappings."""
        pass

    @abstractmethod
    async def is_session_empty(self, session_uuid: str) -> bool:
        """Check if a session has no active SIDs."""
        pass

    @abstractmethod
    async def get_session_for_sid(self, sid: str) -> Optional[str]:
        """Get session UUID for a SID."""
        pass

    @abstractmethod
    async def set_session_for_sid(self, sid: str, session_uuid: str) -> None:
        """Set session UUID for a SID."""
        pass

    @abstractmethod
    async def remove_sid(self, sid: str) -> Optional[str]:
        """Remove SID mapping and return its session UUID."""
        pass


class RedisSessionStore(SessionStore):
    """Redis-based session storage with TTL."""

    def __init__(
        self, 
        redis_key_prefix: str = "chat_session_sids:",
        sid_key_prefix: str = "chat_sid_session:",
        ttl_seconds: int = 3600
    ):
        self.redis = redis_client
        self.redis_key_prefix = redis_key_prefix
        self.sid_key_prefix = sid_key_prefix
        self.ttl_seconds = ttl_seconds

    def _get_session_key(self, session_uuid: str) -> str:
        """Get Redis key for session SIDs."""
        return f"{self.redis_key_prefix}{session_uuid}"

    def _get_sid_key(self, sid: str) -> str:
        """Get Redis key for SID-to-session mapping."""
        return f"{self.sid_key_prefix}{sid}"

    async def add_sid_to_session(self, session_uuid: str, sid: str) -> None:
        """Add a SID to a session's SID set in Redis with TTL."""
        try:
            # Add SID to session's set
            session_key = self._get_session_key(session_uuid)
            await self.redis.sadd(session_key, sid)
            await self.redis.expire(session_key, self.ttl_seconds)
            
            # Also store reverse mapping (SID -> session)
            sid_key = self._get_sid_key(sid)
            await self.redis.set(sid_key, session_uuid)
            await self.redis.expire(sid_key, self.ttl_seconds)
            
            logger.debug(
                f"Added SID {sid} to session {session_uuid} in Redis with {self.ttl_seconds}s TTL"
            )
        except Exception as e:
            logger.error(
                f"Failed to add SID {sid} to session {session_uuid} in Redis: {e}"
            )

    async def remove_sid_from_session(self, session_uuid: str, sid: str) -> None:
        """Remove a SID from a session's SID set in Redis."""
        try:
            session_key = self._get_session_key(session_uuid)
            await self.redis.srem(session_key, sid)
            
            # Remove reverse mapping
            sid_key = self._get_sid_key(sid)
            await self.redis.delete(sid_key)
            
            logger.debug(f"Removed SID {sid} from session {session_uuid} in Redis")

            # Check if the set is empty and clean it up
            remaining_sids = await self.redis.scard(session_key)
            if remaining_sids == 0:
                await self.redis.delete(session_key)
                logger.debug(f"Cleaned up empty session {session_uuid} from Redis")
            else:
                # Refresh TTL for remaining SIDs
                await self.redis.expire(session_key, self.ttl_seconds)
                logger.debug(
                    f"Refreshed TTL for session {session_uuid} with {remaining_sids} remaining SIDs"
                )
        except Exception as e:
            logger.error(
                f"Failed to remove SID {sid} from session {session_uuid} in Redis: {e}"
            )

    async def get_session_sids(self, session_uuid: str) -> Set[str]:
        """Get all SIDs for a session from Redis."""
        try:
            session_key = self._get_session_key(session_uuid)
            sids = await self.redis.smembers(session_key)
            return {sid.decode() if isinstance(sid, bytes) else sid for sid in sids}
        except Exception as e:
            logger.error(
                f"Failed to get SIDs for session {session_uuid} from Redis: {e}"
            )
            return set()

    async def get_all_session_sids(self) -> Dict[str, Set[str]]:
        """Get all session SID mappings from Redis."""
        try:
            pattern = f"{self.redis_key_prefix}*"
            keys = await self.redis.keys(pattern)
            result = {}

            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                session_uuid = key_str.replace(self.redis_key_prefix, "")
                sids = await self.redis.smembers(key)
                result[session_uuid] = {
                    sid.decode() if isinstance(sid, bytes) else sid for sid in sids
                }

            return result
        except Exception as e:
            logger.error(f"Failed to get all session SIDs from Redis: {e}")
            return {}

    async def is_session_empty(self, session_uuid: str) -> bool:
        """Check if a session has no active SIDs in Redis."""
        if not session_uuid:
            logger.debug("Session UUID is None, considering empty")
            return True
            
        try:
            session_key = self._get_session_key(session_uuid)
            exists = await self.redis.exists(session_key)
            if not exists:
                logger.debug(f"Session {session_uuid} key does not exist in Redis")
                return True

            count = await self.redis.scard(session_key)
            is_empty = count == 0
            logger.debug(f"Session {session_uuid} has {count} SIDs, empty: {is_empty}")
            return is_empty
        except Exception as e:
            logger.error(
                f"Failed to check if session {session_uuid} is empty in Redis: {e}"
            )
            return True

    async def get_session_for_sid(self, sid: str) -> Optional[str]:
        """Get session UUID for a SID."""
        try:
            sid_key = self._get_sid_key(sid)
            session_uuid = await self.redis.get(sid_key)
            if session_uuid:
                return session_uuid.decode() if isinstance(session_uuid, bytes) else session_uuid
            return None
        except Exception as e:
            logger.error(f"Failed to get session for SID {sid}: {e}")
            return None

    async def set_session_for_sid(self, sid: str, session_uuid: str) -> None:
        """Set session UUID for a SID."""
        try:
            sid_key = self._get_sid_key(sid)
            await self.redis.set(sid_key, session_uuid)
            await self.redis.expire(sid_key, self.ttl_seconds)
        except Exception as e:
            logger.error(f"Failed to set session for SID {sid}: {e}")

    async def remove_sid(self, sid: str) -> Optional[str]:
        """Remove SID mapping and return its session UUID."""
        try:
            sid_key = self._get_sid_key(sid)
            session_uuid = await self.redis.get(sid_key)
            await self.redis.delete(sid_key)
            
            if session_uuid:
                session_uuid_str = session_uuid.decode() if isinstance(session_uuid, bytes) else session_uuid
                # Also remove from session's SID set
                await self.remove_sid_from_session(session_uuid_str, sid)
                return session_uuid_str
            return None
        except Exception as e:
            logger.error(f"Failed to remove SID {sid}: {e}")
            return None


class MemorySessionStore(SessionStore):
    """In-memory session storage with TTL (fallback when Redis unavailable)."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: Dict[str, Set[str]] = {}
        self._sid_to_session: Dict[str, str] = {}
        self._ttl_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self.ttl_seconds = ttl_seconds

    async def add_sid_to_session(self, session_uuid: str, sid: str) -> None:
        """Add a SID to a session's SID set in memory with TTL."""
        async with self._lock:
            if session_uuid not in self._sessions:
                self._sessions[session_uuid] = set()
            self._sessions[session_uuid].add(sid)
            self._sid_to_session[sid] = session_uuid

            # Cancel existing TTL task and create new one
            if session_uuid in self._ttl_tasks:
                self._ttl_tasks[session_uuid].cancel()

            self._ttl_tasks[session_uuid] = asyncio.create_task(
                self._cleanup_after_ttl(session_uuid)
            )
            logger.debug(
                f"Added SID {sid} to session {session_uuid} in memory with {self.ttl_seconds}s TTL"
            )

    async def remove_sid_from_session(self, session_uuid: str, sid: str) -> None:
        """Remove a SID from a session's SID set in memory."""
        async with self._lock:
            if session_uuid in self._sessions:
                self._sessions[session_uuid].discard(sid)
                logger.debug(f"Removed SID {sid} from session {session_uuid} in memory")

                # Remove reverse mapping
                if sid in self._sid_to_session:
                    del self._sid_to_session[sid]

                # Clean up empty sessions immediately
                if not self._sessions[session_uuid]:
                    del self._sessions[session_uuid]
                    if session_uuid in self._ttl_tasks:
                        self._ttl_tasks[session_uuid].cancel()
                        del self._ttl_tasks[session_uuid]
                    logger.debug(f"Cleaned up empty session {session_uuid} from memory")
                else:
                    # Refresh TTL for remaining SIDs
                    if session_uuid in self._ttl_tasks:
                        self._ttl_tasks[session_uuid].cancel()
                    self._ttl_tasks[session_uuid] = asyncio.create_task(
                        self._cleanup_after_ttl(session_uuid)
                    )

    async def get_session_sids(self, session_uuid: str) -> Set[str]:
        """Get all SIDs for a session from memory."""
        async with self._lock:
            return self._sessions.get(session_uuid, set()).copy()

    async def get_all_session_sids(self) -> Dict[str, Set[str]]:
        """Get all session SID mappings from memory."""
        async with self._lock:
            return {k: v.copy() for k, v in self._sessions.items()}

    async def is_session_empty(self, session_uuid: str) -> bool:
        """Check if a session has no active SIDs in memory."""
        if not session_uuid:
            return True

        async with self._lock:
            if session_uuid not in self._sessions:
                return True
            return len(self._sessions.get(session_uuid, set())) == 0

    async def get_session_for_sid(self, sid: str) -> Optional[str]:
        """Get session UUID for a SID."""
        async with self._lock:
            return self._sid_to_session.get(sid)

    async def set_session_for_sid(self, sid: str, session_uuid: str) -> None:
        """Set session UUID for a SID."""
        async with self._lock:
            self._sid_to_session[sid] = session_uuid

    async def remove_sid(self, sid: str) -> Optional[str]:
        """Remove SID mapping and return its session UUID."""
        async with self._lock:
            session_uuid = self._sid_to_session.pop(sid, None)
            if session_uuid and session_uuid in self._sessions:
                self._sessions[session_uuid].discard(sid)
                if not self._sessions[session_uuid]:
                    del self._sessions[session_uuid]
                    if session_uuid in self._ttl_tasks:
                        self._ttl_tasks[session_uuid].cancel()
                        del self._ttl_tasks[session_uuid]
            return session_uuid

    async def _cleanup_after_ttl(self, session_uuid: str) -> None:
        """Clean up session after TTL expires."""
        try:
            await asyncio.sleep(self.ttl_seconds)
            async with self._lock:
                if session_uuid in self._sessions:
                    # Remove all SID mappings
                    for sid in self._sessions[session_uuid]:
                        self._sid_to_session.pop(sid, None)
                    del self._sessions[session_uuid]
                    if session_uuid in self._ttl_tasks:
                        del self._ttl_tasks[session_uuid]
                    logger.info(
                        f"TTL expired, cleaned up session {session_uuid} from memory"
                    )
        except asyncio.CancelledError:
            pass


def create_session_store() -> SessionStore:
    """Create session store (Redis preferred, memory fallback)."""
    # Always use Redis since your backend uses redis_client
    logger.info("Using Redis session store for Socket.IO sessions")
    return RedisSessionStore()


# Global session store instance
session_store: SessionStore = create_session_store()
