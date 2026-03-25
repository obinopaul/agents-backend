"""Pydantic models for the slides service.

Adapted from external_slide_system/slides/models.py for use with the
project's existing database and API patterns.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class SlideContentBase(BaseModel):
    """Base model for slide content."""

    presentation_name: str = Field(..., description="Name of the presentation")
    slide_number: int = Field(..., description="Slide number (1-indexed)", ge=1)
    slide_title: Optional[str] = Field(None, description="Title of the slide")
    slide_content: str = Field(..., description="HTML content of the slide")


class SlideContentInfo(SlideContentBase):
    """Full slide content information (response model)."""

    id: int
    thread_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_time: datetime
    updated_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class PresentationInfo(BaseModel):
    """Presentation with all its slides."""

    name: str = Field(..., description="Presentation name")
    slide_count: int = Field(..., description="Number of slides")
    last_updated: Optional[datetime] = None
    slides: List[SlideContentInfo] = Field(default_factory=list)


class PresentationListResponse(BaseModel):
    """Response model for listing presentations in a thread."""

    thread_id: str
    presentations: List[PresentationInfo]
    total: int


class SlideWriteRequest(BaseModel):
    """Request model for manual slide write operations."""

    presentation_name: str = Field(..., description="Name of the presentation")
    slide_number: int = Field(..., ge=1, description="Slide number (1-indexed)")
    content: str = Field(..., description="HTML content of the slide")
    title: Optional[str] = Field(None, description="Title of the slide")
    description: Optional[str] = Field(None, description="Description/notes for the slide")


class SlideWriteResponse(BaseModel):
    """Response model for slide write operations."""

    success: bool
    presentation_name: str
    slide_number: int
    slide_id: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
