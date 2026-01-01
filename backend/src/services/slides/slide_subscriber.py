"""Slide event subscriber for syncing tool results to database.

This subscriber intercepts slide tool results (SlideWrite, SlideEdit, 
slide_apply_patch) and persists them to the slide_content database table.

Integration:
    The module/ppt agent should call SlideEventSubscriber.on_tool_complete()
    after each slide tool execution to sync the result to the database.

Usage in LangGraph agent:
    ```python
    from backend.src.services.slides.slide_subscriber import SlideEventSubscriber
    
    subscriber = SlideEventSubscriber()
    
    # In your tool execution callback:
    async def handle_tool_result(tool_name, tool_input, tool_result, thread_id, db_session):
        await subscriber.on_tool_complete(
            db_session=db_session,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_result=tool_result,
            thread_id=thread_id,
        )
    ```

Adapted from external_slide_system/database_subscriber.py.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.slides.service import SlideService

logger = logging.getLogger(__name__)


# Tool name constants
SLIDE_WRITE_TOOL = "SlideWrite"
SLIDE_EDIT_TOOL = "SlideEdit"
SLIDE_APPLY_PATCH_TOOL = "slide_apply_patch"

SLIDE_TOOLS = [SLIDE_WRITE_TOOL, SLIDE_EDIT_TOOL, SLIDE_APPLY_PATCH_TOOL]


class SlideEventSubscriber:
    """Subscriber that handles slide tool results and syncs to database."""

    async def on_tool_complete(
        self,
        *,
        db_session: AsyncSession,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Any,
        thread_id: str,
    ) -> bool:
        """Handle a tool completion event.
        
        Args:
            db_session: SQLAlchemy async session
            tool_name: Name of the tool that completed
            tool_input: Input parameters passed to the tool
            tool_result: Result returned by the tool
            thread_id: Thread ID for this conversation
            
        Returns:
            bool: True if slide was saved, False otherwise
        """
        if tool_name not in SLIDE_TOOLS:
            return False

        logger.info(f"Handling slide tool result for: {tool_name}")

        try:
            if tool_name == SLIDE_APPLY_PATCH_TOOL:
                await self._handle_slide_apply_patch_result(
                    db_session=db_session,
                    tool_result=tool_result,
                    thread_id=thread_id,
                )
            else:
                await self._handle_single_slide_result(
                    db_session=db_session,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_result=tool_result,
                    thread_id=thread_id,
                )
            return True

        except Exception as e:
            logger.error(f"Error handling {tool_name} result: {e}", exc_info=True)
            return False

    async def _handle_single_slide_result(
        self,
        *,
        db_session: AsyncSession,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Any,
        thread_id: str,
    ) -> None:
        """Handle SlideWrite or SlideEdit tool results."""
        presentation_name = tool_input.get("presentation_name")
        slide_number = tool_input.get("slide_number")

        if not presentation_name or not slide_number:
            logger.warning(f"Missing presentation info in {tool_name} result")
            return

        # Extract content based on tool type
        slide_content = None
        slide_title = tool_input.get("title", "")

        # Handle different result structures
        if isinstance(tool_result, dict):
            user_display = tool_result
        elif isinstance(tool_result, list) and len(tool_result) > 0:
            user_display = tool_result[0]
        else:
            user_display = {}

        if tool_name == SLIDE_WRITE_TOOL:
            slide_content = user_display.get("content", "")
        elif tool_name == SLIDE_EDIT_TOOL:
            slide_content = user_display.get("new_content", "")

        if not slide_content:
            logger.warning(f"No content found in {tool_name} result")
            return

        # Save to database
        await SlideService.save_slide_to_db(
            db_session=db_session,
            thread_id=thread_id,
            presentation_name=presentation_name,
            slide_number=slide_number,
            slide_title=slide_title,
            slide_content=slide_content,
            tool_name=tool_name,
        )

    async def _handle_slide_apply_patch_result(
        self,
        *,
        db_session: AsyncSession,
        tool_result: Any,
        thread_id: str,
    ) -> None:
        """Handle SlideApplyPatchTool results which can contain multiple slides."""
        # tool_result should be a list of slide data dicts
        if not isinstance(tool_result, list):
            logger.warning("SlideApplyPatch result is not a list")
            return

        for slide_data in tool_result:
            if not isinstance(slide_data, dict):
                continue

            # Extract filepath to get presentation_name and slide_number
            # Format: /workspace/presentations/{presentation_name}/slide_{number}.html
            filepath = slide_data.get("filepath", "")
            if not filepath or "/presentations/" not in filepath:
                continue

            try:
                # Parse the path
                parts = filepath.split("/presentations/")[-1].split("/")
                if len(parts) < 2:
                    continue

                presentation_name = parts[0]
                slide_filename = parts[1]

                # Extract slide number from filename (e.g., slide_1.html -> 1)
                if not slide_filename.startswith("slide_") or not slide_filename.endswith(".html"):
                    continue

                slide_number = int(
                    slide_filename.replace("slide_", "").replace(".html", "")
                )

                # Get content
                slide_content = slide_data.get("new_content", "")
                if not slide_content:
                    continue

                # Save to database
                await SlideService.save_slide_to_db(
                    db_session=db_session,
                    thread_id=thread_id,
                    presentation_name=presentation_name,
                    slide_number=slide_number,
                    slide_title="",  # Patch tool doesn't provide title
                    slide_content=slide_content,
                    tool_name=SLIDE_APPLY_PATCH_TOOL,
                )

                logger.info(
                    f"Saved patch result for slide {slide_number} in {presentation_name}"
                )

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse filepath {filepath}: {e}")
                continue


# Singleton instance for convenience
slide_subscriber = SlideEventSubscriber()
