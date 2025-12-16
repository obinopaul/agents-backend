# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent MCP (Model Context Protocol) API endpoints.

This module provides endpoints for managing MCP servers and loading tools dynamically.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.src.server.mcp_utils import load_mcp_tools

logger = logging.getLogger(__name__)

router = APIRouter()


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Input schema for the tool")


class MCPServerMetadataRequest(BaseModel):
    """Request model for MCP server metadata."""

    transport: str = Field(..., description="Transport type: 'stdio' or 'http'")
    command: Optional[str] = Field(None, description="Command to start the MCP server (for stdio)")
    args: Optional[List[str]] = Field(None, description="Arguments for the command")
    url: Optional[str] = Field(None, description="URL for HTTP transport")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables for the server")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers (for http transport)")
    timeout_seconds: Optional[int] = Field(
        default=300,
        ge=1,
        le=600,
        description="Timeout in seconds for loading tools"
    )


class MCPServerMetadataResponse(BaseModel):
    """Response model for MCP server metadata."""

    transport: str = Field(..., description="Transport type")
    command: Optional[str] = Field(None, description="Command used")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    url: Optional[str] = Field(None, description="Server URL")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    tools: List[MCPToolInfo] = Field(default_factory=list, description="Available tools")


@router.post(
    '/server/metadata',
    summary="Get MCP server metadata and tools",
    description="Connect to an MCP server and retrieve its available tools.",
    response_model=MCPServerMetadataResponse,
    responses={
        200: {"description": "MCP server metadata with tools"},
        401: {"description": "Unauthorized"},
        403: {"description": "MCP configuration disabled"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """
    Get metadata and available tools from an MCP server.

    This endpoint connects to an MCP (Model Context Protocol) server
    and retrieves information about the tools it provides.

    Requires AGENT_MCP_ENABLED=true in settings.

    Supported transports:
    - stdio: Start a local process via command/args
    - http: Connect to an HTTP server via URL
    """
    # Check if MCP is enabled
    if not settings.AGENT_MCP_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set AGENT_MCP_ENABLED=true in settings to enable MCP features.",
        )

    try:
        timeout = request.timeout_seconds or settings.AGENT_MCP_TIMEOUT_SECONDS

        # Load tools from the MCP server
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            timeout_seconds=timeout,
        )

        # Convert tools to response format
        tool_infos = []
        for tool in tools:
            tool_info = MCPToolInfo(
                name=tool.name if hasattr(tool, 'name') else str(tool),
                description=getattr(tool, 'description', None),
                input_schema=getattr(tool, 'args_schema', None),
            )
            tool_infos.append(tool_info)

        return MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            tools=tool_infos,
        )

    except Exception as e:
        logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
