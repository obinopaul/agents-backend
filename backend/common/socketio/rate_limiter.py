# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
WebSocket Rate Limiter for Socket.IO messages.

Provides per-user and per-session rate limiting using Redis with
an in-memory fallback for when Redis is unavailable.

Uses a sliding window algorithm for accurate rate limiting.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from collections import defaultdict

from backend.core.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    requests: int  # Max requests allowed
    window_seconds: int  # Time window in seconds
    description: str = ""


# Default rate limits for different operation types
DEFAULT_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    # General messages (includes pings, status checks) - lightweight
    "messages": RateLimitConfig(
        requests=100,
        window_seconds=60,
        description="General messages per minute"
    ),

    # Agent queries (computationally expensive)
    "queries": RateLimitConfig(
        requests=10,
        window_seconds=60,
        description="Agent queries per minute"
    ),

    # Sandbox operations
    "sandbox_ops": RateLimitConfig(
        requests=5,
        window_seconds=60,
        description="Sandbox operations per minute"
    ),

    # LLM enhancement prompts
    "enhance_prompt": RateLimitConfig(
        requests=20,
        window_seconds=60,
        description="Enhance prompt requests per minute"
    ),

    # File upload operations
    "file_upload": RateLimitConfig(
        requests=10,
        window_seconds=60,
        description="File upload operations per minute"
    ),
}

# Map message types to their rate limit scopes
MESSAGE_TYPE_TO_SCOPE: Dict[str, str] = {
    "query": "queries",
    "cancel": "messages",
    "ping": "messages",
    "sandbox_status": "sandbox_ops",
    "awake_sandbox": "sandbox_ops",
    "workspace_info": "messages",
    "enhance_prompt": "enhance_prompt",
    "publish": "queries",  # Publishing is expensive
}


class InMemoryRateLimiter:
    """
    In-memory rate limiter for single-instance deployments or Redis fallback.

    Uses sliding window algorithm for accurate rate limiting.
    """

    def __init__(self):
        # Dict[scope][identifier] -> list of timestamps
        self._windows: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the cleanup background task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop the cleanup background task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        """Periodically clean up old entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_old_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Rate limiter cleanup error: {e}")

    async def _cleanup_old_entries(self):
        """Remove timestamps older than the max window."""
        async with self._lock:
            now = time.time()
            max_window = max(
                config.window_seconds
                for config in DEFAULT_RATE_LIMITS.values()
            )
            cutoff = now - max_window

            for scope in list(self._windows.keys()):
                for identifier in list(self._windows[scope].keys()):
                    self._windows[scope][identifier] = [
                        ts for ts in self._windows[scope][identifier]
                        if ts > cutoff
                    ]
                    # Remove empty entries
                    if not self._windows[scope][identifier]:
                        del self._windows[scope][identifier]

    async def check_rate_limit(
        self,
        scope: str,
        identifier: str,
        config: Optional[RateLimitConfig] = None
    ) -> Tuple[bool, int, int, int]:
        """
        Check if a request is within rate limits.

        Args:
            scope: Rate limit scope (e.g., "queries", "messages")
            identifier: User or session identifier
            config: Optional custom config, defaults to scope config

        Returns:
            Tuple of (is_allowed, current_count, limit, retry_after_ms)
        """
        if config is None:
            config = DEFAULT_RATE_LIMITS.get(scope)
            if config is None:
                # Unknown scope, allow by default
                return True, 0, 0, 0

        async with self._lock:
            now = time.time()
            window_start = now - config.window_seconds

            key = f"{scope}:{identifier}"

            # Get timestamps within window
            self._windows[scope][identifier] = [
                ts for ts in self._windows[scope][identifier]
                if ts > window_start
            ]

            current_count = len(self._windows[scope][identifier])

            if current_count >= config.requests:
                # Calculate retry_after based on oldest request in window
                if self._windows[scope][identifier]:
                    oldest_ts = min(self._windows[scope][identifier])
                    retry_after_ms = int((oldest_ts + config.window_seconds - now) * 1000)
                    retry_after_ms = max(retry_after_ms, 1000)  # At least 1 second
                else:
                    retry_after_ms = config.window_seconds * 1000
                return False, current_count, config.requests, retry_after_ms

            # Add current timestamp
            self._windows[scope][identifier].append(now)
            return True, current_count + 1, config.requests, 0


class RedisRateLimiter:
    """
    Redis-backed rate limiter for distributed deployments.

    Uses sliding window algorithm with sorted sets for accurate limiting.
    """

    REDIS_PREFIX = "agents_backend:ws:limiter:"

    def __init__(self):
        self._redis = None
        self._fallback = InMemoryRateLimiter()

    async def start(self):
        """Initialize Redis connection."""
        try:
            from backend.database.redis import redis_client
            self._redis = redis_client
            await self._redis.ping()
            logger.info("Redis rate limiter initialized")
        except Exception as e:
            logger.warning(f"Redis rate limiter unavailable, using in-memory fallback: {e}")
            self._redis = None
            await self._fallback.start()

    async def stop(self):
        """Clean up resources."""
        await self._fallback.stop()

    async def check_rate_limit(
        self,
        scope: str,
        identifier: str,
        config: Optional[RateLimitConfig] = None
    ) -> Tuple[bool, int, int, int]:
        """
        Check if a request is within rate limits using Redis.

        Falls back to in-memory limiter if Redis is unavailable.
        """
        if config is None:
            config = DEFAULT_RATE_LIMITS.get(scope)
            if config is None:
                return True, 0, 0, 0

        # Try Redis first
        if self._redis:
            try:
                return await self._redis_check(scope, identifier, config)
            except Exception as e:
                logger.warning(f"Redis rate limit check failed, using fallback: {e}")

        # Fallback to in-memory
        return await self._fallback.check_rate_limit(scope, identifier, config)

    async def _redis_check(
        self,
        scope: str,
        identifier: str,
        config: RateLimitConfig
    ) -> Tuple[bool, int, int, int]:
        """
        Check rate limit using Redis sorted sets.

        Uses ZADD with timestamps and ZREMRANGEBYSCORE for sliding window.
        """
        key = f"{self.REDIS_PREFIX}{scope}:{identifier}"
        now = time.time()
        window_start = now - config.window_seconds

        # Pipeline: remove old entries, count current, conditionally add new
        pipe = self._redis.pipeline()

        # Remove timestamps outside the window
        pipe.zremrangebyscore(key, '-inf', window_start)

        # Count current entries in window
        pipe.zcard(key)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= config.requests:
            # Get oldest timestamp to calculate retry_after
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_ts = oldest[0][1]
                retry_after_ms = int((oldest_ts + config.window_seconds - now) * 1000)
                retry_after_ms = max(retry_after_ms, 1000)
            else:
                retry_after_ms = config.window_seconds * 1000
            return False, current_count, config.requests, retry_after_ms

        # Add current timestamp
        await self._redis.zadd(key, {str(now): now})
        # Set expiry slightly longer than window to auto-cleanup
        await self._redis.expire(key, config.window_seconds + 60)

        return True, current_count + 1, config.requests, 0


class WebSocketRateLimiter:
    """
    Main rate limiter class for WebSocket messages.

    Provides a unified interface for rate limiting with support for:
    - Per-user limits
    - Per-session limits
    - Per-scope (message type) limits
    - Configurable via settings
    """

    def __init__(self):
        # Use Redis by default, with in-memory fallback
        self._limiter: Optional[RedisRateLimiter] = None
        self._enabled = True

    async def start(self):
        """Initialize the rate limiter."""
        # Check if rate limiting is enabled in settings
        self._enabled = getattr(settings, 'WS_RATE_LIMIT_ENABLED', True)

        if not self._enabled:
            logger.info("WebSocket rate limiting is disabled")
            return

        self._limiter = RedisRateLimiter()
        await self._limiter.start()
        logger.info("WebSocket rate limiter started")

    async def stop(self):
        """Stop the rate limiter."""
        if self._limiter:
            await self._limiter.stop()

    def get_scope_for_message_type(self, message_type: str) -> str:
        """Get the rate limit scope for a message type."""
        return MESSAGE_TYPE_TO_SCOPE.get(message_type, "messages")

    async def check_limit(
        self,
        message_type: str,
        user_id: Optional[int] = None,
        session_uuid: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        Check if a message is within rate limits.

        Args:
            message_type: Type of message (query, ping, etc.)
            user_id: User ID for per-user limits
            session_uuid: Session UUID for per-session limits

        Returns:
            Tuple of (is_allowed, info_dict)
            info_dict contains: scope, current, limit, retry_after_ms
        """
        if not self._enabled or not self._limiter:
            return True, {"scope": "disabled", "current": 0, "limit": 0, "retry_after_ms": 0}

        scope = self.get_scope_for_message_type(message_type)

        # Primary check: per-user limit
        if user_id:
            identifier = f"user:{user_id}"
            is_allowed, current, limit, retry_after = await self._limiter.check_rate_limit(
                scope=scope,
                identifier=identifier
            )

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded: user={user_id}, scope={scope}, "
                    f"current={current}/{limit}, retry_after={retry_after}ms"
                )
                return False, {
                    "scope": scope,
                    "current": current,
                    "limit": limit,
                    "retry_after_ms": retry_after,
                    "limit_type": "per_user"
                }

        # Secondary check: per-session limit (for query flooding within session)
        if session_uuid and scope == "queries":
            identifier = f"session:{session_uuid}"
            is_allowed, current, limit, retry_after = await self._limiter.check_rate_limit(
                scope=scope,
                identifier=identifier
            )

            if not is_allowed:
                logger.warning(
                    f"Session rate limit exceeded: session={session_uuid}, scope={scope}, "
                    f"current={current}/{limit}, retry_after={retry_after}ms"
                )
                return False, {
                    "scope": scope,
                    "current": current,
                    "limit": limit,
                    "retry_after_ms": retry_after,
                    "limit_type": "per_session"
                }

        return True, {
            "scope": scope,
            "current": current if user_id else 0,
            "limit": limit if user_id else 0,
            "retry_after_ms": 0
        }

    def create_error_content(self, info: Dict) -> Dict:
        """
        Create error content dict for rate limit exceeded response.

        Args:
            info: Info dict from check_limit

        Returns:
            Content dict for error event
        """
        return {
            "message": "Rate limit exceeded. Please wait before sending more messages.",
            "error_type": "rate_limit",
            "retry_after_ms": info.get("retry_after_ms", 60000),
            "limit_type": info.get("limit_type", "unknown"),
            "current_usage": {
                "requests": info.get("current", 0),
                "limit": info.get("limit", 0),
                "scope": info.get("scope", "unknown")
            }
        }


# Global instance
websocket_rate_limiter = WebSocketRateLimiter()


async def init_rate_limiter():
    """Initialize the global rate limiter. Call during app startup."""
    await websocket_rate_limiter.start()


async def shutdown_rate_limiter():
    """Shutdown the global rate limiter. Call during app shutdown."""
    await websocket_rate_limiter.stop()
