"""Slide content database model for persistent storage."""

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key, UniversalText


class SlideContent(Base):
    """Slide content storage for presentations.
    
    Stores HTML slide content alongside metadata. Each slide is uniquely
    identified by thread_id + presentation_name + slide_number.
    
    The agent writes slides to the sandbox filesystem, and an event subscriber
    syncs them to this table for fast frontend queries and persistence.
    """

    __tablename__ = 'slide_content'

    id: Mapped[id_key] = mapped_column(init=False)
    thread_id: Mapped[str] = mapped_column(
        sa.String(64), 
        index=True, 
        comment='Thread/Session ID that owns this slide'
    )
    presentation_name: Mapped[str] = mapped_column(
        sa.String(255), 
        index=True,
        comment='Name of the presentation'
    )
    slide_number: Mapped[int] = mapped_column(
        sa.Integer, 
        comment='Slide number (1-indexed)'
    )
    slide_title: Mapped[str | None] = mapped_column(
        sa.String(500), 
        default=None, 
        comment='Title of the slide'
    )
    slide_content: Mapped[str | None] = mapped_column(
        UniversalText, 
        default=None, 
        comment='Full HTML content of the slide'
    )
    slide_metadata: Mapped[dict | None] = mapped_column(
        JSONB, 
        default=None, 
        comment='Additional metadata (tool_name, description, etc.)'
    )

    __table_args__ = (
        sa.UniqueConstraint(
            'thread_id', 
            'presentation_name', 
            'slide_number', 
            name='uq_slide_content_location'
        ),
        {'comment': 'Persistent storage for slide HTML content'}
    )
