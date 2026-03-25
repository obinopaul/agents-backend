from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

class SlideTemplate(Base):
    """
    Slide Template model for storing presentation templates.
    """
    __tablename__ = 'agent_slide_templates'

    id: Mapped[id_key] = mapped_column(init=False)

    # Unique identifier (e.g., "modern-dark")
    template_id: Mapped[str] = mapped_column(
        sa.String(128),
        unique=True,
        index=True,
        comment='Unique template identifier string'
    )

    name: Mapped[str] = mapped_column(
        sa.String(255),
        comment='Human readable name'
    )

    description: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        default=None,
        comment='Description of the template'
    )

    thumbnail_path: Mapped[Optional[str]] = mapped_column(
        sa.String(512),
        default=None,
        comment='Relative path to thumbnail image'
    )
    
    # Path to assets folder
    assets_path: Mapped[Optional[str]] = mapped_column(
        sa.String(512),
        default=None,
        comment='Relative path to assets folder'
    )

    # JSON lists for flexibility
    images: Mapped[List[str]] = mapped_column(
        sa.JSON,
        default_factory=list,
        comment='List of preview image paths'
    )
    
    colors: Mapped[List[str]] = mapped_column(
        sa.JSON,
        default_factory=list,
        comment='Color palette'
    )

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        default=True,
        comment='Whether template is available for selection'
    )

    created_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now, onupdate=timezone.now
    )
