from typing import List, Optional, Dict, Any, Union
import logging
from enum import Enum
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.database.db import CurrentSession, get_db
from backend.app.agent.crud.crud_slide_template import slide_template_dao
from backend.app.agent.model.slide_template import SlideTemplate as DBTemplate

# =============================================================================
# Models
# =============================================================================

class TemplateType(str, Enum):
    SLIDE = "slide"
    DOCUMENT = "document" # Future extension

class BaseTemplate(BaseModel):
    """Base model for all templates."""
    id: str
    name: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    type: TemplateType

class SlideTemplate(BaseTemplate):
    """Specific model for Slide Templates."""
    type: TemplateType = TemplateType.SLIDE
    images: List[str] = Field(default_factory=list, description="Ordered list of slide preview images")
    colors: List[str] = Field(default_factory=list, description="Palette colors")
    
class SlideTemplatesResponse(BaseModel):
    templates: List[SlideTemplate]
    total: int
    page: int
    page_size: int
    total_pages: int

# =============================================================================
# Routers
# =============================================================================

# Main router (can include sub-routers)
router = APIRouter()

# Distinct Router for Slides
# This encapsulates all slide-specific template logic.
slide_router = APIRouter()

@slide_router.get("", response_model=SlideTemplatesResponse)
async def list_slide_templates(
    db: CurrentSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name"),
):
    """
    List available slide templates.

    Returns a paginated list of slide templates with full image sequences.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Listing slide templates - Page: {page}, Page Size: {page_size}, Search: {search}")
    # Use CRUD operation
    templates_db, total = await slide_template_dao.get_all_active(
        db, page=page, per_page=page_size, search=search
    )
    
    # Convert DB Models to Pydantic Schemas
    templates = []
    for t in templates_db:
        templates.append(SlideTemplate(
            id=t.template_id,
            name=t.name,
            description=t.description,
            thumbnail_url=t.thumbnail_path, # Path is used as URL due to static mount logic
            type=TemplateType.SLIDE,
            images=t.images or [],
            colors=t.colors or []
        ))
    
    import math
    return SlideTemplatesResponse(
        templates=templates,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0
    )

@slide_router.get("/{template_id}", response_model=SlideTemplate)
async def get_slide_template(
    template_id: str,
    db: CurrentSession,
):
    """
    Get details of a specific slide template.
    """
    t = await slide_template_dao.get_by_template_id(db, template_id)
    
    if not t:
        raise HTTPException(status_code=404, detail=f"Slide template '{template_id}' not found")
        
    return SlideTemplate(
        id=t.template_id,
        name=t.name,
        description=t.description,
        thumbnail_url=t.thumbnail_path,
        type=TemplateType.SLIDE,
        images=t.images or [],
        colors=t.colors or []
    )

# We can expose other template routers here in the future
# e.g., document_router = APIRouter()
