"""
Executor Node Implementation.

This module contains the executor_node that follows the robust base_node pattern.
It executes, tests, and validates the code written by the Coder.

Key Features:
- Full MCP server integration via MultiServerMCPClient
- Agent-based execution (not direct LLM calls)
- Debugger subagent for fixing errors
- Access to file system, shell, browser tools
- Routes to verifier when execution complete
"""

import json
import logging
import os
from functools import partial
from typing import Annotated, Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command, interrupt

from backend.src.agents import create_deepagent
from backend.src.config.configuration import Configuration
from backend.src.llms.llm import get_llm
from backend.src.module.dev.template import apply_prompt_template, get_prompt_template
from backend.src.tools import (
    crawl_tool,
    get_retriever_tool,
    get_web_search_tool,
)
from backend.src.tools.search import LoggedTavilySearch
from backend.src.utils.context_manager import ContextManager, validate_message_content
from backend.src.utils.json_utils import repair_json_output, sanitize_tool_response

from backend.src.module.dev.types import State
from backend.src.config.tool_filter_config import apply_tool_filter
from .subagents import get_subagents

from backend.src.tools import (
    people_search_tool,
    company_search_tool,
    paper_search_tool,
    get_paper_details_tool,
    search_authors_tool,
    get_author_details_tool,
    get_author_papers_tool,
    semantic_scholar_search_tool,
    arxiv_search_tool,
    pubmed_central_tool,
    create_view_image_tool,
)

logger = logging.getLogger(__name__)


# =============================================================================
# State Preservation Utilities
# =============================================================================

def preserve_state_meta_fields(state: State) -> dict:
    """
    Extract meta/config fields that should be preserved across state transitions.
    
    Minimal fields - most state is in messages.
    """
    return {
        "resources": state.get("resources", []),
    }


# =============================================================================
# Agent Execution Helpers
# =============================================================================

async def _execute_agent_step(
    state: State, agent, agent_name: str, config: RunnableConfig = None
) -> Command[Literal["verifier"]]:
    """
    Helper function to execute the executor agent step.
    
    This is the core execution logic that handles:
    - Building agent input with context
    - Applying context compression
    - Managing recursion limits
    - Error handling and diagnostics
    
    Executor ALWAYS routes to verifier when done.
    
    Args:
        state: Current workflow state
        agent: The configured agent to execute
        agent_name: Name of the agent for logging
        config: Runnable configuration
        
    Returns:
        Command to update state and route to verifier
    """
    logger.debug(f"[_execute_agent_step] Starting execution for agent: {agent_name}")
    
    # Build agent input messages - convert dict messages to proper message objects
    messages = list(state.get("messages", []))

    agent_input = {"messages": messages}

    # Get recursion limit from environment
    default_recursion_limit = 1000
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)

        if parsed_limit > 0:
            recursion_limit = parsed_limit
            logger.info(f"Recursion limit set to: {recursion_limit}")
        else:
            logger.warning(
                f"AGENT_RECURSION_LIMIT value '{env_value_str}' (parsed as {parsed_limit}) is not positive. "
                f"Using default value {default_recursion_limit}."
            )
            recursion_limit = default_recursion_limit
    except ValueError:
        raw_env_value = os.getenv("AGENT_RECURSION_LIMIT")
        logger.warning(
            f"Invalid AGENT_RECURSION_LIMIT value: '{raw_env_value}'. "
            f"Using default value {default_recursion_limit}."
        )
        recursion_limit = default_recursion_limit

    logger.info(f"Agent input: {agent_input}")
    
    # Validate message content before invoking agent
    try:
        validated_messages = validate_message_content(agent_input["messages"])
        agent_input["messages"] = validated_messages
    except Exception as validation_error:
        logger.error(f"Error validating agent input messages: {validation_error}")
    
    # Execute the agent using streaming to enable visibility of tool calls
    # Pattern from deepagents_cli - uses astream() with dual stream_mode
    try:
        # Build agent config with recursion limit and configurable settings
        agent_config = {
            "recursion_limit": recursion_limit,
            "configurable": config.get("configurable", {}) if config else {},
        }
        
        # Stream agent execution - this makes tool calls and messages visible
        collected_messages = []
        
        def _extract_messages(data):
            """Safely extract messages list from various container types."""
            if isinstance(data, list):
                return data
            # Handle LangGraph Overwrite objects
            if hasattr(data, 'value'):
                return data.value if isinstance(data.value, list) else []
            return []
        
        # Track the current AIMessageChunk being built (for proper merging)
        current_ai_chunk: Optional[AIMessageChunk] = None
        
        def _finalize_current_chunk():
            """Finalize the current AI chunk and add to collected messages."""
            nonlocal current_ai_chunk
            if current_ai_chunk is not None:
                # Append merged chunk (preserves tool_call IDs from first chunk)
                collected_messages.append(current_ai_chunk)
                current_ai_chunk = None
        
        async for chunk in agent.astream(
            agent_input,
            stream_mode=["messages", "updates"],
            subgraphs=True,
            config=agent_config,
        ):
            # With subgraphs=True and dual stream_mode, chunk is (namespace, mode, data)
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                # Handle simple dict format (fallback)
                if isinstance(chunk, dict) and "messages" in chunk:
                    collected_messages = _extract_messages(chunk["messages"])
                continue
            
            _namespace, stream_mode, data = chunk
            
            if stream_mode == "messages":
                # data is (message, metadata) tuple
                if isinstance(data, tuple) and len(data) == 2:
                    message, _metadata = data
                    
                    # Properly merge AIMessageChunks to preserve tool_call IDs
                    if isinstance(message, AIMessageChunk):
                        if current_ai_chunk is None:
                            # First chunk - initialize with the ID-bearing chunk
                            current_ai_chunk = message
                        else:
                            # Merge subsequent chunks (preserves ID from first)
                            current_ai_chunk = current_ai_chunk + message
                    else:
                        # Non-AIMessageChunk (e.g., ToolMessage) - finalize current chunk first
                        _finalize_current_chunk()
                        if hasattr(message, "content"):
                            collected_messages.append(message)
            
            elif stream_mode == "updates":
                # Updates overwrite collected_messages, finalize current chunk first
                _finalize_current_chunk()
                # State updates - extract final messages
                if isinstance(data, dict):
                    # Get messages from any node's update
                    for node_name, node_data in data.items():
                        if isinstance(node_data, dict) and "messages" in node_data:
                            collected_messages = _extract_messages(node_data["messages"])
        
        # Finalize any remaining chunk after streaming completes
        _finalize_current_chunk()
        
        # Build result compatible with existing code
        result = {"messages": collected_messages}
        
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        error_message = f"Error executing {agent_name} agent: {str(e)}"
        logger.exception(error_message)
        logger.error(f"Full traceback:\n{error_traceback}")
        
        # Enhanced error diagnostics for content-related errors
        if "Field required" in str(e) and "content" in str(e):
            logger.error(f"Message content validation error detected")
            for i, msg in enumerate(agent_input.get('messages', [])):
                logger.error(f"Message {i}: type={type(msg).__name__}, "
                            f"has_content={hasattr(msg, 'content')}, "
                            f"content_type={type(msg.content).__name__ if hasattr(msg, 'content') else 'N/A'}, "
                            f"content_len={len(str(msg.content)) if hasattr(msg, 'content') and msg.content else 0}")

        detailed_error = f"[ERROR] {agent_name.capitalize()} Agent Error\n\nError Details:\n{str(e)}\n\nPlease check the logs for more information."

        # On error, still route to verifier (let verifier assess the situation)
        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [
                    HumanMessage(
                        content=detailed_error,
                        name=agent_name,
                    )
                ],
            },
            goto="verifier",
        )

    # Process the result
    response_content = result["messages"][-1].content if result.get("messages") else ""
    
    # Sanitize response to remove extra tokens and truncate if needed
    response_content = sanitize_tool_response(str(response_content))
    
    logger.debug(f"{agent_name.capitalize()} full response: {response_content}")

    # Include all messages from agent result to preserve intermediate tool calls/results
    agent_messages = result.get("messages", [])
    logger.debug(
        f"{agent_name.capitalize()} returned {len(agent_messages)} messages. "
        f"Message types: {[type(msg).__name__ for msg in agent_messages]}"
    )
    
    # Executor ALWAYS routes to verifier
    logger.info(f"[Executor] Execution complete, routing to verifier")

    return Command(
        update={
            **preserve_state_meta_fields(state),
            "messages": agent_messages,
        },
        goto="verifier",
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
    *,
    tool_filter_role: str | None = None,
) -> Command[Literal["verifier"]]:
    """
    Helper function to set up an agent with appropriate tools and execute a step.

    This function handles the common logic for agent setup:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools (default + MCP)
    3. Executes the agent on the current step

    Args:
        state: The current state
        config: The runnable config
        agent_type: The type of agent (e.g., "executor")
        default_tools: The default tools to add to the agent

    Returns:
        Command to update state and go to verifier
    """
    configurable = Configuration.from_runnable_config(config)
    mcp_servers = {}
    enabled_tools = {}

    # Extract MCP server configuration for this agent type
    # MCP settings allow dynamic tool loading from external servers
    if configurable.mcp_settings:
        servers = configurable.mcp_settings.get("servers", {})
        for server_name, server_config in servers.items():
            # Check if this MCP server has enabled tools and should be added to this agent type
            if (
                server_config.get("enabled_tools")
                and agent_type in server_config.get("add_to_agents", [])
            ):
                # Extract transport configuration for MCP client
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                # Track which tools come from which server
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name

    # Add dynamic sandbox MCP server if URL is provided (from /agent/stream endpoint)
    # This enables tools like SlideWrite/SlideEdit to be available without static config
    if configurable.mcp_url:
        logger.info(f"[DEBUG_SLIDES] Adding dynamic sandbox MCP server at {configurable.mcp_url}")
        mcp_servers["sandbox"] = {
            "transport": "http",  # Tool Server uses HTTP transport
            "url": f"{configurable.mcp_url}/mcp",  # Endpoint is /mcp, not /sse
        }
    else:
        logger.info("[DEBUG_SLIDES] No mcp_url found in configurable")

    # Build tools list starting with defaults
    loaded_tools = default_tools[:]
    
    # Load MCP tools if any MCP servers are configured
    if mcp_servers:
        try:
            logger.info(f"[DEBUG_SLIDES] Loading MCP tools from {len(mcp_servers)} server(s): {list(mcp_servers.keys())}")
            client = MultiServerMCPClient(mcp_servers)
            all_tools = await client.get_tools()
            
            logger.info(f"[DEBUG_SLIDES] raw client.get_tools() returned {len(all_tools)} tools")
            for t in all_tools:
                logger.info(f"[DEBUG_SLIDES] Found tool: {t.name}")
            
            for tool in all_tools:
                # Determine which server this tool came from (MultiServerMCPClient may not expose this directly easily,
                # but we can try to guess or just accept it if it's from the dynamic sandbox)
                
                # Logic:
                # 1. If tool is in enabled_tools (from static config), accept it
                # 2. If we have a dynamic sandbox, ACCCEPT ALL tools (assumed to be from sandbox)
                #    This is safe because sandbox is isolated per session.
                
                is_static_allowed = tool.name in enabled_tools
                is_dynamic_sandbox = bool(configurable.mcp_url)
                
                logger.info(f"[DEBUG_SLIDES] Checking tool {tool.name}: static={is_static_allowed}, dynamic={is_dynamic_sandbox}")
                
                if is_static_allowed or is_dynamic_sandbox:
                    source = enabled_tools.get(tool.name, "sandbox" if is_dynamic_sandbox else "unknown")
                    
                    # Add server attribution to tool description
                    tool.description = (
                        f"Powered by '{source}'.\n{tool.description}"
                    )
                    loaded_tools.append(tool)
                    logger.debug(f"Loaded MCP tool: {tool.name} from {source}")
            
            logger.info(f"Successfully loaded {len(loaded_tools) - len(default_tools)} MCP tools")
        except Exception as e:
            logger.error(f"[DEBUG_SLIDES] Failed to load MCP tools: {e}", exc_info=True)
            # Continue with default tools only
    
    # Add CodexAgentTool if Codex SSE server is available
    # This allows the agent to delegate complex coding tasks to Codex
    if configurable.codex_url:
        try:
            from backend.src.agents.tools.codex_agent import create_codex_tool
            
            codex_tool = create_codex_tool(
                codex_url=f"{configurable.codex_url}/messages",
                timeout=300,
                session_id=configurable.thread_id,
            )
            loaded_tools.append(codex_tool)
            logger.info(f"[CODEX] Added CodexAgentTool for task delegation (url: {configurable.codex_url})")
        except Exception as codex_error:
            logger.warning(f"[CODEX] Failed to add CodexAgentTool: {codex_error}")

    # Create the agent with all tools
    # Apply tool filter based on role
    role = tool_filter_role or agent_type
    loaded_tools = apply_tool_filter(role, loaded_tools)

    logger.info(f"Creating agent '{agent_type}' (role={role}) with {len(loaded_tools)} tools")

    custom_config = {
        # ===== MIDDLEWARE TOGGLES (all 10 available middleware) ===== 
        "enable_summarization": True,
        "enable_model_retry": False,
        "enable_tool_retry": False,
        "enable_model_call_limit": False,
        "enable_tool_call_limit": False,
        "enable_model_fallback": False,  # Requires all fallback model providers to be configured
        "enable_persistent_tasks": False,  # Requires store - disable for local testing
        "enable_view_image": True,
        "enable_background_tasks": True,  # Requires store for subagents
        "enable_skills": True,
        
        # # ===== SUMMARIZATION SETTINGS =====
        # "summarization_trigger_tokens": 100000,  # Trigger summarization at this token count
        # "summarization_keep_messages": 10,        # Keep this many recent messages unsummarized
        
        # # ===== MODEL RETRY SETTINGS =====
        # "model_max_retries": 3,           # Max retry attempts for model calls
        # "model_backoff_factor": 2.0,      # Exponential backoff multiplier
        # "model_initial_delay": 1.0,       # Initial delay in seconds before retry
        
        # # ===== TOOL RETRY SETTINGS =====
        # "tool_max_retries": 2,            # Max retry attempts for tool calls
        # "tool_backoff_factor": 1.5,       # Exponential backoff multiplier
        # "tool_initial_delay": 0.5,        # Initial delay in seconds before retry
        
        # # ===== MODEL CALL LIMITS =====
        # "model_call_thread_limit": 50,   # Max model calls per thread
        # "model_call_run_limit": 20,       # Max model calls per run
        
        # # ===== TOOL CALL LIMITS =====
        # "tool_call_thread_limit": 100,   # Max tool calls per thread
        # "tool_call_run_limit": 50,        # Max tool calls per run
        
        # ===== BACKGROUND TASKS SETTINGS =====
        "background_task_timeout": 60.0,  # Timeout for background tasks in seconds
        
        # ===== Fallback models =====
        # Note: Disabled because init_chat_model tries to initialize all models
        # which requires all providers (OpenAI, Vertex AI, Anthropic) to be configured

        "enable_model_fallback": False,
        # "fallback_models": ["openai:gpt-4o", "openai:gpt-4o-mini", "anthropic:claude-sonnet-4-5-20250929",],
    }

    # Get executor-specific subagents (includes debugger)
    subagents = get_subagents(model=get_llm())
    
    # Load system prompt from local prompts folder
    try:
        local_system_prompt = get_prompt_template(agent_type)
        logger.debug(f"Loaded local prompt for {agent_type}")
    except Exception as e:
        logger.warning(f"Failed to load local prompt for {agent_type}: {e}")
        local_system_prompt = None
    
    agent = create_deepagent(
        agent_type,
        agent_type,
        loaded_tools,
        prompt_template=None,  # Don't load from root prompts
        system_prompt=local_system_prompt,  # Use locally loaded prompt
        use_default_middleware=True,
        middleware_config=custom_config,
        subagents=subagents,
    )
    
    return await _execute_agent_step(state, agent, agent_type, config)


# =============================================================================
# Executor Node - Main Entry Point
# =============================================================================

async def executor_node(
    state: State, config: RunnableConfig
) -> Command[Literal["verifier"]]:
    """
    Executor node - executes and tests the code written by Coder.
    
    This node:
    1. Inspects what the Coder built
    2. Executes scripts and runs tests
    3. Validates web apps using browser tools
    4. Uses debugger subagent to fix any errors
    5. Routes to verifier when execution is complete
    
    Routing:
        - ALWAYS → verifier (to assess sufficiency)
    """
    logger.info("Executor node running.")
    
    configurable = Configuration.from_runnable_config(config)
    logger.debug(f"[executor_node] Max search results: {configurable.max_search_results}")
    
    # Build tools list based on configuration
    tools = []

    # Add research tools if enabled
    if configurable.enable_added_tools:
        tools.extend([people_search_tool, company_search_tool, paper_search_tool, 
        get_paper_details_tool, search_authors_tool, get_author_details_tool, 
        get_author_papers_tool, semantic_scholar_search_tool, arxiv_search_tool, 
        pubmed_central_tool, create_view_image_tool()])

        logger.info("[executor_node] Added external tools")
    else:
        logger.info("[executor_node] External tools are disabled")
    
    # Add web search and crawl tools only if web search is enabled
    if configurable.enable_web_search:
        tools.extend([get_web_search_tool(configurable.max_search_results), crawl_tool])
        logger.info("[executor_node] Web search tools added")
    else:
        logger.info("[executor_node] Web search is disabled, using only local tools")
    
    # Add retriever tool if resources are available (RAG)
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        logger.debug("[executor_node] Adding retriever tool to tools list")
        tools.insert(0, retriever_tool)  # RAG tool gets priority
    
    # Warn if no tools are available
    if not tools:
        logger.warning("[executor_node] No tools available. Agent will operate in pure reasoning mode.")
    
    logger.info(f"[executor_node] Total tools count: {len(tools)}")
    logger.debug(f"[executor_node] Tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]}")
    logger.info(f"[executor_node] enable_web_search={configurable.enable_web_search}")
    
    # Use 'executor' as the agent type
    return await _setup_and_execute_agent_step(
        state,
        config,
        "executor",
        tools,
    )


__all__ = [
    "executor_node",
    "_execute_agent_step",
    "_setup_and_execute_agent_step",
]
