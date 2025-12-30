# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Chat API endpoints.

This module provides the streaming chat endpoint for AI agent conversations,
with full JWT authentication, request validation, and production-grade
error handling.

Uses PostgreSQL for graph state checkpointing via the centralized
checkpointer_manager.
"""

import asyncio
import base64
import json
import logging
from typing import Annotated, Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_decode
from backend.core.conf import settings
from backend.src.config.configuration import Configuration
from backend.src.graph.builder import graph
from backend.src.graph.checkpoint import chat_stream_message
from backend.src.graph.checkpointer import checkpointer_manager
from backend.src.graph.utils import (
    build_clarified_topic_from_history,
    reconstruct_clarification_history,
)
from backend.src.rag.retriever import Resource
from backend.src.utils.json_utils import sanitize_args
from backend.src.utils.log_sanitizer import (
    sanitize_agent_name,
    sanitize_log_input,
    sanitize_thread_id,
    sanitize_tool_name,
    sanitize_user_content,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton graph instance
# The PostgreSQL checkpointer is injected at runtime by checkpointer_manager
_graph = graph

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"


class ChatMessage(BaseModel):
    """Represents a single message in the chat conversation."""

    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="The message content")
    name: Optional[str] = Field(None, description="Optional name of the message sender")


class MCPServerConfig(BaseModel):
    """Configuration for an MCP (Model Context Protocol) server."""

    transport: str = Field(..., description="Transport type: 'stdio' or 'http'")
    command: Optional[str] = Field(None, description="Command to start the MCP server")
    args: Optional[List[str]] = Field(None, description="Arguments for the command")
    url: Optional[str] = Field(None, description="URL for HTTP transport")
    enabled_tools: Optional[List[str]] = Field(None, description="List of enabled tool names")
    add_to_agents: Optional[List[str]] = Field(None, description="Agents to add the tools to")


class MCPSettings(BaseModel):
    """MCP settings containing server configurations."""

    servers: Optional[dict[str, MCPServerConfig]] = Field(None, description="MCP server configurations")


class ChatRequest(BaseModel):
    """Request model for the chat streaming endpoint."""

    messages: List[ChatMessage] = Field(..., description="List of conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for conversation continuity")
    resources: List[Resource] = Field(default_factory=list, description="RAG resources for the conversation")
    max_plan_iterations: int = Field(default=1, ge=1, le=10, description="Maximum number of plan iterations")
    max_step_num: int = Field(default=3, ge=1, le=10, description="Maximum number of steps in a plan")
    max_search_results: int = Field(default=3, ge=1, le=20, description="Maximum number of search results")
    auto_accepted_plan: bool = Field(default=True, description="Auto-accept generated plans")
    interrupt_feedback: Optional[str] = Field(None, description="Feedback for interrupted workflows")
    mcp_settings: Optional[MCPSettings] = Field(None, description="MCP server configuration")
    enable_background_investigation: bool = Field(default=True, description="Enable background web search")
    enable_web_search: bool = Field(default=True, description="Enable web search in research steps")
    enable_deep_thinking: bool = Field(default=False, description="Enable deep thinking mode")
    enable_clarification: bool = Field(default=False, description="Enable clarification mode")
    max_clarification_rounds: int = Field(default=3, ge=1, le=10, description="Maximum clarification rounds")
    locale: str = Field(default="en-US", description="User's language locale")
    interrupt_before_tools: Optional[List[str]] = Field(None, description="Tools to interrupt before execution")


def _get_recursion_limit() -> int:
    """Get the recursion limit from settings with fallback."""
    return settings.AGENT_RECURSION_LIMIT if settings.AGENT_RECURSION_LIMIT > 0 else 25


def _validate_tool_call_chunks(tool_call_chunks: list) -> None:
    """Validate and log tool call chunk structure for debugging."""
    if not tool_call_chunks:
        return

    logger.debug(f"Validating tool_call_chunks: count={len(tool_call_chunks)}")

    indices_seen = set()
    tool_ids_seen = set()

    for i, chunk in enumerate(tool_call_chunks):
        index = chunk.get("index")
        tool_id = chunk.get("id")
        name = chunk.get("name", "")
        has_args = "args" in chunk

        logger.debug(
            f"Chunk {i}: index={index}, id={tool_id}, name={name}, "
            f"has_args={has_args}, type={chunk.get('type')}"
        )

        if index is not None:
            indices_seen.add(index)
        if tool_id:
            tool_ids_seen.add(tool_id)

    if len(indices_seen) > 1:
        logger.debug(
            f"Multiple indices detected: {sorted(indices_seen)} - "
            f"This may indicate consecutive tool calls"
        )


def _process_tool_call_chunks(tool_call_chunks: list) -> list:
    """
    Process tool call chunks with proper index-based grouping.

    This function handles the concatenation of tool call chunks that belong
    to the same tool call (same index) while properly segregating chunks
    from different tool calls (different indices).
    """
    if not tool_call_chunks:
        return []

    _validate_tool_call_chunks(tool_call_chunks)

    chunks = []
    chunk_by_index = {}

    for chunk in tool_call_chunks:
        index = chunk.get("index")
        chunk_id = chunk.get("id")

        if index is not None:
            if index not in chunk_by_index:
                chunk_by_index[index] = {
                    "name": "",
                    "args": "",
                    "id": chunk_id or "",
                    "index": index,
                    "type": chunk.get("type", ""),
                }

            chunk_name = chunk.get("name", "")
            if chunk_name:
                stored_name = chunk_by_index[index]["name"]
                if stored_name and stored_name != chunk_name:
                    logger.warning(
                        f"Tool name mismatch detected at index {index}: "
                        f"'{stored_name}' != '{chunk_name}'. "
                        f"This may indicate a streaming artifact."
                    )
                else:
                    chunk_by_index[index]["name"] = chunk_name

            if chunk_id and not chunk_by_index[index]["id"]:
                chunk_by_index[index]["id"] = chunk_id

            if chunk.get("args"):
                chunk_by_index[index]["args"] += chunk.get("args", "")
        else:
            logger.debug(f"Chunk without index encountered: {chunk}")
            chunks.append({
                "name": chunk.get("name", ""),
                "args": sanitize_args(chunk.get("args", "")),
                "id": chunk.get("id", ""),
                "index": 0,
                "type": chunk.get("type", ""),
            })

    for index in sorted(chunk_by_index.keys()):
        chunk_data = chunk_by_index[index]
        chunk_data["args"] = sanitize_args(chunk_data["args"])
        chunks.append(chunk_data)
        logger.debug(
            f"Processed tool call: index={index}, name={chunk_data['name']}, "
            f"id={chunk_data['id']}"
        )

    return chunks


def _get_agent_name(agent: tuple, message_metadata: dict) -> str:
    """Extract agent name from agent tuple."""
    agent_name = "unknown"
    if agent and len(agent) > 0:
        agent_name = agent[0].split(":")[0] if ":" in agent[0] else agent[0]
    else:
        agent_name = message_metadata.get("langgraph_node", "unknown")
    return agent_name


def _create_event_stream_message(
    message_chunk: BaseMessage,
    message_metadata: dict,
    thread_id: str,
    agent_name: str,
) -> dict:
    """Create base event stream message."""
    content = message_chunk.content
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    event_stream_message = {
        "thread_id": thread_id,
        "agent": agent_name,
        "id": message_chunk.id,
        "role": "assistant",
        "checkpoint_ns": message_metadata.get("checkpoint_ns", ""),
        "langgraph_node": message_metadata.get("langgraph_node", ""),
        "langgraph_path": message_metadata.get("langgraph_path", ""),
        "langgraph_step": message_metadata.get("langgraph_step", ""),
        "content": content,
    }

    if message_chunk.additional_kwargs.get("reasoning_content"):
        event_stream_message["reasoning_content"] = message_chunk.additional_kwargs["reasoning_content"]

    if message_chunk.response_metadata.get("finish_reason"):
        event_stream_message["finish_reason"] = message_chunk.response_metadata.get("finish_reason")

    return event_stream_message


def _create_interrupt_event(thread_id: str, event_data: dict) -> str:
    """Create interrupt event."""
    interrupt = event_data["__interrupt__"][0]
    interrupt_id = getattr(interrupt, "id", None) or thread_id
    return _make_event(
        "interrupt",
        {
            "thread_id": thread_id,
            "id": interrupt_id,
            "role": "assistant",
            "content": interrupt.value,
            "finish_reason": "interrupt",
            "options": [
                {"text": "Edit plan", "value": "edit_plan"},
                {"text": "Start research", "value": "accepted"},
            ],
        },
    )


def _process_initial_messages(message: dict, thread_id: str) -> None:
    """Process initial messages and yield formatted events."""
    json_data = json.dumps(
        {
            "thread_id": thread_id,
            "id": "run--" + message.get("id", uuid4().hex),
            "role": "user",
            "content": message.get("content", ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat_stream_message(
        thread_id, f"event: message_chunk\ndata: {json_data}\n\n", "none"
    )


async def _process_message_chunk(
    message_chunk: BaseMessage,
    message_metadata: dict,
    thread_id: str,
    agent: tuple,
):
    """Process a single message chunk and yield appropriate events."""
    agent_name = _get_agent_name(agent, message_metadata)
    safe_agent_name = sanitize_agent_name(agent_name)
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] _process_message_chunk started for agent={safe_agent_name}")

    event_stream_message = _create_event_stream_message(
        message_chunk, message_metadata, thread_id, agent_name
    )

    if isinstance(message_chunk, ToolMessage):
        tool_call_id = message_chunk.tool_call_id
        event_stream_message["tool_call_id"] = tool_call_id

        if tool_call_id:
            safe_tool_id = sanitize_log_input(tool_call_id, max_length=100)
            logger.debug(f"[{safe_thread_id}] ToolMessage with tool_call_id: {safe_tool_id}")
        else:
            logger.warning(f"[{safe_thread_id}] ToolMessage received without tool_call_id")

        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, AIMessageChunk):
        if message_chunk.tool_calls:
            safe_tool_names = [sanitize_tool_name(tc.get('name', 'unknown')) for tc in message_chunk.tool_calls]
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has complete tool_calls: {safe_tool_names}")
            event_stream_message["tool_calls"] = message_chunk.tool_calls

            processed_chunks = _process_tool_call_chunks(message_chunk.tool_call_chunks)
            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks

            yield _make_event("tool_calls", event_stream_message)
        elif message_chunk.tool_call_chunks:
            processed_chunks = _process_tool_call_chunks(message_chunk.tool_call_chunks)

            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks

            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            yield _make_event("message_chunk", event_stream_message)


async def _stream_graph_events(
    graph_instance: Any,
    workflow_input: dict,
    workflow_config: dict,
    thread_id: str,
):
    """Stream events from the graph and process them."""
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] Starting graph event stream with agent nodes")
    event_count = 0
    try:
        async for agent, _, event_data in graph_instance.astream(
            workflow_input,
            config=workflow_config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            event_count += 1
            safe_agent = sanitize_agent_name(agent)
            logger.debug(f"[{safe_thread_id}] Graph event #{event_count} received from agent: {safe_agent}")

            if isinstance(event_data, dict):
                if "__interrupt__" in event_data:
                    yield _create_interrupt_event(thread_id, event_data)
                continue

            message_chunk, message_metadata = event_data

            async for event in _process_message_chunk(
                message_chunk, message_metadata, thread_id, agent
            ):
                yield event

        logger.debug(f"[{safe_thread_id}] Graph event stream completed. Total events: {event_count}")
    except asyncio.CancelledError:
        logger.info(f"[{safe_thread_id}] Graph event stream cancelled by user after {event_count} events")
        raise
    except Exception as e:
        logger.exception(f"[{safe_thread_id}] Error during graph execution")
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "error": "Error during graph execution",
            },
        )


async def _astream_workflow_generator(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation: bool,
    enable_web_search: bool,
    enable_deep_thinking: bool,
    enable_clarification: bool,
    max_clarification_rounds: int,
    locale: str = "en-US",
    interrupt_before_tools: Optional[List[str]] = None,
):
    """
    Async generator for streaming workflow events.

    This is the core engine that processes user messages through the LangGraph
    agent workflow and yields Server-Sent Events (SSE) for real-time streaming.
    """
    safe_thread_id = sanitize_thread_id(thread_id)
    safe_feedback = sanitize_log_input(interrupt_feedback) if interrupt_feedback else ""
    logger.debug(
        f"[{safe_thread_id}] _astream_workflow_generator starting: "
        f"messages_count={len(messages)}, auto_accepted_plan={auto_accepted_plan}"
    )

    # Process initial messages
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            _process_initial_messages(message, thread_id)

    # Reconstruct clarification history
    clarification_history = reconstruct_clarification_history(messages)
    clarified_topic, clarification_history = build_clarified_topic_from_history(clarification_history)
    latest_message_content = messages[-1]["content"] if messages else ""
    clarified_research_topic = clarified_topic or latest_message_content

    # Prepare workflow input
    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": latest_message_content,
        "clarification_history": clarification_history,
        "clarified_research_topic": clarified_research_topic,
        "enable_clarification": enable_clarification,
        "max_clarification_rounds": max_clarification_rounds,
        "locale": locale,
    }

    # Handle resume from interrupt with feedback
    if not auto_accepted_plan and interrupt_feedback:
        resume_msg = f"[{interrupt_feedback}]"
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        workflow_input = Command(resume=resume_msg)

    # Prepare workflow config
    workflow_config = {
        "thread_id": thread_id,
        "resources": resources,
        "max_plan_iterations": max_plan_iterations,
        "max_step_num": max_step_num,
        "max_search_results": max_search_results,
        "mcp_settings": mcp_settings,
        "enable_web_search": enable_web_search,
        "enable_deep_thinking": enable_deep_thinking,
        "interrupt_before_tools": interrupt_before_tools,
        "recursion_limit": _get_recursion_limit(),
    }

    # Use centralized PostgreSQL checkpointer (shared connection pool)
    logger.info(f"[{safe_thread_id}] Using PostgreSQL checkpointer")
    async with checkpointer_manager.get_graph_with_checkpointer(_graph, thread_id) as configured_graph:
        async for event in _stream_graph_events(
            configured_graph, workflow_input, workflow_config, thread_id
        ):
            yield event


def _make_event(event_type: str, data: dict) -> str:
    """Create a Server-Sent Event (SSE) formatted string."""
    if data.get("content") == "":
        data.pop("content", None)

    try:
        json_data = json.dumps(data, ensure_ascii=False)
        finish_reason = data.get("finish_reason", "")
        chat_stream_message(
            data.get("thread_id", ""),
            f"event: {event_type}\ndata: {json_data}\n\n",
            finish_reason,
        )
        return f"event: {event_type}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing event data: {e}")
        error_data = json.dumps({"error": "Serialization failed"}, ensure_ascii=False)
        return f"event: error\ndata: {error_data}\n\n"


@router.post(
    '/stream',
    summary="Stream AI agent chat responses",
    description="Process user messages through the AI agent workflow and stream responses in real-time using Server-Sent Events (SSE).",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming response with SSE events",
            "content": {"text/event-stream": {}},
        },
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - MCP configuration disabled"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def chat_stream(request: ChatRequest, http_request: Request):
    """
    Stream AI agent chat responses.

    This endpoint processes user messages through a multi-agent LangGraph workflow
    and streams responses in real-time using Server-Sent Events (SSE).

    The workflow includes:
    - Coordinator agent for conversation management
    - Planner agent for research planning
    - Researcher agent for web searches
    - Analyst and Coder agents for processing
    - Reporter agent for final output generation

    Authentication is required via JWT token.
    """
    # Get current user ID from JWT token
    token = get_token(http_request)
    token_payload = jwt_decode(token)
    user_id = str(token_payload.id)
    logger.debug(f"Chat stream request from user: {user_id}")

    # Check MCP configuration
    mcp_enabled = settings.AGENT_MCP_ENABLED

    if request.mcp_settings and not mcp_enabled:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set AGENT_MCP_ENABLED=true in settings to enable MCP features.",
        )

    # Generate thread ID if default
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())

    # Convert messages to dict format
    messages = [msg.model_dump() for msg in request.messages]
    mcp_settings_dict = request.mcp_settings.model_dump() if request.mcp_settings else {}

    return StreamingResponse(
        _astream_workflow_generator(
            messages=messages,
            thread_id=thread_id,
            resources=request.resources,
            max_plan_iterations=request.max_plan_iterations,
            max_step_num=request.max_step_num,
            max_search_results=request.max_search_results,
            auto_accepted_plan=request.auto_accepted_plan,
            interrupt_feedback=request.interrupt_feedback,
            mcp_settings=mcp_settings_dict if mcp_enabled else {},
            enable_background_investigation=request.enable_background_investigation,
            enable_web_search=request.enable_web_search,
            enable_deep_thinking=request.enable_deep_thinking,
            enable_clarification=request.enable_clarification,
            max_clarification_rounds=request.max_clarification_rounds,
            locale=request.locale,
            interrupt_before_tools=request.interrupt_before_tools,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
