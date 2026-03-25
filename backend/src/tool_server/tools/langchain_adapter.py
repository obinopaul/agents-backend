"""
LangChain Tool Adapter

This module provides an adapter layer that wraps the project's custom BaseTool
implementations to make them compatible with LangChain's tool interface.

The adapter:
- Converts JSON Schema `input_schema` to Pydantic `args_schema`
- Translates `ToolResult` to LangChain's expected return format
- Supports `response_format="content_and_artifact"` for multi-modal content
- Provides async execution via `_arun`
- Includes JWT authentication context support for production use

Usage:
    from backend.src.tool_server.tools.langchain_adapter import (
        LangChainToolAdapter,
        adapt_tools_for_langchain,
    )
    
    # Adapt a single tool
    browser_click = BrowserClickTool(browser)
    lc_browser_click = LangChainToolAdapter.from_base_tool(browser_click)
    
    # Adapt all tools at once
    base_tools = get_sandbox_tools(workspace_path, credential)
    langchain_tools = adapt_tools_for_langchain(base_tools)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union, Tuple, TYPE_CHECKING
import logging
from pydantic import BaseModel, Field, create_model

from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun

# Use TYPE_CHECKING to avoid importing heavy backend modules at module load
# These imports only happen for type hints at type-checking time
if TYPE_CHECKING:
    from backend.src.tool_server.tools.base import (
        BaseTool as ProjectBaseTool,
        ToolResult,
        TextContent,
        ImageContent,
    )

logger = logging.getLogger(__name__)



class AuthenticationContext(BaseModel):
    """Context for JWT authentication in production settings.
    
    This allows tools to access the authentication context when needed,
    particularly for tools that need to make authenticated requests
    to external services or validate user permissions.
    """
    user_id: Optional[str] = None
    token: Optional[str] = None
    session_id: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"  # Allow additional fields for flexibility


def json_schema_to_pydantic_model(
    name: str,
    schema: Dict[str, Any]
) -> Type[BaseModel]:
    """Convert a JSON Schema dict to a Pydantic model.
    
    This is essential for LangChain's `args_schema` which requires a Pydantic
    model to properly communicate expected inputs to the LLM.
    
    Args:
        name: Name for the generated model class
        schema: JSON Schema dict with 'properties' and 'required' keys
        
    Returns:
        A dynamically created Pydantic model class
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    # Map JSON Schema types to Python types
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    
    field_definitions = {}
    
    for field_name, field_schema in properties.items():
        # Get the Python type
        json_type = field_schema.get("type", "string")
        python_type = type_mapping.get(json_type, Any)
        
        # Handle array types with items
        if json_type == "array" and "items" in field_schema:
            item_type = type_mapping.get(
                field_schema["items"].get("type", "string"), Any
            )
            python_type = List[item_type]
        
        # Get description and default
        description = field_schema.get("description", "")
        default = field_schema.get("default", ...)
        
        # If not required and no default, make it Optional with None default
        if field_name not in required:
            if default is ...:
                default = None
            python_type = Optional[python_type]
        
        # Create the field with description
        field_definitions[field_name] = (
            python_type,
            Field(default=default, description=description)
        )
    
    # Create and return the dynamic model
    return create_model(f"{name}Input", **field_definitions)


class LangChainToolAdapter(LangChainBaseTool):
    """Adapter that wraps the project's BaseTool to work with LangChain agents.
    
    This adapter bridges the gap between the project's custom tool implementation
    and LangChain's expected tool interface, enabling seamless integration with
    LangChain agents like ReAct, OpenAI Functions, and LangGraph.
    
    Key features:
    - Converts JSON Schema to Pydantic args_schema
    - Handles text, image, and artifact responses
    - Supports async execution
    - Provides authentication context for production use
    
    Attributes:
        name: Tool name (from wrapped tool)
        description: Tool description (from wrapped tool)
        args_schema: Pydantic model for input validation (generated from input_schema)
        response_format: Set to "content_and_artifact" for multi-modal responses
        wrapped_tool: Reference to the original project BaseTool
        auth_context: Optional authentication context for JWT-protected operations
    """
    
    name: str
    description: str
    args_schema: Type[BaseModel]
    response_format: str = "content_and_artifact"  # Support returning (content, artifact)
    
    # The wrapped project tool (excluded from serialization)
    wrapped_tool: Any = Field(exclude=True)
    
    # Authentication context for production use
    auth_context: Optional[AuthenticationContext] = Field(
        default=None, 
        exclude=True,
        description="JWT authentication context for production deployments"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def from_base_tool(
        cls,
        tool: ProjectBaseTool,
        auth_context: Optional[AuthenticationContext] = None,
    ) -> "LangChainToolAdapter":
        """Create a LangChain tool adapter from a project BaseTool.
        
        Args:
            tool: The project's BaseTool instance to wrap
            auth_context: Optional authentication context for production use
            
        Returns:
            A LangChainToolAdapter instance ready for use with LangChain agents
            
        Example:
            >>> browser_click = BrowserClickTool(browser)
            >>> lc_tool = LangChainToolAdapter.from_base_tool(browser_click)
            >>> # Now usable with LangChain agents
            >>> agent = create_react_agent(llm, [lc_tool])
        """
        # Generate Pydantic model from JSON Schema
        args_schema = json_schema_to_pydantic_model(
            tool.name,
            tool.input_schema
        )
        
        return cls(
            name=tool.name,
            description=tool.description,
            args_schema=args_schema,
            wrapped_tool=tool,
            auth_context=auth_context,
        )
    
    def set_auth_context(self, auth_context: AuthenticationContext) -> None:
        """Set authentication context for production API calls.
        
        In production, this should be called with the JWT token and user info
        before tools are used. This is typically done at the API endpoint level.
        
        Args:
            auth_context: Authentication context with JWT token and user info
        """
        self.auth_context = auth_context
    
    def _format_result(self, result: ToolResult) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Format a ToolResult into LangChain's expected (content, artifact) tuple.
        
        Args:
            result: The project's ToolResult from tool execution
            
        Returns:
            Tuple of (content_str, artifact_dict) where:
            - content_str: Text content for the LLM to process
            - artifact_dict: Additional data (images, metadata) for the application
        """
        # Runtime import to avoid circular/heavy dependencies at module load
        from backend.src.tool_server.tools.base import TextContent, ImageContent
        
        llm_content = result.llm_content
        artifact = None
        
        # Handle string content
        if isinstance(llm_content, str):
            content = llm_content
            
            # Check if there's user display content to preserve as artifact
            if result.user_display_content:
                artifact = {
                    "display_content": result.user_display_content,
                    "is_error": result.is_error or False,
                }
        
        # Handle list content (mixed text/images)
        elif isinstance(llm_content, list):
            text_parts = []
            images = []
            
            for item in llm_content:
                if isinstance(item, TextContent):
                    text_parts.append(item.text)
                elif isinstance(item, ImageContent):
                    images.append({
                        "type": "image",
                        "data": item.data,  # base64 encoded
                        "mime_type": item.mime_type,
                    })
            
            # Combine text for LLM
            content = "\n".join(text_parts) if text_parts else "[Image content]"
            
            # Create artifact with images and metadata
            artifact = {
                "images": images,
                "display_content": result.user_display_content,
                "is_error": result.is_error or False,
            }
        
        else:
            content = str(llm_content)
        
        # Add error indicator to content if needed
        if result.is_error:
            content = f"[ERROR] {content}"
        
        return content, artifact
    
    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Union[str, Tuple[str, Any]]:
        """Synchronous execution - wraps the async execute method.
        
        Note: The project's tools are async, so we run them in an event loop.
        For truly synchronous environments, consider using `_arun` directly.
        """
        import asyncio
        
        # Try to get existing event loop, or create new one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context, can't use run_until_complete
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.wrapped_tool.execute(kwargs)
                    )
                    result = future.result()
            else:
                result = loop.run_until_complete(
                    self.wrapped_tool.execute(kwargs)
                )
        except RuntimeError:
            # No event loop, create one
            result = asyncio.run(self.wrapped_tool.execute(kwargs))
        
        return self._format_result(result)
    
    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Union[str, Tuple[str, Any]]:
        """Asynchronous execution - directly calls the tool's async execute.
        
        This is the preferred method as the project's tools are async by design.
        
        Args:
            run_manager: Optional callback manager for LangChain callbacks
            **kwargs: Tool input parameters (validated by args_schema)
            
        Returns:
            Tuple of (content, artifact) for multi-modal responses
        """
        try:
            result = await self.wrapped_tool.execute(kwargs)
            return self._format_result(result)
            
        except Exception as e:
            error_msg = f"Tool execution failed: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Return error in consistent format
            return (
                f"[ERROR] {error_msg}",
                {"is_error": True, "exception": str(e)}
            )


def adapt_tools_for_langchain(
    tools: List[ProjectBaseTool],
    auth_context: Optional[AuthenticationContext] = None,
) -> List[LangChainToolAdapter]:
    """Convert a list of project BaseTools to LangChain-compatible tools.
    
    This is the main entry point for adapting all tools at once.
    
    Args:
        tools: List of project BaseTool instances (from get_sandbox_tools, etc.)
        auth_context: Optional authentication context for production use
        
    Returns:
        List of LangChainToolAdapter instances ready for use with LangChain agents
        
    Example:
        >>> from backend.src.tool_server.tools.manager import get_sandbox_tools
        >>> base_tools = get_sandbox_tools(workspace_path, credential)
        >>> langchain_tools = adapt_tools_for_langchain(base_tools)
        >>> agent = create_react_agent(llm, langchain_tools)
    """
    adapted_tools = []
    
    for tool in tools:
        try:
            adapted = LangChainToolAdapter.from_base_tool(tool, auth_context)
            adapted_tools.append(adapted)
            logger.debug(f"Adapted tool: {tool.name}")
        except Exception as e:
            logger.error(f"Failed to adapt tool '{tool.name}': {e}")
            # Skip tools that fail to adapt rather than failing entirely
            continue
    
    logger.info(f"Adapted {len(adapted_tools)}/{len(tools)} tools for LangChain")
    return adapted_tools


def get_langchain_tools(
    workspace_path: str,
    credential: Dict[str, Any],
    auth_context: Optional[AuthenticationContext] = None,
) -> List[LangChainToolAdapter]:
    """Get all sandbox tools as LangChain-compatible tools.
    
    This is a convenience function that combines getting the tools
    and adapting them in one step.
    
    Args:
        workspace_path: Path to the workspace directory in the sandbox
        credential: Credential dictionary for web/media tools
        auth_context: Optional JWT authentication context
        
    Returns:
        List of LangChain-compatible tools ready for agent use
        
    Example:
        >>> tools = get_langchain_tools("/home/user/workspace", {"TAVILY_API_KEY": "..."})
        >>> agent = create_react_agent(get_llm(), tools)
    """
    from backend.src.tool_server.tools.manager import get_sandbox_tools
    
    base_tools = get_sandbox_tools(workspace_path, credential)
    return adapt_tools_for_langchain(base_tools, auth_context)
