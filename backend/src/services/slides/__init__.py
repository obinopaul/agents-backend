"""Slides service package for managing presentation slides.

This package provides:
- SlideService: CRUD operations for slides in database
- SlideContentInfo, PresentationInfo: Pydantic response models
- SlideEventSubscriber: Event handler that syncs tool results to database
- convert_slides_to_pdf: PDF export functionality
"""

from backend.src.services.slides.models import (
    SlideContentInfo,
    PresentationInfo,
    PresentationListResponse,
    SlideWriteRequest,
    SlideWriteResponse,
)
from backend.src.services.slides.service import SlideService
from backend.src.services.slides.slide_subscriber import SlideEventSubscriber, slide_subscriber

__all__ = [
    "SlideService",
    "SlideContentInfo",
    "PresentationInfo", 
    "PresentationListResponse",
    "SlideWriteRequest",
    "SlideWriteResponse",
    "SlideEventSubscriber",
    "slide_subscriber",
]
