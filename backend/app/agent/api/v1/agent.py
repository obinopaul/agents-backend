# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent API endpoint with sandbox support.

This module provides the streaming agent endpoint that:
- Creates sandboxes lazily (only when tools need them)
- Reuses sandboxes for the same session
- Streams responses in real-time using SSE

Unlike /chat/stream, this endpoint is designed for agent workflows
that require code execution, file operations, and other sandbox tools.
"""

import asyncio
import json
import logging
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_decode
from backend.core.conf import settings
from backend.src.graph.builder import graph
from backend.src.graph.checkpointer import checkpointer_manager
from backend.src.rag.retriever import Resource
from backend.src.services.session_sandbox_manager import SessionSandboxManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton graph instance
# The PostgreSQL checkpointer is injected at runtime by checkpointer_manager
_graph = graph


# =============================================================================
# Request/Response Models
# =============================================================================

class AgentMessage(BaseModel):
    """Represents a single message in the agent conversation."""
    
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="The message content")
    name: Optional[str] = Field(None, description="Optional name of the message sender")


class AgentRequest(BaseModel):
    """Request model for the agent streaming endpoint."""
    
    messages: List[AgentMessage] = Field(..., description="List of conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for conversation continuity")
    session_id: Optional[str] = Field(None, description="Session ID for sandbox reuse")
    resources: List[Resource] = Field(default_factory=list, description="RAG resources")
    max_plan_iterations: int = Field(default=1, ge=1, le=10, description="Maximum plan iterations")
    max_step_num: int = Field(default=3, ge=1, le=10, description="Maximum steps in a plan")
    max_search_results: int = Field(default=3, ge=1, le=20, description="Maximum search results")
    auto_accepted_plan: bool = Field(default=True, description="Auto-accept generated plans")
    interrupt_feedback: Optional[str] = Field(None, description="Feedback for interrupted workflows")
    enable_background_investigation: bool = Field(default=True, description="Enable background web search")
    enable_web_search: bool = Field(default=True, description="Enable web search")
    enable_deep_thinking: bool = Field(default=False, description="Enable deep thinking mode")
    locale: str = Field(default="en-US", description="User's language locale")


# =============================================================================
# Helper Functions
# =============================================================================

def _make_event(event_type: str, data: dict) -> str:
    """Create a Server-Sent Event (SSE) formatted string."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _get_recursion_limit() -> int:
    """Get recursion limit from settings with fallback."""
    return settings.AGENT_RECURSION_LIMIT if settings.AGENT_RECURSION_LIMIT > 0 else 25


# =============================================================================
# Stream Generator
# =============================================================================

async def _agent_stream_generator(
    messages: List[dict],
    thread_id: str,
    sandbox_manager: SessionSandboxManager,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: Optional[str],
    enable_background_investigation: bool,
    enable_web_search: bool,
    enable_deep_thinking: bool,
    locale: str,
):
    """
    Async generator for streaming agent workflow events.
    
    This generator:
    1. Sends "processing" status immediately
    2. Creates/reuses sandbox (lazy initialization)
    3. Sends "sandbox_ready" status
    4. Runs agent workflow
    5. Streams responses
    """
    try:
        # STEP 1: Send immediate feedback
        yield _make_event("status", {
            "type": "processing",
            "message": "Processing your request..."
        })
        
        # STEP 2: Get or create sandbox (lazy initialization)
        try:
            logger.info(f"Agent stream: Getting sandbox for session {sandbox_manager.session_id}")
            sandbox = await sandbox_manager.get_sandbox()
            
            yield _make_event("status", {
                "type": "sandbox_ready",
                "sandbox_id": sandbox.sandbox_id,
                "message": "Environment ready"
            })
            
        except Exception as e:
            logger.error(f"Agent stream: Sandbox creation failed: {e}")
            yield _make_event("error", {
                "type": "sandbox_error",
                "message": f"Failed to create sandbox: {e}"
            })
            return
        
        # STEP 3: Wait for MCP server to be ready (with keep-alive events)
        # Get MCP URL for debugging
        mcp_url = await sandbox.expose_port(6060)
        logger.info(f"Agent stream: MCP URL = {mcp_url}")
        
        yield _make_event("status", {
            "type": "mcp_check",
            "message": "Checking tool server...",
            "mcp_url": mcp_url,
        })
        
        # Inline MCP health check with keep-alive events to prevent nginx timeout
        import httpx
        from datetime import datetime
        
        mcp_ready = False
        mcp_timeout = 90  # 90 seconds max
        poll_interval = 2  # Poll every 2 seconds for faster detection (was 10s)
        start_time = datetime.now()
        
        async with httpx.AsyncClient() as client:
            while (datetime.now() - start_time).seconds < mcp_timeout:
                elapsed = (datetime.now() - start_time).seconds
                try:
                    resp = await client.get(f"{mcp_url}/health", timeout=8.0)
                    if resp.status_code == 200:
                        logger.info(f"Agent stream: MCP ready after {elapsed}s")
                        mcp_ready = True
                        break
                except Exception as e:
                    logger.debug(f"Agent stream: MCP not ready ({elapsed}s): {type(e).__name__}")
                
                # Send keep-alive event to prevent nginx timeout
                yield _make_event("status", {
                    "type": "mcp_waiting",
                    "message": f"Waiting for tool server... ({elapsed}s)",
                    "elapsed_seconds": elapsed,
                })
                
                await asyncio.sleep(poll_interval)
        
        if not mcp_ready:
            logger.warning("Agent stream: MCP not ready, proceeding anyway")
            yield _make_event("warning", {
                "type": "mcp_timeout",
                "message": "Tool server starting slowly, some tools may be delayed",
                "mcp_url": mcp_url,
            })
        else:
            yield _make_event("status", {
                "type": "mcp_ready",
                "message": "Tools ready",
                "mcp_url": mcp_url,
            })
        
        
        # STEP 4: MCP URL already obtained above, use it for workflow
        
        # STEP 5: Build workflow input
        workflow_input = {
            "messages": messages,
            "locale": locale,
            "auto_accepted_plan": auto_accepted_plan,
            "enable_background_investigation": enable_background_investigation,
        }
        
        workflow_config = {
            "configurable": {
                "thread_id": thread_id,
                "enable_web_search": enable_web_search,
                "max_search_results": max_search_results,
                "max_plan_iterations": max_plan_iterations,
                "max_step_num": max_step_num,
                "enable_deep_thinking": enable_deep_thinking,
                "sandbox_id": sandbox.sandbox_id,
                "mcp_url": mcp_url,
            },
            "recursion_limit": _get_recursion_limit(),
        }
        
        # STEP 6: Stream graph events with PostgreSQL checkpointer
        yield _make_event("status", {
            "type": "agent_start",
            "message": "Agent processing..."
        })
        
        # Use the centralized PostgreSQL checkpointer
        async with checkpointer_manager.get_graph_with_checkpointer(_graph, thread_id) as configured_graph:
            async for event in configured_graph.astream_events(
                workflow_input,
                config=workflow_config,
                version="v2",
            ):
                event_type = event.get("event", "")
                
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if isinstance(chunk, AIMessageChunk) and chunk.content:
                        yield _make_event("message", {
                            "type": "chunk",
                            "content": chunk.content,
                            "thread_id": thread_id,
                        })
                
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    yield _make_event("tool", {
                        "type": "start",
                        "name": tool_name,
                    })
                
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    yield _make_event("tool", {
                        "type": "end",
                        "name": tool_name,
                    })
        
        # STEP 7: Send completion
        yield _make_event("status", {
            "type": "complete",
            "message": "Done",
            "sandbox_id": sandbox.sandbox_id,
        })
        
    except Exception as e:
        logger.exception(f"Agent stream error: {e}")
        yield _make_event("error", {
            "type": "stream_error",
            "message": str(e)
        })


# =============================================================================
# Endpoint
# =============================================================================

@router.post(
    '/stream',
    summary="Stream agent responses with sandbox support",
    description="Process user messages through an AI agent workflow with sandbox tools and stream responses.",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming response with SSE events",
            "content": {"text/event-stream": {}},
        },
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def agent_stream(request: AgentRequest, http_request: Request):
    """
    Stream agent responses with sandbox tool support.
    
    This endpoint:
    - Creates a sandbox lazily (only when needed)
    - Reuses sandboxes for the same session_id
    - Streams responses in real-time using SSE
    
    Events emitted:
    - status: Processing status updates
    - message: Agent response chunks
    - tool: Tool execution events
    - error: Error events
    - warning: Non-fatal warnings
    
    Authentication required via JWT token.
    """
    # Get current user ID from JWT token
    token = get_token(http_request)
    token_payload = jwt_decode(token)
    user_id = str(token_payload.id)
    
    # Generate thread/session IDs if needed
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    
    session_id = request.session_id or thread_id
    
    # Create session sandbox manager (lazy - no sandbox yet)
    sandbox_manager = SessionSandboxManager(
        user_id=user_id,
        session_id=session_id
    )
    
    # Convert messages to dict format
    messages = [msg.model_dump() for msg in request.messages]
    
    return StreamingResponse(
        _agent_stream_generator(
            messages=messages,
            thread_id=thread_id,
            sandbox_manager=sandbox_manager,
            resources=request.resources,
            max_plan_iterations=request.max_plan_iterations,
            max_step_num=request.max_step_num,
            max_search_results=request.max_search_results,
            auto_accepted_plan=request.auto_accepted_plan,
            interrupt_feedback=request.interrupt_feedback,
            enable_background_investigation=request.enable_background_investigation,
            enable_web_search=request.enable_web_search,
            enable_deep_thinking=request.enable_deep_thinking,
            locale=request.locale,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
