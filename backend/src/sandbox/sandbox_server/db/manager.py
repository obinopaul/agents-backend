"""Database manager for sandbox operations.

Uses the main FastAPI database connection instead of a standalone engine.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession as DBSession

from backend.src.sandbox.sandbox_server.logger import logger
from backend.src.sandbox.sandbox_server.db.model import Sandbox

# Import main database session and engine from FastAPI backend
from backend.database.db import async_db_session as SessionLocal, async_engine as engine





@asynccontextmanager
async def get_db() -> AsyncGenerator[DBSession, None]:
    """Get a database session as a context manager.

    Yields:
        A database session that will be automatically committed or rolled back
    """
    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


class SandboxTable:
    """Table class for sandbox operations following Open WebUI pattern."""

    async def create_sandbox(
        self,
        sandbox_id: str,
        provider: str,
        provider_sandbox_id: str,
        user_id: str,
        status: str = "initializing",
    ) -> Sandbox:
        """Create a new sandbox.

        Args:
            sandbox_id: The internal sandbox UUID
            provider: The provider name (e.g., 'e2b')
            provider_sandbox_id: The provider's sandbox ID
            user_id: The user ID who owns the sandbox
            status: Initial status of the sandbox

        Returns:
            The created sandbox
        """
        async with get_db() as db:
            db_sandbox = Sandbox(
                id=sandbox_id,
                provider=provider,
                provider_sandbox_id=provider_sandbox_id,
                user_id=user_id,
                status=status,
            )
            db.add(db_sandbox)
            await db.flush()
            return db_sandbox

    async def get_sandbox_by_id(self, sandbox_id: str) -> Optional[Sandbox]:
        """Get a sandbox by its internal ID.

        Args:
            sandbox_id: The internal sandbox ID

        Returns:
            The sandbox if found, None otherwise
        """
        async with get_db() as db:
            result = await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
            return result.scalar_one_or_none()

    async def get_sandbox_by_provider_id(
        self, provider_sandbox_id: str
    ) -> Optional[Sandbox]:
        """Get a sandbox by its provider ID.

        Args:
            provider_sandbox_id: The provider's sandbox ID

        Returns:
            The sandbox if found, None otherwise
        """
        async with get_db() as db:
            result = await db.execute(
                select(Sandbox).where(Sandbox.sandbox_id == provider_sandbox_id)
            )
            return result.scalar_one_or_none()

    async def update_sandbox_status(
        self, sandbox_id: str, status: Optional[str] = None, **kwargs
    ) -> bool:
        """Update a sandbox's status and optional timestamp fields.

        Args:
            sandbox_id: The internal sandbox ID
            status: New status to set (optional)
            **kwargs: Optional timestamp fields (started_at, stopped_at, etc.)

        Returns:
            True if updated successfully, False if not found
        """
        async with get_db() as db:
            result = await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
            db_sandbox = result.scalar_one_or_none()
            if db_sandbox:
                if status is not None:
                    db_sandbox.status = status

                from datetime import datetime, timezone

                # Update timestamp fields if provided
                for field, value in kwargs.items():
                    if hasattr(db_sandbox, field):
                        if value is True:  # Set current timestamp
                            setattr(db_sandbox, field, datetime.now(timezone.utc))
                        elif value is not None:
                            setattr(db_sandbox, field, value)

                await db.flush()
                return True
            return False

    async def update_last_activity(self, sandbox_id: str) -> bool:
        """Update the last activity timestamp for a sandbox.

        Args:
            sandbox_id: The internal sandbox ID

        Returns:
            True if updated successfully, False if not found
        """
        from datetime import datetime, timezone

        return await self.update_sandbox_status(
            sandbox_id, None, last_activity_at=datetime.now(timezone.utc)
        )

    async def list_user_sandboxes(
        self, user_id: str, status: Optional[str] = None
    ) -> List[Sandbox]:
        """List sandboxes for a user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of sandboxes
        """
        async with get_db() as db:
            query = select(Sandbox).where(Sandbox.user_id == user_id)

            if status:
                query = query.where(Sandbox.status == status)

            query = query.order_by(Sandbox.created_at.desc())
            result = await db.execute(query)
            return result.scalars().all()

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete a sandbox from the database.

        Args:
            sandbox_id: The internal sandbox ID

        Returns:
            True if deleted successfully, False if not found
        """
        async with get_db() as db:
            result = await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
            db_sandbox = result.scalar_one_or_none()
            if db_sandbox:
                await db.delete(db_sandbox)
                return True
            return False

    async def get_sandbox_with_user(self, sandbox_id: str) -> Optional[Sandbox]:
        """Get a sandbox with its user relationship loaded.

        Args:
            sandbox_id: The internal sandbox ID

        Returns:
            The sandbox with user loaded, or None if not found
        """
        async with get_db() as db:
            result = await db.execute(
                select(Sandbox)
                .where(Sandbox.id == sandbox_id)
                .options(selectinload(Sandbox.user))
            )
            return result.scalar_one_or_none()

    async def get_running_sandbox_for_user(self, user_id: str) -> Optional[Sandbox]:
        """Get the most recent running sandbox for a user.
        
        This enables sandbox reuse - if user already has a running sandbox,
        we can connect to it instead of creating a new one.

        Args:
            user_id: The user ID

        Returns:
            The most recent running sandbox if found, None otherwise
        """
        async with get_db() as db:
            result = await db.execute(
                select(Sandbox)
                .where(
                    Sandbox.user_id == user_id,
                    Sandbox.status == "running"
                )
                .order_by(Sandbox.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_sandbox_for_session(self, session_id: str) -> Optional[Sandbox]:
        """Get the sandbox linked to a specific session via SessionMetrics.

        Args:
            session_id: The session ID to look up

        Returns:
            The linked sandbox if found and running, None otherwise
        """
        try:
            # Import here to avoid circular imports
            from backend.app.agent.model.agent_models import SessionMetrics
            
            async with get_db() as db:
                # First, find the session and get its sandbox_id
                result = await db.execute(
                    select(SessionMetrics.sandbox_id)
                    .where(SessionMetrics.session_id == session_id)
                )
                sandbox_id = result.scalar_one_or_none()
                
                if not sandbox_id:
                    return None
                
                # Then get the sandbox if it's still running
                result = await db.execute(
                    select(Sandbox)
                    .where(
                        Sandbox.id == sandbox_id,
                        Sandbox.status == "running"
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"Failed to get sandbox for session {session_id}: {e}")
            return None

    async def update_session_sandbox(self, session_id: str, sandbox_id: str) -> bool:
        """Link a sandbox to a session by updating SessionMetrics.sandbox_id.

        Args:
            session_id: The session ID to update
            sandbox_id: The sandbox ID to link

        Returns:
            True if updated successfully, False if session not found
        """
        try:
            # Import here to avoid circular imports
            from backend.app.agent.model.agent_models import SessionMetrics
            
            async with get_db() as db:
                result = await db.execute(
                    select(SessionMetrics)
                    .where(SessionMetrics.session_id == session_id)
                )
                session_metrics = result.scalar_one_or_none()
                
                if session_metrics:
                    session_metrics.sandbox_id = sandbox_id
                    await db.flush()
                    return True
                return False
        except Exception as e:
            logger.warning(f"Failed to update session {session_id} with sandbox {sandbox_id}: {e}")
            return False


Sandboxes = SandboxTable()

