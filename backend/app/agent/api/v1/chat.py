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

import langchain
langchain.verbose = False
langchain.debug = False

import asyncio
import base64
import json
import logging
from typing import Annotated, Any, Dict, List, Optional, Union
from uuid import uuid4
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_decode
from backend.core.conf import settings
from backend.src.config.configuration import Configuration
from backend.src.graph.builder import graph
from backend.src.graph.checkpoint import chat_stream_message
from backend.src.graph.checkpointer import checkpointer_manager
from backend.app.agent.service.chat_session_service import chat_session_service
from backend.app.agent.crud.crud_chat_event import chat_event_dao
from backend.app.agent.crud.crud_chat_session import chat_session_dao
from backend.database.db import async_db_session

from backend.src.rag.retriever import Resource
from backend.src.utils.json_utils import sanitize_args, safe_json_serialize
from backend.src.utils.log_sanitizer import (
    sanitize_agent_name,
    sanitize_log_input,
    sanitize_thread_id,
    sanitize_tool_name,
    sanitize_user_content,
)

# Import structured models for AG-UI Protocol
from backend.app.agent.models import (
    ChatMessage,
    ReasoningState,
    ToolCall,
    ToolResult,
    make_ag_ui_event,
    # HITL models
    HITLRequest,
    create_hitl_interrupt_event,
)

from backend.app.agent.service.asset_service import process_and_stage_asset


# Import II-Agent Event Adapter for frontend compatibility
from backend.app.agent.event_adapter import (
    IIAgentSSEAdapter,
    create_sse_adapter,
    humanize_tool_name,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton graph instance
# The PostgreSQL checkpointer is injected at runtime by checkpointer_manager
_graph = graph

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"


# =============================================================================
# Request/Response Models
# =============================================================================

# ChatMessage imported from backend.app.agent.models


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


class ChatToolSettings(BaseModel):
    """Tool settings for chat mode."""

    web_search: bool = Field(default=True, description="Enable web search")
    image_search: bool = Field(default=True, description="Enable image search")
    web_visit: bool = Field(default=True, description="Enable web page visits")
    code_interpreter: bool = Field(default=True, description="Enable code interpreter")


class ChatRequest(BaseModel):
    """Request model for the chat streaming endpoint."""

    messages: List[ChatMessage] = Field(..., description="List of conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for conversation continuity")
    session_id: Optional[str] = Field(None, description="Session ID (alias for thread_id, used by frontend)")
    model_id: Optional[str] = Field(None, description="Model ID to use for this request")
    file_ids: Optional[List[str]] = Field(None, description="List of file IDs attached to this message")
    agent_type: str = Field(default="chat", description="Agent type (chat, data_scientist, etc.)")
    tools: Optional[ChatToolSettings] = Field(None, description="Tool settings for this chat")
    resources: List[Resource] = Field(default_factory=list, description="RAG resources for the conversation")
    max_search_results: int = Field(default=3, ge=1, le=20, description="Maximum number of search results")
    mcp_settings: Optional[MCPSettings] = Field(None, description="MCP server configuration (user-provided, not sandbox)")
    enable_background_investigation: bool = Field(default=False, description="Enable background web search before agent starts")
    enable_web_search: bool = Field(default=True, description="Enable web search")
    locale: str = Field(default="en-US", description="User's language locale")


def _get_recursion_limit() -> int:
    """Get the recursion limit from settings with fallback."""
    return settings.AGENT_RECURSION_LIMIT if settings.AGENT_RECURSION_LIMIT > 0 else 1000


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
    # FIX: Do not stringify content here if it is a list (e.g., proper tool result with images)
    # The adapter or _make_event will handle serialization later.
    # if not isinstance(content, str):
    #     content = json.dumps(content, ensure_ascii=False)

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
    """
    Create AG-UI interrupt event using structured HITL models.
    
    Handles LangGraph interrupts and converts them to AG-UI Protocol format.
    Uses HITLRequest for proper parsing and event generation.
    """
    interrupt = event_data["__interrupt__"][0]
    interrupt_value = getattr(interrupt, "value", interrupt)
    
    # Use the structured HITL model for proper event generation
    return create_hitl_interrupt_event(interrupt_value, thread_id)


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
    reasoning_state: ReasoningState,
    adapter: Optional[IIAgentSSEAdapter] = None,
    user_id: Optional[str] = None,
    db: Optional[Any] = None,
):
    """
    Process a single message chunk and yield appropriate events.

    Emits both:
    1. II-Agent Frontend format events (via adapter):
       - content: Text content (start/delta/stop)
       - thinking: Reasoning content (start/delta/stop)
       - tool_call: Tool lifecycle (start/delta/stop)
       - tool_result: Tool outputs

    2. AG-UI Protocol compatible events (for backward compatibility):
       - reasoning_start/message_start/message_content/message_end/end
       - tool_call_start/args/end
       - tool_result
       - message_chunk

    Args:
        message_chunk: LangChain message chunk
        message_metadata: Metadata from the graph event
        thread_id: Thread/session identifier
        agent: Agent tuple from graph
        reasoning_state: ReasoningState instance for tracking reasoning across chunks
        adapter: Optional IIAgentSSEAdapter for II-Agent format events
    """
    agent_name = _get_agent_name(agent, message_metadata)
    safe_agent_name = sanitize_agent_name(agent_name)
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] _process_message_chunk started for agent={safe_agent_name}")

    event_stream_message = _create_event_stream_message(
        message_chunk, message_metadata, thread_id, agent_name
    )

    if isinstance(message_chunk, ToolMessage):
        tool_call_id = message_chunk.tool_call_id
        
        # Intercept and process base64 images in tool content
        if isinstance(message_chunk.content, list) and user_id and db:
            new_content = []
            modified = False
            for block in message_chunk.content:
                if isinstance(block, dict) and block.get("type") == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        try:
                            # Upload to S3
                            base64_data = source.get("data")
                            media_type = source.get("media_type", "image/png")
                            
                            # Decode
                            image_data = base64.b64decode(base64_data)
                            
                            # Upload
                            url, _ = await process_and_stage_asset(
                                user_id=user_id,
                                content=image_data,
                                mime_type=media_type,
                                filename=f"tool_output.png", # Asset service handles extension
                                db=db,
                                thread_id=thread_id
                            )
                            
                            # Replace with URL block
                            new_content.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": url
                                }
                            })
                            modified = True
                            logger.info(f"[{safe_thread_id}] Uploaded tool image to {url}")
                        except Exception as e:
                            logger.error(f"[{safe_thread_id}] Failed to upload tool image: {e}")
                            new_content.append(block)
                    else:
                        new_content.append(block)
                else:
                    new_content.append(block)
            
            if modified:
                message_chunk.content = new_content
                # Update event stream message content
                event_stream_message["content"] = new_content

        event_stream_message["tool_call_id"] = tool_call_id
        # AG-UI: Also include toolCallId for consistency
        event_stream_message["toolCallId"] = tool_call_id

        if tool_call_id:
            safe_tool_id = sanitize_log_input(tool_call_id, max_length=100)
            logger.debug(f"[{safe_thread_id}] ToolMessage with tool_call_id: {safe_tool_id}")
        else:
            logger.warning(f"[{safe_thread_id}] ToolMessage received without tool_call_id")

        # Emit II-Agent format tool_result
        if adapter:
            tool_name = getattr(message_chunk, 'name', '') or event_stream_message.get('langgraph_node', '')
            output = event_stream_message.get('content', '')
            is_error = getattr(message_chunk, 'status', '') == 'error'
            yield adapter.tool_result(tool_call_id, tool_name, output, is_error)

        # Emit tool_result with II-Agent protocol field names for frontend compatibility
        tool_name = getattr(message_chunk, 'name', '') or event_stream_message.get('langgraph_node', '')
        is_error = getattr(message_chunk, 'status', '') == 'error'
        yield _make_event("tool_result", {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "tool_display_name": humanize_tool_name(tool_name),
            "tool_input": {},  # ToolMessage doesn't carry input
            "result": event_stream_message.get('content', ''),
            "is_error": is_error,
            "thread_id": thread_id,
        })

        # Also emit legacy tool_call_result for backwards compatibility
        yield _make_event("tool_call_result", event_stream_message)
        
    elif isinstance(message_chunk, AIMessageChunk):
        # Process content blocks - LangChain standardizes reasoning/text/etc.
        # content_blocks provides unified format across all providers
        has_processed_content = False
        
        if hasattr(message_chunk, 'content_blocks') and message_chunk.content_blocks:
            for block in message_chunk.content_blocks:
                if not isinstance(block, dict):
                    continue
                
                block_type = block.get('type', '')
                
                # Handle reasoning blocks (auto-standardized by LangChain)
                if block_type == 'reasoning':
                    reasoning_text = block.get('reasoning') or block.get('thinking') or block.get('text', '')

                    if reasoning_text:
                        has_processed_content = True

                        # Start reasoning session if not already active
                        if not reasoning_state.is_active:
                            msg_id = reasoning_state.start_reasoning()

                            # Emit II-Agent format thinking start
                            if adapter and not adapter.thinking_active:
                                yield adapter.thinking_start()

                            # Emit AG-UI format for backward compatibility
                            yield _make_event("reasoning_start", {
                                "messageId": msg_id,
                            })
                            yield _make_event("reasoning_message_start", {
                                "messageId": msg_id,
                                "role": "assistant",
                            })

                        # Emit II-Agent format thinking delta
                        if adapter:
                            yield adapter.thinking_delta(reasoning_text)

                        # Stream reasoning content (AG-UI format)
                        yield _make_event("reasoning_message_content", {
                            "messageId": reasoning_state.message_id,
                            "delta": reasoning_text,
                        })
                
                # Handle text blocks
                elif block_type == 'text':
                    text_content = block.get('text', '')

                    if text_content:
                        has_processed_content = True

                        # Close reasoning session if switching to text
                        if reasoning_state.is_active:
                            msg_id = reasoning_state.end_reasoning()

                            # Emit II-Agent format thinking stop
                            if adapter and adapter.thinking_active:
                                yield adapter.thinking_stop()

                            # Emit AG-UI format for backward compatibility
                            yield _make_event("reasoning_message_end", {
                                "messageId": msg_id,
                            })
                            yield _make_event("reasoning_end", {
                                "messageId": msg_id,
                            })

                        # Emit II-Agent format content events
                        if adapter:
                            if not adapter.content_started:
                                yield adapter.content_start()
                            yield adapter.content_delta(text_content)

                        # Emit text message chunk (AG-UI format)
                        event_stream_message["content"] = text_content
                        yield _make_event("message", event_stream_message)
        
        # Fallback for simple string content (no content_blocks)
        if not has_processed_content and isinstance(message_chunk.content, str) and message_chunk.content:
            # Close reasoning if active
            if reasoning_state.is_active:
                msg_id = reasoning_state.end_reasoning()

                # Emit II-Agent format thinking stop
                if adapter and adapter.thinking_active:
                    yield adapter.thinking_stop()

                # Emit AG-UI format for backward compatibility
                yield _make_event("reasoning_message_end", {
                    "messageId": msg_id,
                })
                yield _make_event("reasoning_end", {
                    "messageId": msg_id,
                })

            # Emit II-Agent format content events
            if adapter:
                if not adapter.content_started:
                    yield adapter.content_start()
                yield adapter.content_delta(message_chunk.content)

            # Emit AG-UI format
            event_stream_message["content"] = message_chunk.content
            yield _make_event("message", event_stream_message)

        # Fallback for list content (content as list of dicts, not using content_blocks attr)
        elif not has_processed_content and isinstance(message_chunk.content, list):
            for content_item in message_chunk.content:
                if isinstance(content_item, dict):
                    item_type = content_item.get('type', '')

                    # Handle reasoning blocks in list content
                    if item_type == 'reasoning':
                        reasoning_text = content_item.get('reasoning') or content_item.get('thinking') or content_item.get('text', '')
                        if reasoning_text:
                            has_processed_content = True
                            # Start reasoning session if not already active
                            if not reasoning_state.is_active:
                                msg_id = reasoning_state.start_reasoning()
                                if adapter and not adapter.thinking_active:
                                    yield adapter.thinking_start()
                                yield _make_event("reasoning_start", {"messageId": msg_id})
                                yield _make_event("reasoning_message_start", {"messageId": msg_id, "role": "assistant"})

                            # Emit II-Agent format thinking delta
                            if adapter:
                                yield adapter.thinking_delta(reasoning_text)

                            # Stream reasoning content (AG-UI format)
                            yield _make_event("reasoning_message_content", {
                                "messageId": reasoning_state.message_id,
                                "delta": reasoning_text,
                            })

                    elif item_type == 'text':
                        text_content = content_item.get('text', '')
                        if text_content:
                            # Close reasoning if active
                            if reasoning_state.is_active:
                                msg_id = reasoning_state.end_reasoning()
                                if adapter and adapter.thinking_active:
                                    yield adapter.thinking_stop()
                                yield _make_event("reasoning_message_end", {"messageId": msg_id})
                                yield _make_event("reasoning_end", {"messageId": msg_id})

                            # Emit II-Agent format content events
                            if adapter:
                                if not adapter.content_started:
                                    yield adapter.content_start()
                                yield adapter.content_delta(text_content)

                            # Emit AG-UI format
                            event_stream_message["content"] = text_content
                            yield _make_event("message", event_stream_message)
                elif isinstance(content_item, str) and content_item:
                    # Content item is a plain string
                    if adapter:
                        if not adapter.content_started:
                            yield adapter.content_start()
                        yield adapter.content_delta(content_item)
                    event_stream_message["content"] = content_item
                    yield _make_event("message", event_stream_message)
        
        # Handle tool calls
        # Filter out continuation/delta chunks (empty name = streaming arg delta, not a new tool call)
        # With astream_events(), each streaming chunk may have tool_calls with name='' and id=None
        real_tool_calls = [tc for tc in (message_chunk.tool_calls or []) if tc.get('name')]
        if real_tool_calls:
            safe_tool_names = [sanitize_tool_name(tc.get('name', 'unknown')) for tc in real_tool_calls]
            logger.debug(f"[{safe_thread_id}] AIMessageChunk has complete tool_calls: {safe_tool_names}")
            event_stream_message["tool_calls"] = real_tool_calls

            processed_chunks = _process_tool_call_chunks(message_chunk.tool_call_chunks)
            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks

            # Emit AG-UI compatible events for each tool call using structured ToolCall model
            for tc in real_tool_calls:
                tool_call = ToolCall.from_langchain(tc)

                # Emit II-Agent format tool_call events
                if adapter:
                    yield adapter.tool_call_start(tool_call.tool_call_id, tool_call.tool_name)
                    if tool_call.tool_input:
                        args_str = json.dumps(tool_call.tool_input) if isinstance(tool_call.tool_input, dict) else str(tool_call.tool_input)
                        yield adapter.tool_call_delta(tool_call.tool_call_id, args_str)
                        yield adapter.tool_call_stop(tool_call.tool_call_id, tool_call.tool_name, args_str)

                # AG-UI: TOOL_CALL_START
                start_event = tool_call.to_ag_ui_start_event()
                start_event["thread_id"] = thread_id
                start_event["parentMessageId"] = message_chunk.id
                yield _make_event("tool_call_start", start_event)

                # AG-UI: TOOL_CALL_ARGS (send full args)
                if tool_call.tool_input:
                    args_str = json.dumps(tool_call.tool_input) if isinstance(tool_call.tool_input, dict) else str(tool_call.tool_input)
                    yield _make_event("tool_call_args", tool_call.to_ag_ui_args_event(args_str))

                # AG-UI: TOOL_CALL_END
                yield _make_event("tool_call_end", tool_call.to_ag_ui_end_event())

            # Legacy event for backwards compatibility
            yield _make_event("tool_calls", event_stream_message)
            
        elif message_chunk.tool_call_chunks:
            processed_chunks = _process_tool_call_chunks(message_chunk.tool_call_chunks)

            if processed_chunks:
                event_stream_message["tool_call_chunks"] = processed_chunks
                
                # Emit AG-UI compatible events for streaming chunks
                for chunk in processed_chunks:
                    chunk_id = chunk.get("id", "")
                    chunk_name = chunk.get("name", "")
                    chunk_args = chunk.get("args", "")
                    
                    # If we have a name, this is a start event
                    if chunk_name:
                        yield _make_event("tool_call_start", {
                            "toolCallId": chunk_id,
                            "toolCallName": chunk_name,
                            "thread_id": thread_id,
                        })
                    
                    # If we have args, emit as delta
                    if chunk_args:
                        yield _make_event("tool_call_args", {
                            "toolCallId": chunk_id,
                            "delta": chunk_args,
                        })

            # Legacy event for backwards compatibility
            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            yield _make_event("message_chunk", event_stream_message)


async def _stream_graph_events(
    graph_instance: Any,
    workflow_input: dict,
    workflow_config: dict,
    thread_id: str,
    adapter: Optional[IIAgentSSEAdapter] = None,
    user_id: Optional[str] = None,
    db: Optional[Any] = None,
):
    """
    Stream events from the graph and process them.

    Maintains reasoning state across message chunks for proper AG-UI Protocol
    reasoning event lifecycle (start -> content -> end).

    Emits both AG-UI Protocol events (for backward compatibility) and
    II-Agent format events (via adapter) for frontend compatibility.
    """
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(f"[{safe_thread_id}] Starting graph event stream with agent nodes")
    event_count = 0

    # Track reasoning state across message chunks (using structured ReasoningState)
    reasoning_state = ReasoningState()

    try:
        async for event in graph_instance.astream_events(
            workflow_input,
            config=workflow_config,
            version="v2",
        ):
            event_type = event.get("event")
            metadata = event.get("metadata", {})

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and isinstance(chunk, AIMessageChunk):
                    langgraph_node = metadata.get("langgraph_node", "unknown")
                    agent_tuple = (langgraph_node,)
                    event_count += 1
                    async for sse_event in _process_message_chunk(
                        chunk, metadata, thread_id, agent_tuple, reasoning_state, adapter, user_id, db
                    ):
                        yield sse_event

            elif event_type == "on_tool_end":
                output = event.get("data", {}).get("output")
                if output and isinstance(output, ToolMessage):
                    langgraph_node = metadata.get("langgraph_node", "unknown")
                    agent_tuple = (langgraph_node,)
                    event_count += 1
                    async for sse_event in _process_message_chunk(
                        output, metadata, thread_id, agent_tuple, reasoning_state, adapter, user_id, db
                    ):
                        yield sse_event

            elif event_type == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict) and "__interrupt__" in output:
                    yield _create_interrupt_event(thread_id, output)
                    event_count += 1

        # Close reasoning if still active at the end of the stream
        if reasoning_state.is_active:
            msg_id = reasoning_state.end_reasoning()

            # Emit II-Agent format thinking stop event
            if adapter and adapter.thinking_active:
                yield adapter.thinking_stop()

            # Also emit AG-UI format for backward compatibility
            yield _make_event("reasoning_message_end", {
                "messageId": msg_id,
            })
            yield _make_event("reasoning_end", {
                "messageId": msg_id,
            })

        logger.debug(f"[{safe_thread_id}] Graph event stream completed. Total events: {event_count}")
    except asyncio.CancelledError:
        logger.info(f"[{safe_thread_id}] Graph event stream cancelled by user after {event_count} events")
        raise
    except Exception as e:
        logger.exception(f"[{safe_thread_id}] Error during graph execution")
        if adapter:
            yield adapter.error("Error during graph execution", "graph_error")
        else:
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
    max_search_results: int,
    mcp_settings: dict,
    enable_background_investigation: bool,
    enable_web_search: bool,
    user_id: str,
    locale: str = "en-US",
    model_id: Optional[str] = None,
    file_ids: Optional[List[str]] = None,
    save_messages: bool = True,
):
    """
    Async generator for streaming chat responses.

    This is a simple chat endpoint that processes user messages through the
    LangGraph agent workflow and yields Server-Sent Events (SSE) for real-time
    streaming. No sandbox integration - just direct graph execution.

    Emits II-Agent Frontend compatible events:
    - session: On stream start
    - content: Text streaming (start/delta/stop)
    - thinking: Reasoning/thinking blocks
    - tool_call: Tool execution lifecycle (start/delta/stop)
    - tool_result: Tool outputs
    - usage: Token usage statistics
    - complete: Stream completion
    - error: Error events

    Also maintains AG-UI Protocol compatibility for backward compatibility.
    """
    safe_thread_id = sanitize_thread_id(thread_id)
    logger.debug(
        f"[{safe_thread_id}] _astream_workflow_generator starting: "
        f"messages_count={len(messages)}"
    )

    # Create II-Agent event adapter for frontend compatibility
    adapter = create_sse_adapter(session_id=thread_id, model_id=model_id)

    # --- Save user message to DB (before streaming) ---
    session_name = None
    if save_messages:
        try:
            # Extract user text from messages
            user_text = ""
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_text = msg.get("content", "")
                    break

            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, thread_id)
                if session:
                    # Save user message
                    await chat_event_dao.create_user_message(
                        db=db,
                        session_id=session.id,
                        text=user_text,
                        file_ids=file_ids,
                    )
                    # Update session name from first message if not set
                    if not session.name and user_text:
                        session_name = user_text[:50] + ("..." if len(user_text) > 50 else "")
                        await chat_session_dao.update_name(db, session.id, session_name)
                    else:
                        session_name = session.name
                    # Increment message count
                    await chat_session_dao.increment_message_count(db, session.id)
                    await db.commit()
        except Exception as e:
            logger.warning(f"[{safe_thread_id}] Failed to save user message: {e}")

    # Emit session event at stream start (II-Agent format)
    yield adapter.session_event(is_new=True, name=session_name)

    # Process initial messages for AG-UI events
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            _process_initial_messages(message, thread_id)

    # Build workflow input - simple format for the graph
    workflow_input = {
        "messages": messages,
        "locale": locale,
        "enable_background_investigation": enable_background_investigation,
    }

    # Build workflow config
    workflow_config = {
        "configurable": {
            "thread_id": thread_id,
            "resources": resources,
            "max_search_results": max_search_results,
            "mcp_settings": mcp_settings,
            "enable_web_search": enable_web_search,
            "enable_added_tools": False,  # Chat mode: no research tools (paper_search, arxiv, etc.)
        },
        "recursion_limit": _get_recursion_limit(),
    }

    # Track finish reason for complete event
    finish_reason = "end_turn"
    # Accumulate agent response text for persistence
    accumulated_agent_text = []

    # Use centralized PostgreSQL checkpointer (shared connection pool)
    logger.info(f"[{safe_thread_id}] Using PostgreSQL checkpointer")
    streaming_completed = False
    try:
        async with async_db_session() as db:
            async with checkpointer_manager.get_graph_with_checkpointer(_graph, thread_id) as configured_graph:
                async for event in _stream_graph_events(
                    configured_graph, workflow_input, workflow_config, thread_id, adapter, user_id, db
                ):
                    yield event
                    # Accumulate text content deltas for agent message persistence
                    if save_messages and isinstance(event, str):
                        try:
                            # Parse SSE event to extract content deltas
                            event_type_str = None
                            data = None
                            data_str = None
                            for line in event.strip().split('\n'):
                                if line.startswith('event:'):
                                    event_type_str = line[6:].strip()
                                elif line.startswith('data:'):
                                    data_str = line[5:].strip()
                                    if data_str:
                                        data = json.loads(data_str)

                            # Log event types for debugging (only first occurrence of each type)
                            if event_type_str:
                                logger.debug(f"[{safe_thread_id}] SSE event type: {event_type_str}")

                            # Capture text content ONLY from II-Agent "content" deltas.
                            # IMPORTANT: Each text token produces 3 SSE events:
                            #   1. "content" (II-Agent format via adapter.content_delta)
                            #   2. "message" (AG-UI format via _make_event)
                            #   3. "message_chunk" (legacy format, final else branch)
                            # We must only accumulate from ONE source to avoid
                            # tripling the saved message text.
                            if event_type_str == "content" and data and data.get("status") == "delta" and "delta" in data:
                                text_delta = data["delta"]
                                if text_delta:
                                    accumulated_agent_text.append(text_delta)
                                    logger.debug(f"[{safe_thread_id}] Captured content delta: {len(text_delta)} chars")
                        except json.JSONDecodeError as jde:
                            logger.debug(f"[{safe_thread_id}] JSON decode error for event: {jde}, data_str={data_str[:100] if data_str else 'None'}")
                        except Exception as parse_err:
                            logger.debug(f"[{safe_thread_id}] Event parse error: {parse_err}")
                    # Check for finish reason in event
                    if "finish_reason" in str(event):
                        if "interrupt" in str(event):
                            finish_reason = "interrupt"
                        elif "tool" in str(event):
                            finish_reason = "tool_use"

        # Mark streaming as successfully completed
        streaming_completed = True

        # --- Save agent response BEFORE the complete event ---
        # This ensures the save happens for normal completions
        if save_messages:
            try:
                agent_response_text = "".join(accumulated_agent_text)
                if agent_response_text:
                    logger.info(f"[{safe_thread_id}] Pre-complete save: {len(agent_response_text)} chars accumulated")
                    async with async_db_session() as save_db:
                        session = await chat_session_dao.get_by_uuid(save_db, thread_id)
                        if session:
                            await chat_event_dao.create_agent_message(
                                db=save_db,
                                session_id=session.id,
                                text=agent_response_text,
                                model_name=model_id or "default",
                            )
                            await chat_session_dao.increment_message_count(save_db, session.id)
                            await save_db.commit()
                            logger.info(f"[{safe_thread_id}] Agent response saved in pre-complete")
                            # Mark as already saved so finally block doesn't double-save
                            accumulated_agent_text.clear()
            except Exception as e:
                logger.warning(f"[{safe_thread_id}] Pre-complete save failed: {e}")

        # Emit complete event at stream end (II-Agent format)
        yield adapter.complete(finish_reason=finish_reason)

    except Exception as e:
        logger.exception(f"[{safe_thread_id}] Error in stream generator")
        yield adapter.error(str(e), "stream_error")
    finally:
        # --- Save agent response to DB (in finally block as backup) ---
        # This only runs if pre-complete save didn't happen (e.g., client disconnect)
        if save_messages:
            try:
                agent_response_text = "".join(accumulated_agent_text)
                if not agent_response_text:
                    if not streaming_completed:
                        # Only save placeholder if streaming didn't complete (interrupted)
                        agent_response_text = "[Agent response - interrupted before completion]"
                        logger.info(f"[{safe_thread_id}] Streaming interrupted, saving placeholder")
                    else:
                        # Streaming completed normally but no text - pre-complete save already handled it
                        logger.debug(f"[{safe_thread_id}] No text in finally block, pre-complete save likely handled it")
                        agent_response_text = None

                # Only proceed with save if there's text to save
                if agent_response_text:
                    logger.info(f"[{safe_thread_id}] Finally block saving: {len(agent_response_text)} chars")

                    # Use shield to protect the save operation from cancellation
                    async def _save_agent_response():
                        async with async_db_session() as db:
                            session = await chat_session_dao.get_by_uuid(db, thread_id)
                            if session:
                                await chat_event_dao.create_agent_message(
                                    db=db,
                                    session_id=session.id,
                                    text=agent_response_text,
                                    model_name=model_id or "default",
                                )
                                await chat_session_dao.increment_message_count(db, session.id)
                                await db.commit()
                                logger.info(f"[{safe_thread_id}] Agent response saved in finally block")
                            else:
                                logger.warning(f"[{safe_thread_id}] Session not found for agent response save")

                    await asyncio.shield(_save_agent_response())
            except asyncio.CancelledError:
                # Even if cancelled, try to save via a fire-and-forget task
                if agent_response_text:
                    logger.warning(f"[{safe_thread_id}] Agent response save cancelled, scheduling background save")
                    asyncio.create_task(_background_save_agent_response(
                        thread_id, agent_response_text, model_id or "default"
                    ))
            except Exception as e:
                logger.warning(f"[{safe_thread_id}] Failed to save agent response: {e}")


async def _background_save_agent_response(thread_id: str, text: str, model_name: str):
    """Background task to save agent response if the main save was cancelled."""
    try:
        async with async_db_session() as db:
            session = await chat_session_dao.get_by_uuid(db, thread_id)
            if session:
                await chat_event_dao.create_agent_message(
                    db=db,
                    session_id=session.id,
                    text=text,
                    model_name=model_name,
                )
                await chat_session_dao.increment_message_count(db, session.id)
                await db.commit()
                logger.info(f"[{thread_id}] Agent response saved via background task")
    except Exception as e:
        logger.error(f"[{thread_id}] Background save failed: {e}")


def _make_event(event_type: str, data: dict) -> str:
    """Create a Server-Sent Event (SSE) formatted string with safe serialization."""
    if data.get("content") == "":
        data.pop("content", None)

    json_data = safe_json_serialize(data)
    finish_reason = data.get("finish_reason", "")
    chat_stream_message(
        data.get("thread_id", ""),
        f"event: {event_type}\ndata: {json_data}\n\n",
        finish_reason,
    )
    return f"event: {event_type}\ndata: {json_data}\n\n"


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

    This endpoint processes user messages through the LangGraph agent workflow
    and streams responses in real-time using Server-Sent Events (SSE).
    
    This is a simple chat endpoint without sandbox integration. For sandbox
    features (code execution, file system, etc.), use /agent/agent/stream instead.

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

    # Resolve thread ID: prefer session_id from frontend, fallback to thread_id
    thread_id = request.session_id or request.thread_id
    if thread_id == "__default__" or not thread_id:
        thread_id = str(uuid4())

    # Persist session to database BEFORE streaming starts
    # This ensures the session appears in the sidebar immediately when frontend
    # invalidates cache and refetches /agent/chat-sessions
    try:
        async with async_db_session() as db:
            session, created = await chat_session_service.get_or_create(
                db=db,
                session_uuid=thread_id,
                user_id=int(user_id),
                agent_type="chat"
            )
            await db.commit()
            if created:
                logger.info(f"Created new chat session {thread_id} for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to persist chat session {thread_id}: {e}")
        # Continue anyway - the session will be created on subsequent requests

    # Get model_id from request (optional)
    model_id = request.model_id

    # Determine web search setting from tools or explicit setting
    enable_web_search = request.enable_web_search
    if request.tools:
        enable_web_search = request.tools.web_search

    # Convert messages to dict format
    messages = [msg.model_dump() for msg in request.messages]
    mcp_settings_dict = request.mcp_settings.model_dump() if request.mcp_settings else {}

    logger.info(f"Chat stream starting: thread_id={thread_id}, model_id={model_id}, user_id={user_id}")

    return StreamingResponse(
        _astream_workflow_generator(
            messages=messages,
            thread_id=thread_id,
            resources=request.resources,
            max_search_results=request.max_search_results,
            mcp_settings=mcp_settings_dict if mcp_enabled else {},
            enable_background_investigation=request.enable_background_investigation,
            enable_web_search=enable_web_search,
            locale=request.locale,
            model_id=model_id,
            user_id=user_id,
            file_ids=request.file_ids,
            save_messages=True,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )