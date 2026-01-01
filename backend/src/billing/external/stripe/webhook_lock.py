"""
Webhook Lock and Distributed Processing

Provides distributed locking and deduplication for webhook processing
to prevent duplicate event handling in multi-instance deployments.
"""

import logging
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class WebhookLock:
    """
    Distributed webhook lock for preventing duplicate processing.
    
    Uses database to track webhook events and their processing status.
    This ensures that in a multi-instance deployment, only one instance
    processes each webhook event.
    """
    
    @classmethod
    async def check_and_mark_webhook_processing(
        cls,
        event_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Check if a webhook can be processed and mark it as in-progress.
        
        Args:
            event_id: Stripe event ID
            event_type: Type of webhook event
            payload: Optional event payload to store
            
        Returns:
            Tuple of (can_process: bool, reason: str)
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            import json
            
            async with async_db_session() as session:
                # Check if event already exists
                result = await session.execute(
                    text("""
                        SELECT id, status, created_at 
                        FROM webhook_events 
                        WHERE id = :event_id
                    """),
                    {"event_id": event_id}
                )
                existing = result.fetchone()
                
                if existing:
                    if existing.status == 'completed':
                        return False, "Event already processed"
                    elif existing.status == 'processing':
                        # Check if processing for too long (stuck)
                        age = (datetime.now(timezone.utc) - existing.created_at).total_seconds()
                        if age < 300:  # 5 minute window
                            return False, "Event currently being processed"
                        # Allow retry if stuck for too long
                        logger.warning(f"[WEBHOOK LOCK] Event {event_id} stuck in processing, allowing retry")
                    elif existing.status == 'failed':
                        # Allow retry of failed events
                        logger.info(f"[WEBHOOK LOCK] Retrying failed event {event_id}")
                
                # Insert or update
                payload_json = json.dumps(payload) if payload else None
                await session.execute(
                    text("""
                        INSERT INTO webhook_events (id, event_type, status, payload, created_at)
                        VALUES (:event_id, :event_type, 'processing', :payload::jsonb, :now)
                        ON CONFLICT (id) DO UPDATE SET
                            status = 'processing',
                            created_at = :now
                    """),
                    {
                        "event_id": event_id,
                        "event_type": event_type,
                        "payload": payload_json,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
                
                return True, "Processing"
                
        except Exception as e:
            logger.error(f"[WEBHOOK LOCK] Error checking/marking event {event_id}: {e}")
            # Allow processing on lock errors (prefer duplication over dropping)
            return True, f"Lock error: {e}"
    
    @classmethod
    async def mark_webhook_completed(cls, event_id: str) -> bool:
        """
        Mark a webhook event as successfully processed.
        
        Args:
            event_id: Stripe event ID
            
        Returns:
            True if marked successfully
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        UPDATE webhook_events 
                        SET status = 'completed', completed_at = :now
                        WHERE id = :event_id
                    """),
                    {
                        "event_id": event_id,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
                
            logger.debug(f"[WEBHOOK LOCK] Marked event {event_id} as completed")
            return True
            
        except Exception as e:
            logger.error(f"[WEBHOOK LOCK] Error marking event {event_id} completed: {e}")
            return False
    
    @classmethod
    async def mark_webhook_failed(cls, event_id: str, error_message: str) -> bool:
        """
        Mark a webhook event as failed.
        
        Args:
            event_id: Stripe event ID
            error_message: Error description
            
        Returns:
            True if marked successfully
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        UPDATE webhook_events 
                        SET status = 'failed', error_message = :error, completed_at = :now
                        WHERE id = :event_id
                    """),
                    {
                        "event_id": event_id,
                        "error": error_message[:1000],  # Truncate long errors
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
                
            logger.warning(f"[WEBHOOK LOCK] Marked event {event_id} as failed: {error_message[:100]}")
            return True
            
        except Exception as e:
            logger.error(f"[WEBHOOK LOCK] Error marking event {event_id} failed: {e}")
            return False
    
    @classmethod
    async def get_event_status(cls, event_id: str) -> Optional[Dict]:
        """
        Get the processing status of a webhook event.
        
        Args:
            event_id: Stripe event ID
            
        Returns:
            Dict with status info or None if not found
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT id, event_type, status, error_message, created_at, completed_at
                        FROM webhook_events 
                        WHERE id = :event_id
                    """),
                    {"event_id": event_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        'id': row.id,
                        'event_type': row.event_type,
                        'status': row.status,
                        'error_message': row.error_message,
                        'created_at': row.created_at.isoformat() if row.created_at else None,
                        'completed_at': row.completed_at.isoformat() if row.completed_at else None
                    }
                return None
                
        except Exception as e:
            logger.error(f"[WEBHOOK LOCK] Error getting event status: {e}")
            return None
    
    @classmethod
    async def cleanup_old_events(cls, days: int = 30) -> int:
        """
        Clean up old webhook events to prevent table bloat.
        
        Args:
            days: Delete events older than this many days
            
        Returns:
            Number of events deleted
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            from datetime import timedelta
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        DELETE FROM webhook_events 
                        WHERE created_at < :cutoff
                        RETURNING id
                    """),
                    {"cutoff": cutoff}
                )
                deleted = len(result.fetchall())
                await session.commit()
                
            if deleted > 0:
                logger.info(f"[WEBHOOK LOCK] Cleaned up {deleted} old webhook events")
            
            return deleted
            
        except Exception as e:
            logger.error(f"[WEBHOOK LOCK] Error cleaning up old events: {e}")
            return 0
