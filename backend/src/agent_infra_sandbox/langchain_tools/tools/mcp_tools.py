"""MCP (Model Context Protocol) server integration tools for AIO Sandbox."""

from typing import List, Dict, Any, Optional

import structlog
from langchain_core.tools import tool, BaseTool

from langchain_tools.client import SandboxClient

logger = structlog.get_logger(__name__)


def create_mcp_tools(client: SandboxClient) -> List[BaseTool]:
    """Create all MCP integration tools bound to the given sandbox client.
    
    Args:
        client: SandboxClient instance
        
    Returns:
        List of MCP tools
    """
    
    @tool
    async def mcp_list_servers() -> str:
        """List all available MCP servers configured in the sandbox.
        
        MCP servers provide specialized tools like browser automation,
        file operations, shell execution, and document processing.
        
        Returns:
            List of available MCP server names, or error
        """
        try:
            logger.info("Listing MCP servers")
            
            result = await client.async_client.mcp.list_mcp_servers()
            
            servers = result.data or []
            if not servers:
                return "No MCP servers configured"
            
            output = f"Available MCP Servers ({len(servers)}):\n"
            for server in servers:
                output += f"  - {server}\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to list MCP servers: {e!s}"
            logger.error(error_msg, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def mcp_list_tools(
        server_name: str,
    ) -> str:
        """List all tools available on an MCP server.
        
        Args:
            server_name: Name of the MCP server (from mcp_list_servers)
            
        Returns:
            List of tools with their descriptions and parameters, or error
        """
        try:
            logger.info("Listing MCP tools", server_name=server_name)
            
            result = await client.async_client.mcp.list_mcp_tools(server_name)
            
            tools = result.data.tools or []
            if not tools:
                return f"No tools available on server '{server_name}'"
            
            output = f"Tools on '{server_name}' ({len(tools)}):\n\n"
            for t in tools:
                output += f"📌 {t.name}\n"
                if t.description:
                    output += f"   Description: {t.description}\n"
                if t.input_schema and t.input_schema.get('properties'):
                    params = list(t.input_schema['properties'].keys())
                    output += f"   Parameters: {', '.join(params)}\n"
                output += "\n"
                
            return output.rstrip()
            
        except Exception as e:
            error_msg = f"Failed to list tools: {e!s}"
            logger.error(error_msg, server_name=server_name, error=str(e))
            return f"ERROR: {error_msg}"
    
    @tool
    async def mcp_execute(
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a tool on an MCP server.
        
        Use mcp_list_tools to discover available tools and their parameters.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool
            
        Returns:
            Tool execution result, or error
        """
        try:
            logger.info("Executing MCP tool", server_name=server_name, tool_name=tool_name)
            
            result = await client.async_client.mcp.execute_mcp_tool(
                server_name=server_name,
                tool_name=tool_name,
                request=arguments or {},
            )
            
            data = result.data
            
            # Format the content response
            outputs = []
            for content in data.content or []:
                if hasattr(content, 'text') and content.text:
                    outputs.append(content.text)
                elif hasattr(content, 'type'):
                    if content.type == 'text':
                        outputs.append(content.text)
                    elif content.type == 'image':
                        outputs.append(f"[IMAGE: {content.mime_type or 'image/png'}]")
            
            if data.is_error:
                return f"ERROR: Tool execution failed. Output:\n{''.join(outputs)}"
                
            if not outputs:
                return "(no output)"
                
            return "\n".join(outputs)
            
        except Exception as e:
            error_msg = f"Failed to execute MCP tool: {e!s}"
            logger.error(error_msg, server_name=server_name, tool_name=tool_name, error=str(e))
            return f"ERROR: {error_msg}"
    
    return [
        mcp_list_servers,
        mcp_list_tools,
        mcp_execute,
    ]
