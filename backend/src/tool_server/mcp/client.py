import httpx
import logging
from fastmcp.client import Client
from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool, StructuredTool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1800


class MCPClient(Client):
    """
    Enhanced MCP Client that extends fastmcp.client.Client with:
    - Custom credential management
    - Tool server URL configuration
    - Codex registration
    - Custom MCP integration
    - LangChain-compatible tool conversion
    
    Usage:
        async with MCPClient("https://6060-sandbox-id.e2b.app") as client:
            # Set credentials for authenticated tools
            await client.set_credential({
                "user_api_key": "your-api-key",
                "session_id": "session-123"
            })
            
            # Get tools as LangChain-compatible tools
            tools = await client.get_langchain_tools()
            
            # Use with LangGraph agent
            agent = create_react_agent(llm, tools)
    """
    
    def __init__(self, server_url: str, timeout: int = DEFAULT_TIMEOUT, **args):
        logger.info(f"Initializing MCPClient with server URL: {server_url}")
        self.server_url = server_url.rstrip("/")  # Remove trailing slash if present
        self.http_session = None
        self._timeout = timeout
        mcp_url = self.server_url + "/mcp"
        super().__init__(mcp_url, **args)

    async def __aenter__(self):
        self.http_session = httpx.AsyncClient(timeout=self._timeout)
        return await super().__aenter__()  # Initialize the parent class

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.http_session:
            await self.http_session.aclose()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def health_check(self) -> bool:
        """Check if the MCP server is healthy and responding."""
        if not self.http_session:
            raise Exception("MCPClient is not initialized. Use 'async with' context manager.")
        
        try:
            response = await self.http_session.get(
                self.server_url + "/health",
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def set_credential(self, credential: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set authentication credentials for tools that require them.
        
        Args:
            credential: Dict containing:
                - user_api_key: API key for authenticated tool calls
                - session_id: Session identifier for tracking
        
        Returns:
            Response from server confirming credential was set
        """
        if not self.http_session:
            raise Exception("MCPClient is not initialized. Use 'async with' context manager.")
        
        response = await self.http_session.post(
            self.server_url + "/credential", json=credential
        )
        if response.status_code != 200:
            raise Exception(f"Failed to set credential: {response.text}")
        logger.info("Credential set successfully")
        return response.json()

    async def set_tool_server_url(self, tool_server_url: str) -> Dict[str, Any]:
        """
        Set the external tool server URL for tools that make outbound API calls.
        
        Note: Credential must be set before calling this method.
        
        Args:
            tool_server_url: URL of the external tool server (e.g., "http://localhost:7000")
        
        Returns:
            Response from server confirming URL was set
        """
        if not self.http_session:
            raise Exception("MCPClient is not initialized. Use 'async with' context manager.")
        
        response = await self.http_session.post(
            self.server_url + "/tool-server-url",
            json={"tool_server_url": tool_server_url},
        )
        if response.status_code != 200:
            raise Exception(f"Failed to set tool server url: {response.text}")
        logger.info(f"Tool server URL set to: {tool_server_url}")
        return response.json()

    async def register_codex(self) -> Dict[str, Any]:
        """
        Register the Codex SSE HTTP server for enhanced code editing capabilities.
        
        Returns:
            Response containing status and Codex URL if successful
        """
        if not self.http_session:
            raise Exception("MCPClient is not initialized. Use 'async with' context manager.")
        
        response = await self.http_session.post(self.server_url + "/register-codex")
        if response.status_code != 200:
            raise Exception(f"Failed to register codex: {response.text}")
        logger.info("Codex registered successfully")
        return response.json()

    async def register_custom_mcp(self, mcp_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a custom MCP server configuration for additional tool integrations.
        
        Args:
            mcp_config: MCP server configuration dict (e.g., {"command": "...", "args": [...]})
        
        Returns:
            Response from server confirming registration
        """
        if not self.http_session:
            raise Exception("MCPClient is not initialized. Use 'async with' context manager.")

        response = await self.http_session.post(
            self.server_url + "/custom-mcp", json=mcp_config
        )
        if response.status_code != 200:
            raise Exception(f"Failed to register custom mcp: {response.text}")
        logger.info("Custom MCP registered successfully")
        return response.json()

    async def get_langchain_tools(self) -> List[BaseTool]:
        """
        Get all available tools as LangChain-compatible BaseTool instances.
        
        This converts MCP tools to LangChain's StructuredTool format,
        making them compatible with LangGraph agents (create_react_agent, etc.)
        
        Returns:
            List of LangChain BaseTool instances ready for agent use
        """
        # Get raw MCP tools from the server
        mcp_tools = await self.list_tools()
        langchain_tools = []
        
        for mcp_tool in mcp_tools:
            # Create async wrapper that calls the MCP tool
            tool_name = mcp_tool.name
            
            async def _call_tool(tool_name=tool_name, **kwargs) -> str:
                """Execute the MCP tool and return result."""
                result = await self.call_tool(tool_name, kwargs)
                # Handle different result types
                if hasattr(result, 'content'):
                    # MCP result with content attribute
                    if isinstance(result.content, list):
                        return "\n".join(str(item) for item in result.content)
                    return str(result.content)
                return str(result)
            
            # Build input schema from MCP tool parameters
            input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {}
            
            # Create LangChain StructuredTool
            langchain_tool = StructuredTool.from_function(
                coroutine=_call_tool,
                name=tool_name,
                description=mcp_tool.description or f"Execute {tool_name}",
                args_schema=None,  # Let it infer from function signature
            )
            
            langchain_tools.append(langchain_tool)
        
        logger.info(f"Converted {len(langchain_tools)} MCP tools to LangChain format")
        return langchain_tools

    async def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        tools = await self.list_tools()
        return [t.name for t in tools]

