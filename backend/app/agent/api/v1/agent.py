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
import langchain
langchain.verbose = False
langchain.debug = False

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
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_decode
from backend.core.conf import settings
from backend.src.graph.checkpointer import checkpointer_manager
from backend.src.rag.retriever import Resource
from backend.src.services.sandbox_service import SandboxService
from backend.src.services.session_sandbox_manager import SessionSandboxManager
from backend.app.agent.service.chat_session_service import chat_session_service

from backend.src.config.skill_config import AgentCategory
from backend.database.db import CurrentSession, async_db_session
from backend.src.services.slides.slide_subscriber import slide_subscriber
from backend.src.services.user_message import user_message_subscriber
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

# Import II-Agent Event Adapter for frontend compatibility
from backend.app.agent.event_adapter import (
    IIAgentSSEAdapter,
    create_sse_adapter,
    humanize_tool_name,
)

from backend.app.agent.service.asset_service import process_and_stage_asset
import base64

# Import shared JSON serialization utilities
from backend.src.utils.json_utils import (
    make_serializable,
    safe_json_serialize,
)



logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Robust JSON Serialization for SSE Events
# =============================================================================
# This handles non-serializable objects like LangChain's ToolRuntime, Pydantic
# models, bytes, sets, and other complex types that may appear in tool events.
# 
# NOTE: These are local aliases to the shared json_utils functions for backward
# compatibility with any code that may be calling _make_serializable or
# _safe_json_serialize directly from this module.

# Re-export from json_utils for backward compatibility
_make_serializable = make_serializable
_safe_json_serialize = safe_json_serialize




# =============================================================================
# Module Registry - Lazy Loading Agent Modules
# =============================================================================

class AgentModuleType(str, Enum):
    """Available agent modules.
    
    Each module represents a different LangGraph agent workflow:
    - GENERAL: Default MCP-enabled agent with sandbox tools
    - DEEP_RESEARCH: Deep research multi-agent workflow
    - ACADEMIC: Academic research multi-agent workflow
    - DESIGN: Design multi-agent workflow
    - DEV: Software development multi-agent workflow
    - DATA_SCIENTIST: Data scientist multi-agent workflow
    - SLIDES: Slides multi-agent workflow
    - DOCUMENTS: LaTeX/documents multi-agent workflow
    """
    GENERAL = "general"       # Default MCP-enabled agent
    DEEP_RESEARCH = "deep_research"     # Deep research multi-agent workflow  
    ACADEMIC = "academic"       # Academic research multi-agent workflow
    DESIGN = "design"               # Design multi-agent workflow
    DEV = "dev"           # Software development multi-agent workflow
    DATA_SCIENTIST = "data_scientist"           # Data scientist multi-agent workflow
    SLIDES = "slides"           # Slides multi-agent workflow
    DOCUMENTS = "documents"     # LaTeX/documents multi-agent workflow
    QUANT = "quant"     # Tax/Financial multi-agent workflow
    EXCALIDRAW = "excalidraw"     # Excalidraw multi-agent workflow
    


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

def _load_quant_graph():
    """Load the quant multi-agent workflow graph."""
    from backend.src.module.quant.builder import graph
    return graph

def _load_excalidraw_graph():
    """Load the excalidraw multi-agent workflow graph."""
    from backend.src.module.excalidraw.builder import graph
    return graph

def _load_deep_research_graph():
    """Load the deep research multi-agent workflow graph."""
    from backend.src.module.deep_research.builder import graph
    return graph

def _load_academic_graph():
    """Load the academic research graph (stub)."""
    from backend.src.module.academic.builder import graph
    return graph

def _load_design_graph():
    """Load the design research graph (stub)."""
    from backend.src.module.design.builder import graph
    return graph

def _load_data_scientist_graph():
    """Load the data scientist research graph (stub)."""
    from backend.src.module.data_scientist.builder import graph
    return graph

def _load_dev_graph():
    """Load the software dev research graph (stub)."""
    from backend.src.module.dev.builder import graph
    return graph

def _load_slides_graph():
    """Load the slides generation graph (stub)."""
    from backend.src.module.slides.builder import graph
    return graph

def _load_documents_graph():
    """Load the documents generation graph (stub)."""
    from backend.src.module.documents.builder import graph
    return graph


# Register all modules
ModuleRegistry.register(AgentModuleType.GENERAL, ModuleInfo(
    name="general",
    import_path="backend.src.graph.builder",
    loader=_load_general_graph,
    is_implemented=True,
    description="MCP-enabled agent with sandbox tools for general coding tasks",
))

ModuleRegistry.register(AgentModuleType.DEEP_RESEARCH, ModuleInfo(
    name="deep_research",
    import_path="backend.src.module.deep_research.builder",
    loader=_load_deep_research_graph,
    is_implemented=True,
    description="Multi-agent deep research workflow",
))

ModuleRegistry.register(AgentModuleType.ACADEMIC, ModuleInfo(
    name="academic",
    import_path="backend.src.module.academic.builder",
    loader=_load_academic_graph,
    is_implemented=True,
    description="Multi-agent academic workflow",
))

ModuleRegistry.register(AgentModuleType.DESIGN, ModuleInfo(
    name="design",
    import_path="backend.src.module.design.builder",
    loader=_load_design_graph,
    is_implemented=True,
    description="Multi-agent design workflow",
))

ModuleRegistry.register(AgentModuleType.EXCALIDRAW, ModuleInfo(
    name="excalidraw",
    import_path="backend.src.module.excalidraw.builder",
    loader=_load_excalidraw_graph,
    is_implemented=True,
    description="Multi-agent excalidraw workflow",
))

ModuleRegistry.register(AgentModuleType.QUANT, ModuleInfo(
    name="quant",
    import_path="backend.src.module.quant.builder",
    loader=_load_quant_graph,
    is_implemented=True,
    description="Multi-agent quant workflow",
))


ModuleRegistry.register(AgentModuleType.DATA_SCIENTIST, ModuleInfo(
    name="data_scientist",
    import_path="backend.src.module.data_scientist.builder",
    loader=_load_data_scientist_graph,
    is_implemented=True,
    description="Multi-agent data scientist workflow",
))

ModuleRegistry.register(AgentModuleType.DEV, ModuleInfo(
    name="dev",
    import_path="backend.src.module.dev.builder",
    loader=_load_dev_graph,
    is_implemented=True,
    description="Multi-agent dev workflow",
))

ModuleRegistry.register(AgentModuleType.SLIDES, ModuleInfo(
    name="slides",
    import_path="backend.src.module.slides.builder",
    loader=_load_slides_graph,
    is_implemented=True,
    description="Multi-agent slides workflow",
))

ModuleRegistry.register(AgentModuleType.DOCUMENTS, ModuleInfo(
    name="documents",
    import_path="backend.src.module.documents.builder",
    loader=_load_documents_graph,
    is_implemented=True,
    description="Multi-agent documents workflow",
))


# # =============================================================================
# # Module Tool Mapping
# # =============================================================================

# MODULE_TOOL_MAPPING = {
#     AgentModuleType.GENERAL: ["*"],  # All tools
    
#     AgentModuleType.DESIGN: [
#         "design_*",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#         "register_port",
#         "shell_run_command", "shell_view",
#     ],
    
#     AgentModuleType.DEV: [
#         "file_*", "shell_*", 
#         "browser_*", "click", "drag", "dropdown", "enter_text", "enter_text_multiple_fields", "navigate", "press_key", "scroll", "tab", "view", "wait",
#         "web_batch_search", "web_search", "web_visit_compress", "web_visit",
#         "todo_*", "message_user",
#         "grep", "ast_grep", "lsp", "lsp_manager", "str_replace_editor",
#         "init", "register_port", "save_checkpoint", "database",
#     ],
    
#     AgentModuleType.DOCUMENTS: [
#         "document_*", "image_generate", "video_generate",
#         "image_search", "read_remote_image", "web_batch_search", "web_search", "web_visit_compress", "web_visit",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#         "shell_run_command",  # For LaTeX compilation
#     ],
    
#     AgentModuleType.SLIDES: [
#         "slide_*", "image_generate", "video_generate",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#         "image_generate",
#         "web_search", "image_search", "read_remote_image", "web_batch_search", "web_visit_compress", "web_visit",
#     ],
    
#     AgentModuleType.ACADEMIC: [
#         "document_*", "image_generate",
#         "image_search", "read_remote_image", "web_batch_search", "web_search", "web_visit_compress", "web_visit",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#         "web_*", "browser_*",
#     ],
    
#     AgentModuleType.DEEP_RESEARCH: [
#         "web_*", "browser_*", "image_generate",
#         "image_search", "read_remote_image", "web_batch_search", "web_search", "web_visit_compress", "web_visit",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#     ],
    
#     AgentModuleType.DATA_SCIENTIST: [
#         "file_*", "shell_*", "browser_*",
#         "image_search", "read_remote_image", "web_batch_search", "web_search", "web_visit_compress", "web_visit",
#         "todo_*", "message_user",
#         "file_read", "file_write", "file_edit", "file_patch",
#         "ast_grep", "grep", "str_replace_editor",
#         "database",
#         "image_generate",
#     ],
# }

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
    enable_background_investigation: bool = Field(default=False, description="Enable background web search before agent starts")
    enable_web_search: bool = Field(default=True, description="Enable web search")
    locale: str = Field(default="en-US", description="User's language locale")
    enable_added_tools: bool = Field(default=False, description="Enable added research tools (paper_search, arxiv, etc.)")
    mcp_settings: Optional[dict] = Field(default=None, description="MCP server configuration (user-provided, not sandbox). Same format as chat endpoint.")

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
    return settings.AGENT_RECURSION_LIMIT if settings.AGENT_RECURSION_LIMIT > 0 else 1000


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
    enable_added_tools: bool,
    locale: str,
    db_session: CurrentSession,  # Required for slide subscriber
    user_api_key: str,  # User's JWT token for MCP authentication
    user_id: str,
    mcp_settings: Optional[dict] = None,  # User-provided MCP server configs (Source C)
):
    """
    Async generator for streaming agent workflow events.

    This generator:
    1. Sends "processing" status immediately
    2. Creates/reuses sandbox (lazy initialization)
    3. Sends "sandbox_ready" status
    4. Runs agent workflow
    5. Streams responses with II-Agent Frontend format + AG-UI Protocol support:
       - session: On stream start
       - content: Text streaming (start/delta/stop)
       - thinking: Reasoning events (auto-detected from model output)
       - tool_call: Tool execution lifecycle (start/delta/stop)
       - tool_result: Tool outputs
       - status: Status updates (processing, sandbox_ready, etc.)
       - usage: Token usage statistics
       - complete: Stream completion
       - error: Error events
    """
    # Track reasoning state for AG-UI Protocol (using structured ReasoningState)
    reasoning_state = ReasoningState()

    # Create II-Agent event adapter for frontend compatibility
    adapter = create_sse_adapter(session_id=thread_id, model_id=module_name)

    try:
        # Emit session event at stream start (II-Agent format)
        yield adapter.session_event(is_new=True)
        # STEP 1: Send immediate feedback
        # Emit II-Agent format status
        yield adapter.status_update("processing", f"Processing with {module_name} module...", module=module_name)

        # Also emit AG-UI format for backward compatibility
        yield _make_event("status", {
            "type": "processing",
            "message": f"Processing with {module_name} module...",
            "module": module_name,
        })
        
        # STEP 2: Get or create sandbox (lazy initialization)
        try:
            logger.info(f"Agent stream: Getting sandbox for session {sandbox_manager.session_id}")
            sandbox, is_cold_start = await sandbox_manager.get_sandbox()
            
            start_type = "cold_start" if is_cold_start else "warm_start"
            yield _make_event("status", {
                "type": "sandbox_ready",
                "sandbox_id": sandbox.sandbox_id,
                "message": "Environment ready" if is_cold_start else "Reconnected to environment",
                "start_type": start_type,
            })
            
        except Exception as e:
            logger.error(f"Agent stream: Sandbox creation failed: {e}")
            yield _make_event("error", {
                "type": "sandbox_error",
                "message": f"Failed to create sandbox: {e}"
            })
            return
        
        # =====================================================================
        # STEP 3: MCP is already configured by sandbox_service
        # =====================================================================
        # The cold/warm start pattern means MCP initialization is done:
        # - COLD START: sandbox_service.pre_configure_mcp_server() already ran
        #   (health check + credential + tool server URL + verification)
        # - WARM START: sandbox_service.reset_tool_server() already ran
        #   (just tool server URL reset, ~200-500ms)
        #
        # We just need to get the MCP URL for downstream use
        mcp_url = await sandbox.expose_port(settings.SANDBOX_MCP_SERVER_PORT)
        logger.info(f"Agent stream: MCP URL = {mcp_url} (start_type={start_type})")
        
        # Emit appropriate status based on cold/warm start
        yield _make_event("status", {
            "type": "mcp_ready",
            "message": f"Tools ready ({start_type})",
            "mcp_url": mcp_url,
            "start_type": start_type,
        })
        
        # STEP 3.5: Register Codex SSE server and create CodexAgentTool if available
        # OPTIMIZATION: Only register Codex on COLD START - it's already running on warm start
        codex_tool = None
        codex_url = None
        try:
            from backend.src.tool_server.mcp.client import MCPClient
            
            if is_cold_start:
                # COLD START: Register Codex SSE server (slow ~2-5s)
                async with MCPClient(mcp_url) as mcp_client:
                    codex_result = await mcp_client.register_codex()
                    
                    if codex_result.get("status") in ("success", "already_running"):
                        codex_url = await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT)
                        logger.info(f"Agent stream: Codex SSE server registered at {codex_url}")
                        
                        from backend.src.agents.tools.codex_agent import create_codex_tool
                        
                        codex_tool = create_codex_tool(
                            codex_url=f"{codex_url}/messages",
                            timeout=300,
                            session_id=thread_id,
                            event_callback=None,  
                        )
                        
                        yield _make_event("status", {
                            "type": "codex_ready",
                            "message": "Codex agent available for complex coding tasks",
                            "codex_url": codex_url,
                        })
                    else:
                        logger.debug(f"Agent stream: Codex not available: {codex_result}")
            else:
                # WARM START: Codex is already running, just get the URL (fast ~100ms)
                codex_url = await sandbox.expose_port(settings.SANDBOX_CODEX_SSE_PORT)
                logger.info(f"Agent stream: Codex already running at {codex_url} (warm start)")
                
                from backend.src.agents.tools.codex_agent import create_codex_tool
                
                codex_tool = create_codex_tool(
                    codex_url=f"{codex_url}/messages",
                    timeout=300,
                    session_id=thread_id,
                    event_callback=None,
                )
                
                yield _make_event("status", {
                    "type": "codex_ready",
                    "message": "Codex agent available (warm start)",
                    "codex_url": codex_url,
                })
                    
        except Exception as codex_error:
            logger.debug(f"Agent stream: Codex registration skipped: {codex_error}")
            # Codex is optional - continue without it
        
        # STEP 3.6: Get VS Code URL for frontend (viewer)
        vscode_url = None
        try:
            vscode_url = await sandbox.expose_port(settings.SANDBOX_CODE_SERVER_PORT)
            logger.info(f"Agent stream: VS Code available at {vscode_url}")
            
            yield _make_event("status", {
                "type": "vscode_ready",
                "message": "VS Code viewer available",
                "vscode_url": vscode_url,
            })
        except Exception as vs_error:
            logger.warning(f"Agent stream: Failed to expose VS Code port: {vs_error}")
        
        # STEP 3.7: Get Design MCP Server URL for diagram editing
        design_url = None
        try:
            design_url = await sandbox.expose_port(settings.SANDBOX_DESIGN_MCP_PORT)
            logger.info(f"Agent stream: Design MCP Server available at {design_url}")
            
            yield _make_event("status", {
                "type": "design_ready",
                "message": "Design viewer available (Draw.io)",
                "design_url": design_url,
            })
        except Exception as design_error:
            logger.debug(f"Agent stream: Design MCP port not available (expected if not in image): {design_error}")
        
        # STEP 3.8: Get LaTeX Editor URL for document editing
        latex_url = None
        try:
            latex_url = await sandbox.expose_port(settings.SANDBOX_LATEX_EDITOR_PORT)
            logger.info(f"Agent stream: LaTeX Editor available at {latex_url}")
            
            yield _make_event("status", {
                "type": "latex_ready",
                "message": "LaTeX Editor available",
                "latex_url": latex_url,
            })
        except Exception as latex_error:
            logger.debug(f"Agent stream: LaTeX Editor port not available (expected if not in image): {latex_error}")
        
        # STEP 3.9: Get Excalidraw URL for diagram editing
        excalidraw_url = None
        try:
            excalidraw_url = await sandbox.expose_port(settings.SANDBOX_EXCALIDRAW_PORT)
            logger.info(f"Agent stream: Excalidraw available at {excalidraw_url}")
            
            yield _make_event("status", {
                "type": "excalidraw_ready",
                "message": "Excalidraw available",
                "excalidraw_url": excalidraw_url,
            })
        except Exception as excalidraw_error:
            logger.debug(f"Agent stream: Excalidraw port not available (expected if not in image): {excalidraw_error}")
        
        # STEP 3.10: Get Graphiti MCP URL for Knowledge Graph operations
        graphiti_url = None
        try:
            graphiti_url = await sandbox.expose_port(settings.SANDBOX_GRAPHITI_MCP_PORT)
            logger.info(f"Agent stream: Graphiti MCP available at {graphiti_url}")
            
            yield _make_event("status", {
                "type": "graphiti_ready",
                "message": "Knowledge Graph available",
                "graphiti_url": graphiti_url,
            })
        except Exception as graphiti_error:
            logger.debug(f"Agent stream: Graphiti MCP port not available (expected if not in image): {graphiti_error}")
        
        # STEP 3.11: Emit consolidated agent_initialized event with ALL URLs
        # This is the event the frontend expects to set up the agent UI and store URLs
        # It must be emitted AFTER all individual URL status events
        yield adapter.agent_initialized(
            sandbox_id=sandbox.sandbox_id,
            vscode_url=vscode_url,
            mcp_url=mcp_url,
            codex_url=codex_url,
            design_url=design_url,
            latex_url=latex_url,
            excalidraw_url=excalidraw_url,
            graphiti_url=graphiti_url,
            start_type=start_type,
        )
        logger.info(f"Agent stream: Emitted agent_initialized with all URLs (start_type={start_type})")
        
        # STEP 4: MCP URL already obtained above, use it for workflow
        
        # STEP 4.5: Load skills from sandbox (optional)
        # OPTIMIZATION: Only load skills on COLD START - skills don't change between messages
        skills_prompt_section = ""
        if is_cold_start:
            try:
                from backend.src.agents.middleware.skills_middleware.sandbox_load import (
                    list_skills_from_sandbox,
                    format_skills_for_prompt,
                )
                skills = await list_skills_from_sandbox(sandbox)
                if skills:
                    skills_prompt_section = format_skills_for_prompt(skills)
                    logger.info(f"Agent stream: Loaded {len(skills)} skills from sandbox")
                    yield _make_event("status", {
                        "type": "skills_loaded",
                        "message": f"Loaded {len(skills)} skills",
                        "skill_count": len(skills),
                        "skill_names": [s.get("name", "") for s in skills[:10]],
                    })
                else:
                    logger.debug("Agent stream: No skills found in sandbox")
            except Exception as e:
                logger.warning(f"Agent stream: Failed to load skills: {e}")
                # Continue without skills - not fatal
        else:
            # WARM START: Skip skills loading (~1-2s saved)
            logger.debug("Agent stream: Skipping skills loading (warm start)")
        
        # STEP 5: Build workflow input
        # Messages are already in LangChain v1 format (string or list of content blocks)
        workflow_input = {
            "messages": messages,
            "locale": locale,
            "auto_accepted_plan": auto_accepted_plan,
            "enable_background_investigation": enable_background_investigation,
        }
        
        # Inject skills section into workflow input if available
        if skills_prompt_section:
            workflow_input["skills_prompt"] = skills_prompt_section
        
        # =====================================================================
        # STEP 5.5: Handle interrupt resume (HITL feedback continuation)
        # =====================================================================
        # If the frontend sent interrupt_feedback, the graph is paused at an
        # interrupt() call inside human_feedback_node. We need to resume the
        # graph with Command(resume=...) instead of starting a new run.
        is_interrupt_resume = False
        if interrupt_feedback is not None and interrupt_feedback != "":
            is_interrupt_resume = True
            logger.info(f"Agent stream: Resuming interrupted graph with feedback: {interrupt_feedback[:100]}...")
        
        # Load user's MCP settings from DB if not provided in request
        # This ensures user-configured MCPs (Source C) are available in agent flow
        effective_mcp_settings = mcp_settings or {}
        if not effective_mcp_settings:
            try:
                from backend.app.agent.crud.crud_mcp_setting import mcp_setting_dao
                from backend.app.agent.schema.mcp_setting import MCPToolType
                from backend.database.db import async_db_session
                
                async with async_db_session() as _mcp_db:
                    user_mcp_records = await mcp_setting_dao.get_by_user_id(
                        _mcp_db, int(user_id), only_active=True
                    )
                    # Build mcp_settings dict from CUSTOM type records that have mcp_config
                    custom_servers = {}
                    for record in user_mcp_records:
                        if (
                            record.tool_type == MCPToolType.CUSTOM
                            and record.mcp_config
                            and record.mcp_config.get("mcpServers")
                        ):
                            custom_servers.update(record.mcp_config["mcpServers"])
                    
                    if custom_servers:
                        effective_mcp_settings = {"servers": custom_servers}
                        logger.info(
                            f"Agent stream: Loaded {len(custom_servers)} user MCP server(s) "
                            f"from DB for user {user_id}"
                        )
            except Exception as mcp_load_err:
                logger.warning(
                    f"Agent stream: Failed to load user MCP settings from DB: {mcp_load_err}. "
                    "Continuing without user MCPs."
                )
        
        workflow_config = {
            "configurable": {
                "thread_id": thread_id,
                "enable_web_search": enable_web_search,
                "enable_added_tools": enable_added_tools,
                "max_search_results": max_search_results,
                "max_plan_iterations": max_plan_iterations,
                "max_step_num": max_step_num,
                "sandbox_id": sandbox.sandbox_id,
                "mcp_url": mcp_url,
                # User MCP settings (Source C) — additional MCP servers beyond sandbox
                "mcp_settings": effective_mcp_settings,
                # Codex SSE server URL (for CodexAgentTool)
                "codex_url": codex_url,
                # VS Code URL (for frontend viewer)
                "vscode_url": vscode_url,
                # Graphiti MCP URL (for Knowledge Graph operations)
                "graphiti_url": graphiti_url,
            },
            "recursion_limit": _get_recursion_limit(),
        }
        
        # STEP 6: Stream graph events with PostgreSQL checkpointer
        # First, warm up the database connection to prevent stale connection errors
        # This is critical after long sandbox/MCP initialization (30-60s cold start)
        db_ready = await checkpointer_manager.warm_up_connection()
        if not db_ready:
            logger.warning("Database connection warm-up failed, proceeding anyway")
            yield _make_event("warning", {
                "type": "db_connection_warning",
                "message": "Database connection may be unstable"
            })
        
        yield _make_event("status", {
            "type": "agent_start",
            "message": "Agent processing..."
        })
        
        # Use the centralized PostgreSQL checkpointer with the provided graph
        async with checkpointer_manager.get_graph_with_checkpointer(graph, thread_id) as configured_graph:
            # Determine the correct input for the graph
            # If resuming from an interrupt, use Command(resume=...) to pass the
            # human's feedback back into the interrupt() call in human_feedback_node
            if is_interrupt_resume:
                from langgraph.types import Command as LangGraphCommand
                stream_input = LangGraphCommand(resume=interrupt_feedback)
                logger.info(f"Agent stream: Using Command(resume=...) for interrupt resume")
            else:
                stream_input = workflow_input
            
            async for event in configured_graph.astream_events(
                stream_input,
                config=workflow_config,
                version="v2",
                subgraphs=True,  # CRITICAL: Enable streaming from nested agent subgraphs
            ):
                event_type = event.get("event", "")

                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if isinstance(chunk, AIMessageChunk):
                        has_content_blocks = hasattr(chunk, 'content_blocks') and chunk.content_blocks

                        # Process content blocks - LangChain standardizes reasoning/text/etc.
                        # content_blocks provides unified format across all providers
                        if has_content_blocks:
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

                                            # Emit II-Agent format thinking start
                                            if not adapter.thinking_active:
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
                                        # Close reasoning session if switching to text
                                        if reasoning_state.is_active:
                                            msg_id = reasoning_state.end_reasoning()

                                            # Emit II-Agent format thinking stop
                                            if adapter.thinking_active:
                                                yield adapter.thinking_stop()

                                            # Emit AG-UI format for backward compatibility
                                            yield _make_event("reasoning_message_end", {
                                                "messageId": msg_id,
                                            })
                                            yield _make_event("reasoning_end", {
                                                "messageId": msg_id,
                                            })

                                        # Emit II-Agent format content events
                                        if not adapter.content_started:
                                            yield adapter.content_start()
                                        yield adapter.content_delta(text_content)

                                        # Emit text message chunk (AG-UI format)
                                        yield _make_event("message", {
                                            "type": "chunk",
                                            "content": text_content,
                                            "thread_id": thread_id,
                                        })
                        
                        # Handle list content (e.g., Anthropic format)
                        elif isinstance(chunk.content, list) and chunk.content:
                            for item in chunk.content:
                                if isinstance(item, dict):
                                    item_type = item.get('type', '')

                                    # Handle reasoning blocks in list content
                                    if item_type == 'reasoning':
                                        reasoning_text = item.get('reasoning') or item.get('thinking') or item.get('text', '')
                                        if reasoning_text:
                                            # Start reasoning session if not already active
                                            if not reasoning_state.is_active:
                                                msg_id = reasoning_state.start_reasoning()
                                                if not adapter.thinking_active:
                                                    yield adapter.thinking_start()
                                                yield _make_event("reasoning_start", {"messageId": msg_id})
                                                yield _make_event("reasoning_message_start", {"messageId": msg_id, "role": "assistant"})

                                            # Emit II-Agent format thinking delta
                                            yield adapter.thinking_delta(reasoning_text)

                                            # Stream reasoning content (AG-UI format)
                                            yield _make_event("reasoning_message_content", {
                                                "messageId": reasoning_state.message_id,
                                                "delta": reasoning_text,
                                            })

                                    elif item_type == 'text':
                                        text = item.get('text', '')
                                        if text:
                                            # Close reasoning if switching to text
                                            if reasoning_state.is_active:
                                                msg_id = reasoning_state.end_reasoning()
                                                if adapter.thinking_active:
                                                    yield adapter.thinking_stop()
                                                yield _make_event("reasoning_message_end", {"messageId": msg_id})
                                                yield _make_event("reasoning_end", {"messageId": msg_id})

                                            # Emit II-Agent format content events
                                            if not adapter.content_started:
                                                yield adapter.content_start()
                                            yield adapter.content_delta(text)
                                            # Emit AG-UI format
                                            yield _make_event("message", {
                                                "type": "chunk",
                                                "content": text,
                                                "thread_id": thread_id,
                                            })
                                    elif item_type == 'text_delta':
                                        text = item.get('text', '')
                                        if text:
                                            # Close reasoning if switching to text
                                            if reasoning_state.is_active:
                                                msg_id = reasoning_state.end_reasoning()
                                                if adapter.thinking_active:
                                                    yield adapter.thinking_stop()
                                                yield _make_event("reasoning_message_end", {"messageId": msg_id})
                                                yield _make_event("reasoning_end", {"messageId": msg_id})

                                            # Emit II-Agent format content events
                                            if not adapter.content_started:
                                                yield adapter.content_start()
                                            yield adapter.content_delta(text)
                                            # Emit AG-UI format
                                            yield _make_event("message", {
                                                "type": "chunk",
                                                "content": text,
                                                "thread_id": thread_id,
                                            })
                                elif isinstance(item, str) and item:
                                    # Emit II-Agent format content events
                                    if not adapter.content_started:
                                        yield adapter.content_start()
                                    yield adapter.content_delta(item)
                                    # Emit AG-UI format
                                    yield _make_event("message", {
                                        "type": "chunk",
                                        "content": item,
                                        "thread_id": thread_id,
                                    })
                        
                        # Fallback for simple string content (no content_blocks)
                        elif isinstance(chunk.content, str) and chunk.content:
                            # Close reasoning if active
                            if reasoning_state.is_active:
                                msg_id = reasoning_state.end_reasoning()

                                # Emit II-Agent format thinking stop
                                if adapter.thinking_active:
                                    yield adapter.thinking_stop()

                                # Emit AG-UI format for backward compatibility
                                yield _make_event("reasoning_message_end", {
                                    "messageId": msg_id,
                                })
                                yield _make_event("reasoning_end", {
                                    "messageId": msg_id,
                                })

                            # Emit II-Agent format content events
                            if not adapter.content_started:
                                yield adapter.content_start()
                            yield adapter.content_delta(chunk.content)

                            # Emit AG-UI format
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

                    # Emit II-Agent format tool_call start
                    yield adapter.tool_call_start(tool_run_id, tool_name)

                    # AG-UI Protocol: TOOL_CALL_START (using model method)
                    event_data = tool_call.to_ag_ui_start_event()
                    event_data["thread_id"] = thread_id
                    yield _make_event("tool_call_start", event_data)

                    # AG-UI Protocol: TOOL_CALL_ARGS (send full args as single delta)
                    if tool_input:
                        # Use safe serializer to handle ToolRuntime and other complex types
                        args_str = _safe_json_serialize(tool_input)
                        # Emit II-Agent format tool_call delta
                        yield adapter.tool_call_delta(tool_run_id, args_str)
                        # Emit AG-UI format
                        yield _make_event("tool_call_args", tool_call.to_ag_ui_args_event(args_str))
                
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_run_id = event.get("run_id", str(uuid4()))
                    tool_output = event.get("data", {}).get("output", "")
                    tool_input = event.get("data", {}).get("input", {})

                    # ── Extract content from LangChain ToolMessage ──
                    # LangGraph's astream_events delivers on_tool_end with
                    # data.output as a raw ToolMessage Pydantic object.
                    # We extract .content here at the source so downstream
                    # serialization never touches the ToolMessage wrapper.
                    if isinstance(tool_output, (ToolMessage, BaseMessage)):
                        tool_output = tool_output.content
                    elif hasattr(tool_output, 'content') and hasattr(tool_output, 'tool_call_id'):
                        # Duck-typed ToolMessage (cross-module import edge case)
                        tool_output = tool_output.content

                    # ── Normalize MCP content blocks to plain text ──
                    # langchain-mcp-adapters returns ToolMessage.content as a
                    # list of content block dicts from the MCP protocol:
                    #   [{"type": "text", "text": "actual output", "id": "..."}]
                    # The frontend expects a plain string or serializable value.
                    if isinstance(tool_output, list) and tool_output:
                        if all(
                            isinstance(b, dict) and b.get("type") in ("text", "image", "file")
                            for b in tool_output
                        ):
                            text_parts = [b["text"] for b in tool_output if b.get("type") == "text" and "text" in b]
                            image_blocks = [b for b in tool_output if b.get("type") == "image"]
                            if text_parts and not image_blocks:
                                tool_output = "\n".join(text_parts) if len(text_parts) > 1 else text_parts[0]
                            elif image_blocks:
                                # Keep as list — image processing below handles it
                                pass

                    # Optimization: Process base64 images in tool output
                    if isinstance(tool_output, list) and user_id and db_session:
                        new_output = []
                        modified = False
                        for block in tool_output:
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
                                            filename=f"tool_output_{tool_run_id[:8]}.png",
                                            db=db_session,
                                            thread_id=thread_id
                                        )
                                        
                                        # Replace with URL block
                                        new_output.append({
                                            "type": "image",
                                            "source": {
                                                "type": "url",
                                                "url": url
                                            }
                                        })
                                        modified = True
                                        logger.info(f"[{thread_id}] Uploaded tool image to {url}")
                                    except Exception as e:
                                        logger.error(f"[{thread_id}] Failed to upload tool image: {e}")
                                        new_output.append(block)
                                else:
                                    new_output.append(block)
                            else:
                                new_output.append(block)
                        
                        if modified:
                            tool_output = new_output



                    # Emit II-Agent format tool_call stop
                    input_str = _safe_json_serialize(tool_input) if tool_input else "{}"
                    yield adapter.tool_call_stop(tool_run_id, tool_name, input_str)

                    # AG-UI Protocol: TOOL_CALL_END
                    yield _make_event("tool_call_end", {
                        "toolCallId": tool_run_id,
                    })

                    # Emit II-Agent format tool_result
                    yield adapter.tool_result(tool_run_id, tool_name, tool_output)

                    # Emit tool result for frontend consumption and conversation history
                    yield _make_event("tool_result", {
                        "tool_call_id": tool_run_id,
                        "tool_name": tool_name,
                        "tool_display_name": humanize_tool_name(tool_name),
                        "tool_input": tool_input,
                        "result": tool_output,
                        "is_error": False,
                        "thread_id": thread_id,
                    })
                    
                    # Sync slide tool results to database (SlideWrite, SlideEdit, etc.)
                    try:
                        if tool_name in ["SlideWrite", "SlideEdit", "slide_apply_patch"]:
                            logger.debug(f"Syncing slide result for {tool_name}")
                        
                        # Pass sandbox context for content processing (replaces local URLs with permanent ones)
                        # The sandbox.download_file signature is: async (path: str, format: str) -> bytes
                        async def sandbox_download(path: str, format: str = "bytes") -> bytes:
                            return await sandbox.download_file(path, format=format)
                        
                        await slide_subscriber.on_tool_complete(
                            db_session=db_session,
                            tool_name=tool_name,
                            tool_input=event.get("data", {}).get("input", {}),
                            tool_result=tool_output,
                            thread_id=thread_id,
                            sandbox_id=sandbox.sandbox_id,
                            sandbox_download_func=sandbox_download,
                        )
                    except Exception as e:
                        logger.error(f"Failed to sync slide tool result: {e}")
                    
                    # Process message_user attachments (upload to storage, replace sandbox paths with URLs)
                    try:
                        if tool_name == "message_user":
                            logger.debug(f"Processing message_user attachments for thread {thread_id}")
                            enhanced_result = await user_message_subscriber.on_tool_complete(
                                tool_name=tool_name,
                                tool_result=tool_output,
                                thread_id=thread_id,
                                sandbox_download_func=sandbox_download,
                                sandbox_id=sandbox.sandbox_id,
                            )
                            if enhanced_result:
                                # Emit enhanced tool result with attachment URLs
                                yield _make_event("tool_result_enhanced", {
                                    "role": "tool",
                                    "content": enhanced_result,
                                    "toolCallId": tool_run_id,
                                    "toolName": tool_name,
                                    "thread_id": thread_id,
                                    "has_attachments": True,
                                })
                                logger.info(f"Emitted enhanced tool_result with attachment URLs")
                    except Exception as e:
                        logger.error(f"Failed to process message_user attachments: {e}")

                elif event_type == "on_chain_end":
                    # Handle sub-agent completion events
                    # Sub-agents (CompiledSubAgent) trigger on_chain_end when they complete
                    chain_name = event.get("name", "")
                    chain_tags = event.get("tags", [])
                    chain_metadata = event.get("metadata", {})

                    # Detect if this is a sub-agent completion based on:
                    # 1. Chain name contains "subagent" or "compiled"
                    # 2. Tags contain subagent identifiers
                    # 3. Metadata indicates a sub-agent handler
                    is_subagent = (
                        "subagent" in chain_name.lower() or
                        "compiled" in chain_name.lower() or
                        any("subagent" in tag.lower() for tag in chain_tags) or
                        chain_name in ["planner", "analyzer", "coder", "executor", "verifier", "researcher", "debugger", "reviewer"]
                    )

                    if is_subagent:
                        # Extract output from the chain completion
                        chain_output = event.get("data", {}).get("output", "")
                        output_text = ""

                        # Handle different output formats
                        if isinstance(chain_output, str):
                            output_text = chain_output
                        elif isinstance(chain_output, dict):
                            # Try to get content from dict
                            output_text = chain_output.get("content", "") or chain_output.get("text", "") or str(chain_output)
                        elif chain_output:
                            output_text = str(chain_output)

                        # Create summary if output is too long
                        if len(output_text) > 500:
                            output_text = output_text[:497] + "..."

                        # Emit sub_agent_complete event
                        logger.debug(f"Sub-agent completed: {chain_name}")
                        yield _make_event("sub_agent_complete", {
                            "text": output_text if output_text else f"{chain_name} completed",
                            "chain_name": chain_name,
                            "thread_id": thread_id,
                        })

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

            # Emit II-Agent format thinking stop
            if adapter.thinking_active:
                yield adapter.thinking_stop()

            # Emit AG-UI format for backward compatibility
            yield _make_event("reasoning_message_end", {
                "messageId": msg_id,
            })
            yield _make_event("reasoning_end", {
                "messageId": msg_id,
            })

        # STEP 7: Send completion
        # Emit II-Agent format complete event
        yield adapter.complete(finish_reason="end_turn")

        # Also emit AG-UI format status for backward compatibility
        yield _make_event("status", {
            "type": "complete",
            "message": "Done",
            "sandbox_id": sandbox.sandbox_id,
            "vscode_url": vscode_url,  # VS Code viewer URL for frontend
            "codex_url": codex_url,  # Codex SSE URL if available
            "design_url": design_url,  # Design MCP Server URL if available
            "latex_url": latex_url,  # LaTeX Editor URL if available
            "excalidraw_url": excalidraw_url,  # Excalidraw URL if available
            "graphiti_url": graphiti_url,  # Graphiti MCP URL for Knowledge Graph
        })
        
    except Exception as e:
        logger.exception(f"Agent stream error: {e}")
        # Emit II-Agent format error
        yield adapter.error(str(e), "stream_error")
        # Also emit AG-UI format for backward compatibility
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
    - academic: Multi-agent academic research workflow
    - slides: Multi-agent slides workflow
    - design: Multi-agent design workflow
    - dev: Multi-agent softwaredevelopment workflow
    - data_scientist: Multi-agent data scientist workflow
    - 

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

    # Persist session to database (Fix for 404 in history & General Mode)
    # Using Service logic (which now handles race conditions)
    # We await this to ensure session exists before any stream events or messages are saved.
    try:
        async with async_db_session() as session_db:
            await chat_session_service.get_or_create(
                db=session_db,
                session_uuid=thread_id,
                user_id=int(user_id), # Ensure integer
                agent_type=request.module.value
            )
            # Context manager auto-commits on exit
    except Exception as e:
        logger.error(f"Failed to persist session {thread_id}: {e}")
        # Proceed despite DB error to allow streaming
    
    def get_agent_category(module: AgentModuleType) -> AgentCategory | None:
        """Map module name to agent category for skills injection."""
        if module == AgentModuleType.GENERAL:
            return "general"
        elif module == AgentModuleType.QUANT:
            return "general"
        elif module == AgentModuleType.DEEP_RESEARCH:
            return "scientific"
        elif module == AgentModuleType.ACADEMIC:
            return "academic"
        elif module == AgentModuleType.SLIDES:
            return "general"
        elif module == AgentModuleType.DESIGN:
            return "general"
        elif module == AgentModuleType.DEV:
            return "general"
        elif module == AgentModuleType.DATA_SCIENTIST:
            return "scientific"
        elif module == AgentModuleType.EXCALIDRAW:
            return "general"
        elif module == AgentModuleType.DOCUMENTS:
            return "general"
        return None

    # Create session sandbox manager (lazy - no sandbox yet)
    # Using thread_id for sandbox session to maintain consistency
    sandbox_manager = SessionSandboxManager(
        user_id=user_id,
        session_id=thread_id,  # thread_id serves as session_id for sandbox
        user_api_key=token,  # Pass JWT token for MCP credential setup
        agent_category=get_agent_category(request.module),
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
            enable_added_tools=request.enable_added_tools,
            locale=request.locale,
            db_session=db,
            user_api_key=token,  # Pass user's JWT for MCP authentication
            user_id=user_id,
            mcp_settings=request.mcp_settings,
        ),

        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
