"""Slide event subscriber for syncing tool results to database.

This subscriber intercepts slide tool results (SlideWrite, SlideEdit, 
slide_apply_patch) and persists them to the slide_content database table.

The subscriber handles multiple tool result formats:
1. LangChain tuple format: (content_str, artifact_dict)
2. MCP FastMCPToolResult with structured_content
3. Direct dict with content/new_content
4. List format (for batch operations)

Integration:
    The agent should call SlideEventSubscriber.on_tool_complete()
    after each slide tool execution to sync the result to the database.

Usage in LangGraph agent:
    ```python
    from backend.src.services.slides.slide_subscriber import slide_subscriber
    
    # In the on_tool_end event handler:
    await slide_subscriber.on_tool_complete(
        db_session=db_session,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result=tool_output,
        thread_id=thread_id,
        sandbox_id=sandbox.sandbox_id,  # Optional: for content processing
    )
    ```

Adapted from external_slide_system/database_subscriber.py with production enhancements.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.services.slides.service import SlideService

logger = logging.getLogger(__name__)


# Tool name constants - must match exactly what the tools return
SLIDE_WRITE_TOOL = "SlideWrite"
SLIDE_EDIT_TOOL = "SlideEdit"
SLIDE_APPLY_PATCH_TOOL = "slide_apply_patch"

SLIDE_TOOLS = frozenset([SLIDE_WRITE_TOOL, SLIDE_EDIT_TOOL, SLIDE_APPLY_PATCH_TOOL])

# Regex pattern for parsing slide filepath
# Format: /workspace/presentations/{presentation_name}/slide_{number}.html
SLIDE_FILEPATH_PATTERN = re.compile(
    r"/workspace/presentations/([^/]+)/slide_(\d+)\.html$"
)


class ToolResultExtractor:
    """
    Robust extractor for tool results across different formats.
    
    Handles the various structures that tool results can have:
    - LangChain adapter tuple: (content_str, artifact_dict)
    - MCP structured_content: {structured_content: {user_display_content: {...}}}
    - Direct user_display_content dict
    - FastMCPToolResult objects
    - List of results
    """
    
    @staticmethod
    def extract_user_display_content(tool_result: Any) -> Optional[Dict[str, Any]]:
        """
        Extract user_display_content from any tool result format.
        
        Args:
            tool_result: The raw tool result in any supported format
            
        Returns:
            Dict containing the user display content, or None if not found
        """
        # Format 1: LangChain adapter tuple (content_str, artifact_dict)
        # This is the most common format when using LangChain agents
        if isinstance(tool_result, tuple):
            return ToolResultExtractor._extract_from_tuple(tool_result)
        
        # Format 2: Dict with various structures
        if isinstance(tool_result, dict):
            return ToolResultExtractor._extract_from_dict(tool_result)
        
        # Format 3: List (for batch operations or some MCP formats)
        if isinstance(tool_result, list):
            return ToolResultExtractor._extract_from_list(tool_result)
        
        # Format 4: Object with structured_content attribute (FastMCPToolResult)
        if hasattr(tool_result, 'structured_content'):
            return ToolResultExtractor._extract_from_object(tool_result)
        
        # Format 5: String (minimal result, no display content)
        if isinstance(tool_result, str):
            logger.debug("Tool result is string, no display content available")
            return None
        
        logger.warning(f"Unknown tool result type: {type(tool_result).__name__}")
        return None
    
    @staticmethod
    def _extract_from_tuple(tool_result: tuple) -> Optional[Dict[str, Any]]:
        """Extract from LangChain adapter tuple format."""
        if len(tool_result) < 2:
            logger.debug(f"Tuple has only {len(tool_result)} elements, expected 2")
            return None
        
        content_str, artifact = tool_result
        
        if not isinstance(artifact, dict):
            logger.debug(f"Artifact is not dict: {type(artifact).__name__}")
            return None
        
        # The artifact contains display_content from LangChainToolAdapter._format_result()
        display_content = artifact.get("display_content")
        
        if display_content is None:
            logger.debug("No display_content in artifact")
            return None
        
        # display_content can be dict, list, or string
        if isinstance(display_content, dict):
            return display_content
        elif isinstance(display_content, list):
            # Return as-is for batch processing
            return {"_batch_results": display_content}
        elif isinstance(display_content, str):
            # String content, wrap in dict
            return {"content": display_content}
        
        return None
    
    @staticmethod
    def _extract_from_dict(tool_result: dict) -> Optional[Dict[str, Any]]:
        """Extract from various dict formats."""
        # Check for MCP structured_content wrapper
        if "structured_content" in tool_result:
            sc = tool_result.get("structured_content", {})
            if isinstance(sc, dict):
                udc = sc.get("user_display_content")
                if isinstance(udc, dict):
                    return udc
                elif isinstance(udc, list):
                    return {"_batch_results": udc}
        
        # Check for direct user_display_content
        if "user_display_content" in tool_result:
            udc = tool_result.get("user_display_content")
            if isinstance(udc, dict):
                return udc
            elif isinstance(udc, list):
                return {"_batch_results": udc}
        
        # Check if this is the result dict itself (has content or new_content)
        if "content" in tool_result or "new_content" in tool_result:
            return tool_result
        
        # Check if this is a slide result with filepath
        if "filepath" in tool_result:
            return tool_result
        
        logger.debug(f"Dict has no recognized content keys: {list(tool_result.keys())}")
        return tool_result  # Return as-is, let caller handle
    
    @staticmethod
    def _extract_from_list(tool_result: list) -> Optional[Dict[str, Any]]:
        """Extract from list format."""
        if not tool_result:
            return None
        
        first_item = tool_result[0]
        
        # If first item is a dict with slide data, return batch format
        if isinstance(first_item, dict) and ("content" in first_item or "new_content" in first_item or "filepath" in first_item):
            return {"_batch_results": tool_result}
        
        # Otherwise try to extract from first item
        if isinstance(first_item, dict):
            return ToolResultExtractor._extract_from_dict(first_item)
        
        return None
    
    @staticmethod
    def _extract_from_object(tool_result: Any) -> Optional[Dict[str, Any]]:
        """Extract from objects with structured_content attribute."""
        sc = getattr(tool_result, 'structured_content', None)
        
        if sc is None:
            return None
        
        if isinstance(sc, dict):
            udc = sc.get("user_display_content")
            if isinstance(udc, dict):
                return udc
            elif isinstance(udc, list):
                return {"_batch_results": udc}
        
        return None


class SlideEventSubscriber:
    """
    Production-grade subscriber for syncing slide tool results to database.
    
    Features:
    - Handles multiple tool result formats (LangChain, MCP, direct)
    - Robust error handling with detailed logging
    - Support for batch slide operations
    - Content processing integration (optional)
    - Thread-safe for concurrent operations
    """

    def __init__(self):
        """Initialize the slide event subscriber."""
        self._extractor = ToolResultExtractor()
        # Content processor will be initialized lazily when needed
        self._content_processor = None

    async def on_tool_complete(
        self,
        *,
        db_session: AsyncSession,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Any,
        thread_id: str,
        sandbox_id: Optional[str] = None,
        sandbox_download_func: Optional[callable] = None,
    ) -> bool:
        """
        Handle a tool completion event and sync to database.
        
        Args:
            db_session: SQLAlchemy async session for database operations
            tool_name: Name of the tool that completed
            tool_input: Input parameters passed to the tool
            tool_result: Result returned by the tool (supports multiple formats)
            thread_id: Thread ID for this conversation
            sandbox_id: Optional sandbox ID for content processing
            sandbox_download_func: Optional async function to download sandbox files
            
        Returns:
            bool: True if slide was saved successfully, False otherwise
        """
        # Debug logging for all tool completions
        print(f"DEBUG: SlideEventSubscriber.on_tool_complete called", flush=True)
        print(f"DEBUG:   tool_name={tool_name}", flush=True)
        print(f"DEBUG:   thread_id={thread_id}", flush=True)
        print(f"DEBUG:   tool_result type={type(tool_result).__name__}", flush=True)
        
        if isinstance(tool_input, dict):
            print(f"DEBUG:   tool_input keys={list(tool_input.keys())}", flush=True)
        
        # Fast path: Skip non-slide tools immediately
        if tool_name not in SLIDE_TOOLS:
            return False

        print(f"DEBUG: Processing slide tool: {tool_name}", flush=True)
        logger.info(f"Processing slide tool result: {tool_name} for thread {thread_id}")

        try:
            if tool_name == SLIDE_APPLY_PATCH_TOOL:
                saved = await self._handle_slide_apply_patch_result(
                    db_session=db_session,
                    tool_result=tool_result,
                    thread_id=thread_id,
                    sandbox_id=sandbox_id,
                    sandbox_download_func=sandbox_download_func,
                )
            else:
                saved = await self._handle_single_slide_result(
                    db_session=db_session,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_result=tool_result,
                    thread_id=thread_id,
                    sandbox_id=sandbox_id,
                    sandbox_download_func=sandbox_download_func,
                )
            
            if saved:
                print(f"DEBUG: Successfully saved slide(s) to database", flush=True)
            else:
                print(f"DEBUG: No slides were saved (possibly no content)", flush=True)
            
            return saved

        except Exception as e:
            logger.error(f"Error handling {tool_name} result: {e}", exc_info=True)
            print(f"DEBUG: Exception in slide subscriber: {type(e).__name__}: {e}", flush=True)
            return False

    async def _handle_single_slide_result(
        self,
        *,
        db_session: AsyncSession,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Any,
        thread_id: str,
        sandbox_id: Optional[str] = None,
        sandbox_download_func: Optional[callable] = None,
    ) -> bool:
        """
        Handle SlideWrite or SlideEdit tool results.
        
        Returns:
            bool: True if slide was saved, False otherwise
        """
        # Extract presentation metadata from tool input
        presentation_name = tool_input.get("presentation_name")
        slide_number = tool_input.get("slide_number")
        slide_title = tool_input.get("title", "")

        if not presentation_name:
            logger.warning(f"Missing presentation_name in {tool_name} input")
            print(f"DEBUG: Missing presentation_name in tool_input", flush=True)
            return False
            
        if slide_number is None:
            logger.warning(f"Missing slide_number in {tool_name} input")
            print(f"DEBUG: Missing slide_number in tool_input", flush=True)
            return False

        # Ensure slide_number is int
        try:
            slide_number = int(slide_number)
        except (ValueError, TypeError):
            logger.warning(f"Invalid slide_number: {slide_number}")
            return False

        print(f"DEBUG: Extracting content for {tool_name}", flush=True)
        print(f"DEBUG:   presentation={presentation_name}, slide={slide_number}", flush=True)

        # Extract user_display_content from the tool result
        user_display = self._extractor.extract_user_display_content(tool_result)
        
        print(f"DEBUG: Extracted user_display type: {type(user_display).__name__ if user_display else 'None'}", flush=True)
        if isinstance(user_display, dict):
            print(f"DEBUG: user_display keys: {list(user_display.keys())}", flush=True)

        # Extract slide content based on tool type
        slide_content = ""
        
        if user_display and isinstance(user_display, dict):
            if tool_name == SLIDE_WRITE_TOOL:
                slide_content = user_display.get("content", "")
            elif tool_name == SLIDE_EDIT_TOOL:
                slide_content = user_display.get("new_content", "")
        
        # Fallback 1: Try to get content from the filepath data
        if not slide_content and user_display and isinstance(user_display, dict):
            # Some formats include filepath info along with content
            if "new_content" in user_display:
                slide_content = user_display["new_content"]
        
        # Fallback 2: Use content from tool_input (the original content sent to tool)
        if not slide_content and tool_name == SLIDE_WRITE_TOOL:
            slide_content = tool_input.get("content", "")
            if slide_content:
                print(f"DEBUG: Using content from tool_input (fallback)", flush=True)
                logger.info(f"Using content from tool_input as fallback for {tool_name}")
        
        if not slide_content:
            logger.warning(f"No content found in {tool_name} result or input")
            print(f"DEBUG: No content found - cannot save slide", flush=True)
            return False

        print(f"DEBUG: Content length: {len(slide_content)} chars", flush=True)

        # Process content if we have sandbox access (replace local URLs with permanent ones)
        if sandbox_id and sandbox_download_func:
            slide_content = await self._process_content(
                content=slide_content,
                sandbox_id=sandbox_id,
                thread_id=thread_id,
                sandbox_download_func=sandbox_download_func,
            )

        # Save to database
        print(f"DEBUG: Saving slide to database...", flush=True)
        logger.info(
            f"Saving {tool_name} result: presentation='{presentation_name}', "
            f"slide={slide_number}, content_length={len(slide_content)}"
        )
        
        slide_id = await SlideService.save_slide_to_db(
            db_session=db_session,
            thread_id=thread_id,
            presentation_name=presentation_name,
            slide_number=slide_number,
            slide_title=slide_title,
            slide_content=slide_content,
            tool_name=tool_name,
        )
        
        print(f"DEBUG: Slide saved with ID: {slide_id}", flush=True)
        logger.info(f"Saved slide {slide_number} in '{presentation_name}' (id={slide_id})")
        
        return True

    async def _handle_slide_apply_patch_result(
        self,
        *,
        db_session: AsyncSession,
        tool_result: Any,
        thread_id: str,
        sandbox_id: Optional[str] = None,
        sandbox_download_func: Optional[callable] = None,
    ) -> bool:
        """
        Handle SlideApplyPatchTool results which can contain multiple slides.
        
        Returns:
            bool: True if at least one slide was saved, False otherwise
        """
        print(f"DEBUG: Handling slide_apply_patch result", flush=True)
        
        # Extract user_display_content which should contain the batch results
        user_display = self._extractor.extract_user_display_content(tool_result)
        
        # Get the list of slide data
        slides_data = []
        
        if user_display and isinstance(user_display, dict):
            # Check for batch results wrapper
            if "_batch_results" in user_display:
                batch = user_display["_batch_results"]
                if isinstance(batch, list):
                    slides_data = batch
            # Or the user_display itself is a list
            elif isinstance(user_display.get("slides"), list):
                slides_data = user_display["slides"]
        
        # Fallback: If tool_result is directly a list
        if not slides_data and isinstance(tool_result, list):
            slides_data = tool_result
        
        # Handle tuple format where second element might have the batch
        if not slides_data and isinstance(tool_result, tuple) and len(tool_result) >= 2:
            _, artifact = tool_result
            if isinstance(artifact, dict):
                dc = artifact.get("display_content")
                if isinstance(dc, list):
                    slides_data = dc

        if not slides_data:
            logger.warning("SlideApplyPatch result has no slide data")
            print(f"DEBUG: No slides_data found in patch result", flush=True)
            return False

        print(f"DEBUG: Found {len(slides_data)} slides in patch result", flush=True)
        
        saved_count = 0
        
        for slide_data in slides_data:
            if not isinstance(slide_data, dict):
                continue

            # Extract filepath to get presentation_name and slide_number
            filepath = slide_data.get("filepath", "")
            
            if not filepath:
                continue

            # Parse filepath using regex
            match = SLIDE_FILEPATH_PATTERN.search(filepath)
            if not match:
                logger.debug(f"Filepath doesn't match pattern: {filepath}")
                continue

            presentation_name = match.group(1)
            slide_number = int(match.group(2))

            # Get content
            slide_content = slide_data.get("new_content", "")
            if not slide_content:
                continue

            # Process content if we have sandbox access
            if sandbox_id and sandbox_download_func:
                slide_content = await self._process_content(
                    content=slide_content,
                    sandbox_id=sandbox_id,
                    thread_id=thread_id,
                    sandbox_download_func=sandbox_download_func,
                )

            # Save to database
            try:
                slide_id = await SlideService.save_slide_to_db(
                    db_session=db_session,
                    thread_id=thread_id,
                    presentation_name=presentation_name,
                    slide_number=slide_number,
                    slide_title="",  # Patch tool doesn't provide title
                    slide_content=slide_content,
                    tool_name=SLIDE_APPLY_PATCH_TOOL,
                )
                
                saved_count += 1
                logger.info(
                    f"Saved patch result for slide {slide_number} in '{presentation_name}' (id={slide_id})"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to save patch for slide {slide_number} in '{presentation_name}': {e}"
                )

        print(f"DEBUG: Saved {saved_count}/{len(slides_data)} slides from patch", flush=True)
        return saved_count > 0

    async def _process_content(
        self,
        content: str,
        sandbox_id: str,
        thread_id: str,
        sandbox_download_func: callable,
    ) -> str:
        """
        Process slide content to replace local URLs with permanent storage URLs.
        
        This is optional and only runs if content processor is available.
        Falls back to original content on any error.
        
        Args:
            content: HTML slide content
            sandbox_id: ID of sandbox containing files
            thread_id: Thread ID for storage path organization
            sandbox_download_func: Async function to download from sandbox
            
        Returns:
            Processed content with permanent URLs, or original on failure
        """
        try:
            # Lazy import to avoid circular dependencies
            from backend.src.services.slides.content_processor import SlideContentProcessor
            
            if self._content_processor is None:
                self._content_processor = SlideContentProcessor(
                    sandbox_download_func=sandbox_download_func
                )
            
            processed = await self._content_processor.process_html_content(
                html=content,
                sandbox_id=sandbox_id,
                thread_id=thread_id,
            )
            
            if processed != content:
                logger.info(f"Processed content: replaced local URLs with permanent URLs")
            
            return processed
            
        except ImportError:
            # Content processor not available, skip processing
            logger.debug("SlideContentProcessor not available, skipping content processing")
            return content
        except Exception as e:
            # On any error, return original content
            logger.warning(f"Content processing failed, using original: {e}")
            return content


# Singleton instance for convenience
slide_subscriber = SlideEventSubscriber()
