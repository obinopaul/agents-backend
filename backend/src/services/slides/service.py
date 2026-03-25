"""Slide service layer for database operations.

Provides CRUD operations for slides stored in the slide_content table.
Adapted from external_slide_system/slides/service.py for use with
the project's async SQLAlchemy patterns.
"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.model.slide_content import SlideContent
from backend.src.services.slides.models import (
    SlideContentInfo,
    PresentationInfo,
    PresentationListResponse,
    SlideWriteRequest,
    SlideWriteResponse,
)
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


class SlideService:
    """Service class for slide database operations."""

    @staticmethod
    async def save_slide_to_db(
        *,
        db_session: AsyncSession,
        thread_id: str,
        presentation_name: str,
        slide_number: int,
        slide_title: str,
        slide_content: str,
        tool_name: str = "SlideWrite",
    ) -> int:
        """Save or update a slide in the database.
        
        Args:
            db_session: SQLAlchemy async session
            thread_id: Thread/session ID that owns this slide
            presentation_name: Name of the presentation
            slide_number: Slide number (1-indexed)
            slide_title: Title of the slide
            slide_content: HTML content
            tool_name: Name of the tool that created/updated this slide
            
        Returns:
            int: The slide's database ID
        """
        # Check if slide already exists
        result = await db_session.execute(
            select(SlideContent).where(
                and_(
                    SlideContent.thread_id == thread_id,
                    SlideContent.presentation_name == presentation_name,
                    SlideContent.slide_number == slide_number,
                )
            )
        )
        existing_slide = result.scalar_one_or_none()

        if existing_slide:
            # Update existing slide
            existing_slide.slide_title = slide_title
            existing_slide.slide_content = slide_content
            existing_slide.slide_metadata = {
                "tool_name": tool_name,
                "last_tool_execution": timezone.now().isoformat(),
            }
            await db_session.commit()
            logger.info(
                f"Updated slide {slide_number} in {presentation_name} for thread {thread_id}"
            )
            return existing_slide.id
        else:
            # Create new slide
            new_slide = SlideContent(
                thread_id=thread_id,
                presentation_name=presentation_name,
                slide_number=slide_number,
                slide_title=slide_title,
                slide_content=slide_content,
                slide_metadata={
                    "tool_name": tool_name,
                    "last_tool_execution": timezone.now().isoformat(),
                },
            )
            db_session.add(new_slide)
            await db_session.commit()
            await db_session.refresh(new_slide)
            logger.info(
                f"Created slide {slide_number} in {presentation_name} for thread {thread_id}"
            )
            return new_slide.id

    @staticmethod
    async def get_thread_presentations(
        *,
        db_session: AsyncSession,
        thread_id: str,
    ) -> PresentationListResponse:
        """Get all presentations and their slides for a thread.
        
        Args:
            db_session: SQLAlchemy async session
            thread_id: Thread ID to query
            
        Returns:
            PresentationListResponse with all presentations and slides
        """
        try:
            # Query distinct presentations with aggregates
            result = await db_session.execute(
                select(
                    SlideContent.presentation_name,
                    func.count(SlideContent.id).label("slide_count"),
                    func.max(SlideContent.updated_time).label("last_updated"),
                )
                .where(SlideContent.thread_id == thread_id)
                .group_by(SlideContent.presentation_name)
                .order_by(func.max(SlideContent.updated_time).desc())
            )

            presentations = []
            for row in result:
                # Get all slides for this presentation
                slides_result = await db_session.execute(
                    select(SlideContent)
                    .where(
                        and_(
                            SlideContent.thread_id == thread_id,
                            SlideContent.presentation_name == row.presentation_name,
                        )
                    )
                    .order_by(SlideContent.slide_number)
                )
                slides = slides_result.scalars().all()

                slide_infos = [
                    SlideService._to_slide_content_info(slide) for slide in slides
                ]

                presentations.append(
                    PresentationInfo(
                        name=row.presentation_name,
                        slide_count=row.slide_count,
                        last_updated=row.last_updated,
                        slides=slide_infos,
                    )
                )

            return PresentationListResponse(
                thread_id=thread_id,
                presentations=presentations,
                total=len(presentations),
            )

        except Exception as e:
            logger.error(f"Failed to get presentations for thread {thread_id}: {e}")
            return PresentationListResponse(
                thread_id=thread_id,
                presentations=[],
                total=0,
            )

    @staticmethod
    async def get_slide_content(
        *,
        db_session: AsyncSession,
        thread_id: str,
        presentation_name: str,
        slide_number: int,
    ) -> Optional[SlideContentInfo]:
        """Get a specific slide's content.
        
        Args:
            db_session: SQLAlchemy async session
            thread_id: Thread ID
            presentation_name: Name of the presentation
            slide_number: Slide number to retrieve
            
        Returns:
            SlideContentInfo or None if not found
        """
        result = await db_session.execute(
            select(SlideContent).where(
                and_(
                    SlideContent.thread_id == thread_id,
                    SlideContent.presentation_name == presentation_name,
                    SlideContent.slide_number == slide_number,
                )
            )
        )
        slide = result.scalar_one_or_none()
        
        if slide:
            return SlideService._to_slide_content_info(slide)
        return None

    @staticmethod
    async def get_all_slides_for_presentation(
        *,
        db_session: AsyncSession,
        thread_id: str,
        presentation_name: str,
    ) -> List[SlideContentInfo]:
        """Get all slides for a presentation, ordered by slide number.
        
        Args:
            db_session: SQLAlchemy async session
            thread_id: Thread ID
            presentation_name: Name of the presentation
            
        Returns:
            List of SlideContentInfo objects
        """
        result = await db_session.execute(
            select(SlideContent)
            .where(
                and_(
                    SlideContent.thread_id == thread_id,
                    SlideContent.presentation_name == presentation_name,
                )
            )
            .order_by(SlideContent.slide_number)
        )
        slides = result.scalars().all()
        return [SlideService._to_slide_content_info(slide) for slide in slides]

    @staticmethod
    async def execute_slide_write(
        *,
        db_session: AsyncSession,
        thread_id: str,
        write_request: SlideWriteRequest,
    ) -> SlideWriteResponse:
        """Execute a manual slide write operation.
        
        Args:
            db_session: SQLAlchemy async session
            thread_id: Thread ID
            write_request: The write request with slide data
            
        Returns:
            SlideWriteResponse indicating success or failure
        """
        try:
            slide_id = await SlideService.save_slide_to_db(
                db_session=db_session,
                thread_id=thread_id,
                presentation_name=write_request.presentation_name,
                slide_number=write_request.slide_number,
                slide_title=write_request.title or "",
                slide_content=write_request.content,
                tool_name="ManualWrite",
            )

            return SlideWriteResponse(
                success=True,
                presentation_name=write_request.presentation_name,
                slide_number=write_request.slide_number,
                slide_id=slide_id,
            )

        except Exception as e:
            logger.error(f"Slide write failed: {e}")
            return SlideWriteResponse(
                success=False,
                presentation_name=write_request.presentation_name,
                slide_number=write_request.slide_number,
                error=str(e),
                error_code="WRITE_FAILED",
            )

    @staticmethod
    def _to_slide_content_info(slide: SlideContent) -> SlideContentInfo:
        """Convert database model to Pydantic response model."""
        return SlideContentInfo(
            id=slide.id,
            thread_id=slide.thread_id,
            presentation_name=slide.presentation_name,
            slide_number=slide.slide_number,
            slide_title=slide.slide_title or "",
            slide_content=slide.slide_content or "",
            metadata=slide.slide_metadata or {},
            created_time=slide.created_time,
            updated_time=slide.updated_time,
        )
