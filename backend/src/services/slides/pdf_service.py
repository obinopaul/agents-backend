"""PDF generation service for converting HTML slides to PDF.

Uses Playwright to render HTML slides in a headless browser,
then merges them into a single PDF using pypdf.

Adapted from external_slide_system/slides/pdf_service.py.
"""

import io
import logging
from typing import List, AsyncGenerator, Dict, Any

from backend.src.services.slides.models import SlideContentInfo

logger = logging.getLogger(__name__)


async def convert_slides_to_pdf(slides: List[SlideContentInfo]) -> bytes:
    """Convert a list of HTML slides to a single PDF document.

    Args:
        slides: List of SlideContentInfo objects containing HTML content

    Returns:
        bytes: PDF document as bytes

    Raises:
        ValueError: If no slides provided
        ImportError: If playwright or pypdf not installed
    """
    if not slides:
        raise ValueError("No slides to convert")

    # Import dependencies
    try:
        from playwright.async_api import async_playwright
        from pypdf import PdfWriter, PdfReader
    except ImportError as e:
        logger.error(f"Missing PDF dependencies: {e}")
        raise ImportError(
            "PDF export requires playwright and pypdf. "
            "Install with: pip install playwright pypdf && playwright install chromium"
        )

    # PDF options for slide format (1280x720)
    pdf_options = {
        'width': '1280px',
        'height': '720px',
        'print_background': True,
        'margin': {
            'top': '0',
            'bottom': '0',
            'left': '0',
            'right': '0'
        },
        'display_header_footer': False,
        'prefer_css_page_size': False,
        'scale': 1
    }

    pdf_buffers = []

    # Launch Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )

            # Convert each slide to PDF
            for slide in slides:
                logger.info(
                    f"Converting slide {slide.slide_number} of {slide.presentation_name}"
                )

                page = await context.new_page()

                try:
                    await page.wait_for_load_state('domcontentloaded')
                    await page.set_content(
                        slide.slide_content,
                        wait_until='networkidle',
                        timeout=60000
                    )

                    pdf_buffer = await page.pdf(
                        print_background=pdf_options['print_background'],
                        margin=pdf_options['margin'],
                        display_header_footer=pdf_options['display_header_footer'],
                        prefer_css_page_size=pdf_options['prefer_css_page_size'],
                        scale=pdf_options['scale'],
                        width=pdf_options['width'],
                        height=pdf_options['height']
                    )

                    pdf_buffers.append(pdf_buffer)
                    logger.info(f"Successfully converted slide {slide.slide_number}")

                finally:
                    await page.close()

        finally:
            await browser.close()

    # Merge all PDFs into one
    logger.info("Merging PDFs...")

    pdf_writer = PdfWriter()

    for pdf_buffer in pdf_buffers:
        pdf_reader = PdfReader(io.BytesIO(pdf_buffer))
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)

    # Save merged PDF to bytes
    output = io.BytesIO()
    pdf_writer.write(output)
    output.seek(0)

    logger.info(f"Created PDF with {len(pdf_writer.pages)} pages")

    return output.read()


async def convert_slides_to_pdf_with_progress(
    slides: List[SlideContentInfo]
) -> AsyncGenerator[Dict[str, Any], None]:
    """Convert slides to PDF with progress updates for SSE streaming.

    Args:
        slides: List of SlideContentInfo objects

    Yields:
        Dict with progress updates and final PDF bytes
    """
    if not slides:
        yield {"type": "error", "message": "No slides to convert"}
        return

    try:
        from playwright.async_api import async_playwright
        from pypdf import PdfWriter, PdfReader
    except ImportError as e:
        yield {"type": "error", "message": f"Missing dependencies: {e}"}
        return

    pdf_options = {
        'width': '1280px',
        'height': '720px',
        'print_background': True,
        'margin': {'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
        'display_header_footer': False,
        'prefer_css_page_size': False,
        'scale': 1
    }

    pdf_buffers = []
    total_slides = len(slides)

    yield {
        "type": "progress",
        "message": "Starting PDF generation...",
        "current": 0,
        "total": total_slides,
        "percent": 0
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )

            for index, slide in enumerate(slides, 1):
                yield {
                    "type": "progress",
                    "message": f"Converting slide {slide.slide_number} of {slide.presentation_name}",
                    "current": index,
                    "total": total_slides,
                    "percent": round((index / total_slides) * 80, 1)  # Reserve 20% for merge
                }

                page = await context.new_page()

                try:
                    await page.wait_for_load_state('domcontentloaded')
                    await page.set_content(
                        slide.slide_content,
                        wait_until='networkidle',
                        timeout=60000
                    )

                    pdf_buffer = await page.pdf(
                        print_background=pdf_options['print_background'],
                        margin=pdf_options['margin'],
                        display_header_footer=pdf_options['display_header_footer'],
                        prefer_css_page_size=pdf_options['prefer_css_page_size'],
                        scale=pdf_options['scale'],
                        width=pdf_options['width'],
                        height=pdf_options['height']
                    )

                    pdf_buffers.append(pdf_buffer)

                finally:
                    await page.close()

        finally:
            await browser.close()

    # Merge PDFs
    yield {
        "type": "progress",
        "message": "Merging PDFs...",
        "current": total_slides,
        "total": total_slides,
        "percent": 90.0
    }

    pdf_writer = PdfWriter()

    for pdf_buffer in pdf_buffers:
        pdf_reader = PdfReader(io.BytesIO(pdf_buffer))
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)

    output = io.BytesIO()
    pdf_writer.write(output)
    output.seek(0)

    logger.info(f"Created PDF with {len(pdf_writer.pages)} pages")

    # Final result
    yield {
        "type": "complete",
        "message": f"PDF created with {len(pdf_writer.pages)} pages",
        "pdf_bytes": output.read(),
        "total_pages": len(pdf_writer.pages)
    }
