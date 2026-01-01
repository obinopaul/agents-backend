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
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, BaseMessage
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_decode
from backend.core.conf import settings
from backend.src.graph.checkpointer import checkpointer_manager
from backend.src.rag.retriever import Resource
from backend.src.services.session_sandbox_manager import SessionSandboxManager
from backend.database.db import CurrentSession
from backend.src.services.slides.slide_subscriber import slide_subscriber
from backend.core.conf import settings

# Import structured models for AG-UI Protocol
from backend.app.agent.models import (
    AgentMessage,
    ReasoningState,
    ToolCall,
    ToolCallState,
    make_ag_ui_event,
    extract_reasoning_from_content_blocks,
    # HITL models
    HITLRequest,
    HITLState,
    create_hitl_interrupt_event,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Robust JSON Serialization for SSE Events
# =============================================================================
# This handles non-serializable objects like LangChain's ToolRuntime, Pydantic
# models, bytes, sets, and other complex types that may appear in tool events.

def _make_serializable(obj: Any, seen: set = None) -> Any:
    """Recursively convert any object to a JSON-serializable form.
    
    This is a defensive serializer that NEVER raises exceptions.
    It handles:
    - Pydantic models (v1 and v2)
    - LangChain objects (ToolRuntime, BaseTool, etc.)
    - Bytes, sets, tuples
    - Circular references
    - Any edge case with graceful fallback
    
    Args:
        obj: Any Python object
        seen: Set of id() values to detect circular references
        
    Returns:
        JSON-serializable representation
    """
    if seen is None:
        seen = set()
    
    # Handle None and primitives (most common case, fast path)
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float, str)):
        return obj
    
    # Detect circular references
    obj_id = id(obj)
    if obj_id in seen:
        return f"<circular ref: {type(obj).__name__}>"
    
    # Handle common iterables
    if isinstance(obj, (list, tuple)):
        seen.add(obj_id)
        return [_make_serializable(item, seen) for item in obj]
    
    if isinstance(obj, set):
        seen.add(obj_id)
        return [_make_serializable(item, seen) for item in obj]
    
    if isinstance(obj, dict):
        seen.add(obj_id)
        result = {}
        for k, v in obj.items():
            # Skip private/internal keys
            str_key = str(k) if not isinstance(k, str) else k
            if str_key.startswith('_'):
                continue
            result[str_key] = _make_serializable(v, seen)
        return result
    
    # Handle bytes
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8', errors='replace')
        except Exception:
            return f"<bytes: {len(obj)} bytes>"
    
    # Handle Pydantic v2 models (most common in FastAPI)
    if hasattr(obj, 'model_dump'):
        try:
            seen.add(obj_id)
            return _make_serializable(obj.model_dump(), seen)
        except Exception:
            pass
    
    # Handle Pydantic v1 models
    if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
        try:
            seen.add(obj_id)
            return _make_serializable(obj.dict(), seen)
        except Exception:
            pass
    
    # Handle LangChain messages and tools with content attribute
    if hasattr(obj, 'content'):
        try:
            return _make_serializable(obj.content, seen)
        except Exception:
            pass
    
    # Handle objects with __dict__ (general Python objects)
    if hasattr(obj, '__dict__'):
        try:
            seen.add(obj_id)
            # Filter out private attrs and callables
            public_attrs = {
                k: v for k, v in obj.__dict__.items()
                if not k.startswith('_') and not callable(v)
            }
            if public_attrs:
                return _make_serializable(public_attrs, seen)
        except Exception:
            pass
    
    # Handle callables/functions
    if callable(obj):
        return f"<{type(obj).__name__}>"
    
    # Ultimate fallback - type name (never raises)
    return f"<{type(obj).__name__}>"


def _safe_json_serialize(data: Any) -> str:
    """Safely serialize any data to JSON string.
    
    This function NEVER raises an exception. It handles all edge cases
    including ToolRuntime, complex LangChain objects, and circular references.
    
    Args:
        data: Any Python object or data structure
        
    Returns:
        JSON string representation (always succeeds)
    """
    try:
        # First pass: make everything serializable
        serializable = _make_serializable(data)
        # Second pass: dump to JSON
        return json.dumps(serializable, ensure_ascii=False)
    except Exception as e:
        # Absolute fallback - should never reach here
        logger.warning(f"JSON serialization fallback triggered: {e}")
        return json.dumps({"error": f"Serialization fallback: {str(data)[:200]}"})


# =============================================================================
# Module Registry - Lazy Loading Agent Modules
# =============================================================================

class AgentModuleType(str, Enum):
    """Available agent modules.
    
    Each module represents a different LangGraph agent workflow:
    - GENERAL: Default MCP-enabled agent with sandbox tools
    - RESEARCH: Deep research multi-agent workflow
    - PODCAST: Podcast generation (not yet implemented)
    - PPT: PowerPoint generation (not yet implemented)
    - PROSE: Prose writing operations (not yet implemented)
    """
    GENERAL = "general"       # Default MCP-enabled agent
    RESEARCH = "research"     # Deep research multi-agent workflow  
    PODCAST = "podcast"       # Podcast generation (stub)
    PPT = "ppt"               # PowerPoint generation (stub)
    PROSE = "prose"           # Prose writing (stub)


@dataclass
class ModuleInfo:
    """Information about an agent module."""
    name: str
    import_path: str
    loader: Callable[[], Any]
    is_implemented: bool = True
    description: str = ""


class ModuleRegistry:
    """
    Registry for agent modules with lazy loading.
    
    Modules are only imported when first requested, reducing startup time.
    Each module exports a compiled LangGraph graph that can be used with
    the checkpointer_manager for state persistence.
    """
    
    _modules: Dict[str, ModuleInfo] = {}
    _loaded_graphs: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, module_type: AgentModuleType, info: ModuleInfo):
        """Register a module with its loader."""
        cls._modules[module_type.value] = info
    
    @classmethod
    def get_graph(cls, module_type: AgentModuleType):
        """Get a module's compiled graph (lazy loaded)."""
        name = module_type.value
        
        if name not in cls._modules:
            raise ValueError(f"Unknown module: {name}")
        
        info = cls._modules[name]
        
        # Check if module is implemented
        if not info.is_implemented:
            raise NotImplementedError(
                f"Module '{name}' is not yet implemented. "
                f"Available modules: {cls.get_available_modules()}"
            )
        
        # Lazy load the graph
        if name not in cls._loaded_graphs:
            logger.info(f"Loading module graph: {name}")
            cls._loaded_graphs[name] = info.loader()
            
        return cls._loaded_graphs[name]
    
    @classmethod
    def get_available_modules(cls) -> List[str]:
        """Get list of implemented module names."""
        return [name for name, info in cls._modules.items() if info.is_implemented]
    
    @classmethod
    def get_module_info(cls, module_type: AgentModuleType) -> Optional[ModuleInfo]:
        """Get info about a module."""
        return cls._modules.get(module_type.value)


# Module loader functions (lazy import)
def _load_general_graph():
    """Load the general/default MCP-enabled agent graph."""
    from backend.src.graph.builder import graph
    return graph

def _load_research_graph():
    """Load the deep research multi-agent workflow graph."""
    from backend.src.module.research.graph.builder import graph
    return graph

def _load_podcast_graph():
    """Load the podcast generation graph (stub)."""
    from backend.src.module.podcast import graph
    return graph

def _load_ppt_graph():
    """Load the PPT generation graph (stub)."""
    from backend.src.module.ppt import graph
    return graph

def _load_prose_graph():
    """Load the prose writing graph (stub)."""
    from backend.src.module.prose import graph
    return graph


# Register all modules
ModuleRegistry.register(AgentModuleType.GENERAL, ModuleInfo(
    name="general",
    import_path="backend.src.graph.builder",
    loader=_load_general_graph,
    is_implemented=True,
    description="MCP-enabled agent with sandbox tools for general coding tasks",
))

ModuleRegistry.register(AgentModuleType.RESEARCH, ModuleInfo(
    name="research",
    import_path="backend.src.module.research.graph.builder",
    loader=_load_research_graph,
    is_implemented=True,
    description="Multi-agent deep research workflow with coordinator, planner, researcher, and reporter",
))

ModuleRegistry.register(AgentModuleType.PODCAST, ModuleInfo(
    name="podcast",
    import_path="backend.src.module.podcast",
    loader=_load_podcast_graph,
    is_implemented=False,
    description="AI-powered podcast generation from text content",
))

ModuleRegistry.register(AgentModuleType.PPT, ModuleInfo(
    name="ppt",
    import_path="backend.src.module.ppt",
    loader=_load_ppt_graph,
    is_implemented=False,
    description="PowerPoint presentation generation using Marp CLI",
))

ModuleRegistry.register(AgentModuleType.PROSE, ModuleInfo(
    name="prose",
    import_path="backend.src.module.prose",
    loader=_load_prose_graph,
    is_implemented=False,
    description="Prose writing operations: continue, improve, shorten, lengthen, fix",
))


# =============================================================================
# Request/Response Models
# =============================================================================

# AgentMessage imported from backend.app.agent.models


class AgentRequest(BaseModel):
    """Request model for the agent streaming endpoint."""
    
    module: AgentModuleType = Field(
        default=AgentModuleType.GENERAL,
        description="Agent module to use. Default 'general' uses MCP sandbox tools."
    )
    messages: List[AgentMessage] = Field(..., description="List of conversation messages")
    thread_id: str = Field(default="__default__", description="Thread ID for conversation continuity and sandbox session")
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
    """Create a Server-Sent Event (SSE) formatted string.
    
    Uses _safe_json_serialize to handle non-serializable objects
    like ToolRuntime, Pydantic models, etc.
    """
    json_data = _safe_json_serialize(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _get_recursion_limit() -> int:
    """Get recursion limit from settings with fallback."""
    return settings.AGENT_RECURSION_LIMIT if settings.AGENT_RECURSION_LIMIT > 0 else 25


# =============================================================================
# Stream Generator
# =============================================================================

async def _agent_stream_generator(
    graph,  # The compiled LangGraph to use
    module_name: str,  # Module name for logging/events
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
    db_session: CurrentSession,  # Required for slide subscriber
):
    """
    Async generator for streaming agent workflow events.
    
    This generator:
    1. Sends "processing" status immediately
    2. Creates/reuses sandbox (lazy initialization)
    3. Sends "sandbox_ready" status
    4. Runs agent workflow
    5. Streams responses with AG-UI Protocol support:
       - Reasoning events (auto-detected from model output)
       - Multimodal message conversion
       - Tool call lifecycle events
    """
    # Track reasoning state for AG-UI Protocol (using structured ReasoningState)
    reasoning_state = ReasoningState()
    
    try:
        # STEP 1: Send immediate feedback
        yield _make_event("status", {
            "type": "processing",
            "message": f"Processing with {module_name} module...",
            "module": module_name,
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
        mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
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
            
            # Explicitly register tools with the MCP server
            # Required because the server uses on-demand registration optimizations
            try:
                async with httpx.AsyncClient() as client:
                    # 1. Set credentials
                    # Use a dummy key for now, or extract from user profile if needed
                    # The session_id matches the thread_id for consistency
                    cred_payload = {
                        "user_api_key": "sandbox-key", 
                        "session_id": thread_id
                    }
                    await client.post(f"{mcp_url}/credential", json=cred_payload)
                    
                    # 2. Set tool server URL and trigger registration
                    # Tools communicate internally on localhost:6060
                    # Using 127.0.0.1 to be safer inside container
                    url_payload = {"tool_server_url": "http://127.0.0.1:6060"}
                    logger.info(f"[DEBUG_SLIDES] Registering tools at {mcp_url}/tool-server-url with {url_payload}")
                    
                    reg_resp = await client.post(f"{mcp_url}/tool-server-url", json=url_payload)
                    
                    if reg_resp.status_code == 200:
                        logger.info("[DEBUG_SLIDES] Agent stream: Sandbox tools registered successfully")
                        yield _make_event("status", {
                            "type": "tool_registration",
                            "message": "Slides tools registered",
                            "status": "success"
                        })
                        
                        # [DEBUG PROBE] Immediately check if we can see the tools
                        try:
                            from langchain_mcp_adapters.client import MultiServerMCPClient
                            logger.info("[DEBUG_SLIDES] PROBE: Checking if tools are visible via MCP client...")
                            
                            probe_servers = {
                                "probe": {
                                    "transport": "http",  # Tool Server uses HTTP
                                    "url": f"{mcp_url}/mcp",  # Endpoint is /mcp
                                }
                            }
                            probe_client = MultiServerMCPClient(probe_servers)
                            # Give it a tiny moment?
                            await asyncio.sleep(1)
                            probe_tools = await probe_client.get_tools()
                            
                            probe_names = [t.name for t in probe_tools]
                            logger.info(f"[DEBUG_SLIDES] PROBE: Found {len(probe_names)} tools: {probe_names}")
                            
                            yield _make_event("status", {
                                "type": "tool_probe",
                                "message": f"Probe found {len(probe_names)} tools",
                                "tools": probe_names
                            })
                            
                            # Clean up probe
                            # probe_client doesn't have explicit close? usually context manager, but MultiServerMCPClient isn't one.
                            # We'll just leave it be, it's ephemeral.
                            
                        except Exception as probe_error:
                            logger.error(f"[DEBUG_SLIDES] PROBE FAILED: {probe_error}")
                            yield _make_event("warning", {
                                "type": "tool_probe_error",
                                "message": f"Probe failed: {str(probe_error)}"
                            })

                    else:
                        error_msg = f"Tool reg failed: {reg_resp.status_code} {reg_resp.text}"
                        logger.error(f"[DEBUG_SLIDES] {error_msg}")
                        yield _make_event("warning", {
                            "type": "tool_registration_failed",
                            "message": error_msg
                        })
                        
            except Exception as reg_error:
                error_msg = f"Tool reg error: {str(reg_error)}"
                logger.error(f"[DEBUG_SLIDES] {error_msg}")
                yield _make_event("warning", {
                    "type": "tool_registration_error",
                    "message": error_msg
                })
        
        
        # STEP 4: MCP URL already obtained above, use it for workflow
        
        # STEP 5: Build workflow input
        # Messages are already in LangChain v1 format (string or list of content blocks)
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
        
        # Use the centralized PostgreSQL checkpointer with the provided graph
        async with checkpointer_manager.get_graph_with_checkpointer(graph, thread_id) as configured_graph:
            async for event in configured_graph.astream_events(
                workflow_input,
                config=workflow_config,
                version="v2",
            ):
                event_type = event.get("event", "")
                
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if isinstance(chunk, AIMessageChunk):
                        # Process content blocks - LangChain standardizes reasoning/text/etc.
                        # content_blocks provides unified format across all providers
                        if hasattr(chunk, 'content_blocks') and chunk.content_blocks:
                            for block in chunk.content_blocks:
                                if not isinstance(block, dict):
                                    continue
                                
                                block_type = block.get('type', '')
                                
                                # Handle reasoning blocks (auto-standardized by LangChain)
                                if block_type == 'reasoning':
                                    reasoning_text = block.get('reasoning') or block.get('thinking') or block.get('text', '')
                                    
                                    if reasoning_text:
                                        # Start reasoning session if not already active
                                        if not reasoning_state.is_active:
                                            msg_id = reasoning_state.start_reasoning()
                                            
                                            yield _make_event("reasoning_start", {
                                                "messageId": msg_id,
                                            })
                                            yield _make_event("reasoning_message_start", {
                                                "messageId": msg_id,
                                                "role": "assistant",
                                            })
                                        
                                        # Stream reasoning content
                                        yield _make_event("reasoning_message_content", {
                                            "messageId": reasoning_state.message_id,
                                            "delta": reasoning_text,
                                        })
                                
                                # Handle text blocks
                                elif block_type == 'text':
                                    text_content = block.get('text', '')
                                    
                                    if text_content:
                                        # Close reasoning session if switching to text
                                        if reasoning_state.is_active:
                                            msg_id = reasoning_state.end_reasoning()
                                            yield _make_event("reasoning_message_end", {
                                                "messageId": msg_id,
                                            })
                                            yield _make_event("reasoning_end", {
                                                "messageId": msg_id,
                                            })
                                        
                                        # Emit text message chunk
                                        yield _make_event("message", {
                                            "type": "chunk",
                                            "content": text_content,
                                            "thread_id": thread_id,
                                        })
                        
                        # Fallback for simple string content (no content_blocks)
                        elif isinstance(chunk.content, str) and chunk.content:
                            # Close reasoning if active
                            if reasoning_state.is_active:
                                msg_id = reasoning_state.end_reasoning()
                                yield _make_event("reasoning_message_end", {
                                    "messageId": msg_id,
                                })
                                yield _make_event("reasoning_end", {
                                    "messageId": msg_id,
                                })
                            
                            yield _make_event("message", {
                                "type": "chunk",
                                "content": chunk.content,
                                "thread_id": thread_id,
                            })
                
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_run_id = event.get("run_id", str(uuid4()))
                    tool_input = event.get("data", {}).get("input", {})
                    
                    # Create structured ToolCall
                    tool_call = ToolCall(
                        tool_call_id=tool_run_id,
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    
                    # AG-UI Protocol: TOOL_CALL_START (using model method)
                    event_data = tool_call.to_ag_ui_start_event()
                    event_data["thread_id"] = thread_id
                    yield _make_event("tool_call_start", event_data)
                    
                    # AG-UI Protocol: TOOL_CALL_ARGS (send full args as single delta)
                    if tool_input:
                        # Use safe serializer to handle ToolRuntime and other complex types
                        args_str = _safe_json_serialize(tool_input)
                        yield _make_event("tool_call_args", tool_call.to_ag_ui_args_event(args_str))
                
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_run_id = event.get("run_id", str(uuid4()))
                    tool_output = event.get("data", {}).get("output", "")
                    
                    # AG-UI Protocol: TOOL_CALL_END
                    yield _make_event("tool_call_end", {
                        "toolCallId": tool_run_id,
                    })
                    
                    # Also emit tool result as tool message for conversation history
                    yield _make_event("tool_result", {
                        "role": "tool",
                        "content": str(tool_output) if tool_output else "",
                        "toolCallId": tool_run_id,
                        "toolName": tool_name,
                        "thread_id": thread_id,
                    })
                    
                    # Sync slide tool results to database (SlideWrite, SlideEdit, etc.)
                    # This happens asynchronously and doesn't block the stream significantly
                    try:
                        await slide_subscriber.on_tool_complete(
                            db_session=db_session,
                            tool_name=tool_name,
                            tool_input=event.get("data", {}).get("input", {}),
                            tool_result=tool_output,
                            thread_id=thread_id,
                        )
                    except Exception as e:
                        logger.error(f"Failed to sync slide tool result: {e}")
            
            # Check graph state for interrupts after streaming completes
            # LangGraph signals interrupts via __interrupt__ in the state
            try:
                state_snapshot = await configured_graph.aget_state(workflow_config)
                if state_snapshot and hasattr(state_snapshot, 'tasks'):
                    for task in state_snapshot.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            # Found an interrupt - emit HITL event
                            for interrupt_obj in task.interrupts:
                                interrupt_value = getattr(interrupt_obj, 'value', interrupt_obj)
                                yield create_hitl_interrupt_event(interrupt_value, thread_id)
                            # Don't emit completion if interrupted
                            return
            except Exception as state_error:
                logger.debug(f"Could not check state for interrupts: {state_error}")
        
        # Close reasoning if still active at the end
        if reasoning_state.is_active:
            msg_id = reasoning_state.end_reasoning()
            yield _make_event("reasoning_message_end", {
                "messageId": msg_id,
            })
            yield _make_event("reasoning_end", {
                "messageId": msg_id,
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
    description="Process user messages through an AI agent workflow with sandbox tools and stream responses. Supports multiple agent modules.",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming response with SSE events",
            "content": {"text/event-stream": {}},
        },
        400: {"description": "Bad request - Invalid module specified"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"},
        501: {"description": "Not implemented - Module not yet available"},
    },
    dependencies=[DependsJwtAuth],
)
async def agent_stream(
    request: AgentRequest, 
    http_request: Request,
    db: CurrentSession,
):
    """
    Stream agent responses with sandbox tool support.
    
    This endpoint:
    - Supports multiple agent modules via the 'module' parameter
    - Creates a sandbox lazily (only when needed)
    - Reuses sandboxes for the same thread_id
    - Streams responses in real-time using SSE
    - Supports multimodal input (images, audio, video, files)
    - Automatically emits reasoning events when model returns thinking content
    
    Available Modules:
    - general (default): MCP-enabled agent with sandbox tools
    - research: Deep research multi-agent workflow
    - podcast: Podcast generation (not yet implemented)
    - ppt: PowerPoint generation (not yet implemented)
    - prose: Prose writing (not yet implemented)
    
    Events emitted (AG-UI Protocol compatible):
    - status: Processing status updates (includes module name)
    - message: Agent response chunks
    - reasoning_*: Reasoning events (auto-detected)
    - tool_call_*: Tool execution events
    - tool_result: Tool output
    - error/warning: Error and warning events
    
    Authentication required via JWT token.
    """
    # Get current user ID from JWT token
    token = get_token(http_request)
    token_payload = jwt_decode(token)
    user_id = str(token_payload.id)
    
    # Generate thread_id if using default (thread_id is used for both conversation and sandbox)
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    
    # Create session sandbox manager (lazy - no sandbox yet)
    # Using thread_id for sandbox session to maintain consistency
    sandbox_manager = SessionSandboxManager(
        user_id=user_id,
        session_id=thread_id  # thread_id serves as session_id for sandbox
    )
    
    # Convert messages to dict format
    messages = [msg.model_dump() for msg in request.messages]
    
    # Get the module's graph from registry
    try:
        selected_graph = ModuleRegistry.get_graph(request.module)
        module_name = request.module.value
        logger.info(f"Agent stream: Using module '{module_name}' for thread {thread_id}")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return StreamingResponse(
        _agent_stream_generator(
            graph=selected_graph,
            module_name=module_name,
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
            db_session=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
