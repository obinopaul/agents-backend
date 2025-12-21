# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Slides API endpoints.

This module provides endpoints for managing and exporting slides
created by the agent in sandbox environments:
- List presentations in a sandbox
- List slides within a presentation
- Get slide HTML content for preview
- Export presentation to PDF
"""

import io
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel
from backend.common.security.jwt import DependsJwtAuth
from backend.src.services.sandbox_service import sandbox_service
from backend.src.sandbox.sandbox_server.models.exceptions import (
    SandboxAuthenticationError,
    SandboxNotFoundException,
    SandboxTimeoutException,
    SandboxNotInitializedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slides"])

# Default workspace presentations path
PRESENTATIONS_PATH = "/workspace/presentations"


# ============================================================================
# Models
# ============================================================================

class PresentationInfo(BaseModel):
    """Information about a presentation."""
    name: str = Field(..., description="Presentation folder name")
    slide_count: int = Field(..., description="Number of slides in presentation")
    path: str = Field(..., description="Full path to presentation")


class SlideInfo(BaseModel):
    """Information about a single slide."""
    slide_number: int = Field(..., description="Slide number (1-indexed)")
    filename: str = Field(..., description="Slide filename")
    path: str = Field(..., description="Full path to slide file")


class ListPresentationsResponse(BaseModel):
    """Response for listing presentations."""
    success: bool = True
    presentations: List[PresentationInfo] = Field(default_factory=list)
    message: str = "Presentations retrieved successfully"


class ListSlidesResponse(BaseModel):
    """Response for listing slides in a presentation."""
    success: bool = True
    presentation_name: str
    slides: List[SlideInfo] = Field(default_factory=list)
    message: str = "Slides retrieved successfully"


class SlideContentResponse(BaseModel):
    """Response for slide content."""
    success: bool = True
    slide_number: int
    presentation_name: str
    content: str = Field(..., description="HTML content of the slide")
    message: str = "Slide content retrieved successfully"


class ExportPresentationRequest(BaseModel):
    """Request for exporting a presentation."""
    presentation_name: str = Field(..., description="Name of the presentation to export")
    format: str = Field(default="pdf", description="Export format: 'pdf' or 'zip'")


# ============================================================================
# Exception Handling
# ============================================================================

def handle_sandbox_exception(e: Exception):
    """Handle sandbox exceptions and return appropriate HTTP status code."""
    if isinstance(e, SandboxAuthenticationError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    elif isinstance(e, SandboxNotFoundException) or isinstance(e, FileNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    elif isinstance(e, SandboxTimeoutException):
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    elif isinstance(e, SandboxNotInitializedError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    else:
        logger.exception(f"Unexpected error in slides endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def get_sandbox_service():
    """Get initialized sandbox service."""
    if not sandbox_service._controller:
        await sandbox_service.initialize()
    return sandbox_service.controller


# ============================================================================
# Helper Functions
# ============================================================================

def parse_slide_number(filename: str) -> Optional[int]:
    """Extract slide number from filename like 'slide_1.html' or '01_intro.html'."""
    # Try pattern: slide_N.html
    match = re.match(r'slide_(\d+)\.html?', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Try pattern: NN_name.html (numbered prefix)
    match = re.match(r'(\d+)[_-].*\.html?', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Try pattern: just N.html
    match = re.match(r'(\d+)\.html?', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return None


async def list_directory(controller, sandbox_id: str, path: str) -> List[str]:
    """List directory contents using run_cmd."""
    try:
        output = await controller.run_cmd(
            sandbox_id, 
            f"ls -1 {path} 2>/dev/null || echo ''",
            background=False
        )
        if not output or output.strip() == '':
            return []
        return [f.strip() for f in output.strip().split('\n') if f.strip()]
    except Exception as e:
        logger.warning(f"Failed to list directory {path}: {e}")
        return []


async def count_slides_in_presentation(controller, sandbox_id: str, presentation_path: str) -> int:
    """Count HTML slide files in a presentation directory."""
    try:
        output = await controller.run_cmd(
            sandbox_id,
            f"ls -1 {presentation_path}/*.html 2>/dev/null | wc -l || echo '0'",
            background=False
        )
        return int(output.strip()) if output.strip().isdigit() else 0
    except Exception:
        return 0


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/{sandbox_id}/presentations",
    response_model=ResponseSchemaModel[ListPresentationsResponse],
    summary="List presentations in sandbox",
    description="List all presentation folders in the sandbox workspace.",
    dependencies=[DependsJwtAuth],
)
async def list_presentations(
    sandbox_id: str,
    controller=Depends(get_sandbox_service)
):
    """
    List all presentations in the sandbox workspace.
    
    Presentations are stored in /workspace/presentations/ directory.
    Each subdirectory is considered a presentation.
    """
    try:
        # List presentation directories
        directories = await list_directory(controller, sandbox_id, PRESENTATIONS_PATH)
        
        presentations = []
        for dir_name in directories:
            presentation_path = f"{PRESENTATIONS_PATH}/{dir_name}"
            slide_count = await count_slides_in_presentation(
                controller, sandbox_id, presentation_path
            )
            
            presentations.append(PresentationInfo(
                name=dir_name,
                slide_count=slide_count,
                path=presentation_path,
            ))
        
        return ResponseModel(
            data=ListPresentationsResponse(
                success=True,
                presentations=presentations,
                message=f"Found {len(presentations)} presentation(s)",
            )
        )
    except Exception as e:
        logger.error(f"Failed to list presentations: {e}")
        handle_sandbox_exception(e)


@router.get(
    "/{sandbox_id}/presentations/{presentation_name}",
    response_model=ResponseSchemaModel[ListSlidesResponse],
    summary="List slides in presentation",
    description="List all slides within a specific presentation.",
    dependencies=[DependsJwtAuth],
)
async def list_slides(
    sandbox_id: str,
    presentation_name: str,
    controller=Depends(get_sandbox_service)
):
    """
    List all slides in a presentation.
    
    Returns slide information sorted by slide number.
    """
    try:
        presentation_path = f"{PRESENTATIONS_PATH}/{presentation_name}"
        
        # Check if presentation exists
        files = await list_directory(controller, sandbox_id, presentation_path)
        if not files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Presentation '{presentation_name}' not found or is empty"
            )
        
        # Filter HTML files and extract slide info
        slides = []
        for filename in files:
            if filename.lower().endswith('.html'):
                slide_num = parse_slide_number(filename)
                if slide_num is not None:
                    slides.append(SlideInfo(
                        slide_number=slide_num,
                        filename=filename,
                        path=f"{presentation_path}/{filename}",
                    ))
        
        # Sort by slide number
        slides.sort(key=lambda s: s.slide_number)
        
        # Re-number if needed (in case of gaps)
        for i, slide in enumerate(slides, 1):
            slide.slide_number = i
        
        return ResponseModel(
            data=ListSlidesResponse(
                success=True,
                presentation_name=presentation_name,
                slides=slides,
                message=f"Found {len(slides)} slide(s)",
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list slides: {e}")
        handle_sandbox_exception(e)


@router.get(
    "/{sandbox_id}/slides/{presentation_name}/{slide_num}",
    response_model=ResponseSchemaModel[SlideContentResponse],
    summary="Get slide content",
    description="Get HTML content of a specific slide for preview.",
    dependencies=[DependsJwtAuth],
)
async def get_slide(
    sandbox_id: str,
    presentation_name: str,
    slide_num: int,
    controller=Depends(get_sandbox_service)
):
    """
    Get the HTML content of a specific slide.
    
    This can be used to render slide previews in the frontend.
    """
    try:
        presentation_path = f"{PRESENTATIONS_PATH}/{presentation_name}"
        
        # List files to find the slide
        files = await list_directory(controller, sandbox_id, presentation_path)
        
        slide_file = None
        for filename in files:
            if filename.lower().endswith('.html'):
                num = parse_slide_number(filename)
                if num == slide_num:
                    slide_file = filename
                    break
        
        if not slide_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Slide {slide_num} not found in presentation '{presentation_name}'"
            )
        
        # Read slide content
        slide_path = f"{presentation_path}/{slide_file}"
        content = await controller.read_file(sandbox_id, slide_path)
        
        return ResponseModel(
            data=SlideContentResponse(
                success=True,
                slide_number=slide_num,
                presentation_name=presentation_name,
                content=content,
                message="Slide content retrieved successfully",
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get slide content: {e}")
        handle_sandbox_exception(e)


@router.post(
    "/{sandbox_id}/slides/export",
    summary="Export presentation as PDF",
    description="Convert all slides in a presentation to a downloadable PDF file.",
    response_class=Response,
    responses={
        200: {
            "description": "PDF file",
            "content": {"application/pdf": {}},
        },
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        404: {"description": "Presentation not found"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def export_presentation(
    sandbox_id: str,
    request: ExportPresentationRequest,
    controller=Depends(get_sandbox_service)
):
    """
    Export a presentation as a PDF file.
    
    Uses Playwright to render each HTML slide and merges them into a single PDF.
    The PDF uses 1280x720 slide dimensions for optimal viewing.
    """
    try:
        presentation_name = request.presentation_name
        presentation_path = f"{PRESENTATIONS_PATH}/{presentation_name}"
        
        # Get all slides
        files = await list_directory(controller, sandbox_id, presentation_path)
        if not files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Presentation '{presentation_name}' not found"
            )
        
        # Collect slide content
        slides_content = []
        for filename in sorted(files):
            if filename.lower().endswith('.html'):
                slide_num = parse_slide_number(filename)
                if slide_num is not None:
                    content = await controller.read_file(
                        sandbox_id, f"{presentation_path}/{filename}"
                    )
                    slides_content.append({
                        'number': slide_num,
                        'content': content,
                    })
        
        if not slides_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No slides found in presentation"
            )
        
        # Sort by slide number
        slides_content.sort(key=lambda s: s['number'])
        
        # Convert to PDF using Playwright
        try:
            from playwright.async_api import async_playwright
            from pypdf import PdfWriter, PdfReader
        except ImportError as e:
            logger.error(f"Missing PDF dependencies: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF export dependencies not installed. Please install playwright and pypdf."
            )
        
        pdf_options = {
            'width': '1280px',
            'height': '720px',
            'print_background': True,
            'margin': {'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
            'display_header_footer': False,
            'prefer_css_page_size': False,
            'scale': 1,
        }
        
        pdf_buffers = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 720})
            
            try:
                for slide in slides_content:
                    page = await context.new_page()
                    try:
                        await page.wait_for_load_state('domcontentloaded')
                        await page.set_content(
                            slide['content'], 
                            wait_until='networkidle', 
                            timeout=60000
                        )
                        pdf_buffer = await page.pdf(**pdf_options)
                        pdf_buffers.append(pdf_buffer)
                        logger.info(f"Converted slide {slide['number']} to PDF")
                    finally:
                        await page.close()
            finally:
                await browser.close()
        
        # Merge PDFs
        pdf_writer = PdfWriter()
        for pdf_buffer in pdf_buffers:
            pdf_reader = PdfReader(io.BytesIO(pdf_buffer))
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        pdf_bytes = output.read()
        
        logger.info(f"Created PDF with {len(pdf_writer.pages)} pages for '{presentation_name}'")
        
        # Sanitize filename
        safe_name = re.sub(r'[^\w\-_]', '_', presentation_name)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}.pdf",
                "Content-Length": str(len(pdf_bytes)),
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export presentation: {e}")
        handle_sandbox_exception(e)


@router.get(
    "/{sandbox_id}/slides/download/{presentation_name}",
    summary="Download presentation as ZIP",
    description="Download all slide HTML files as a ZIP archive.",
    response_class=Response,
    responses={
        200: {
            "description": "ZIP file containing all slides",
            "content": {"application/zip": {}},
        },
        401: {"description": "Unauthorized"},
        404: {"description": "Presentation not found"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def download_presentation_zip(
    sandbox_id: str,
    presentation_name: str,
    controller=Depends(get_sandbox_service)
):
    """
    Download all slides as a ZIP archive.
    
    This provides the raw HTML files for offline viewing or editing.
    """
    import zipfile
    
    try:
        presentation_path = f"{PRESENTATIONS_PATH}/{presentation_name}"
        
        # Get all slides
        files = await list_directory(controller, sandbox_id, presentation_path)
        if not files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Presentation '{presentation_name}' not found"
            )
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in sorted(files):
                if filename.lower().endswith('.html'):
                    content = await controller.read_file(
                        sandbox_id, f"{presentation_path}/{filename}"
                    )
                    # Ensure content is bytes
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    zip_file.writestr(f"{presentation_name}/{filename}", content)
        
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()
        
        # Sanitize filename
        safe_name = re.sub(r'[^\w\-_]', '_', presentation_name)
        
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}.zip",
                "Content-Length": str(len(zip_bytes)),
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download presentation: {e}")
        handle_sandbox_exception(e)
