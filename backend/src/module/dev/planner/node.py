"""
Planner Node - Refactored Implementation.

This module contains the refactored planner_node that follows the robust 
base_node pattern from nodes.py. It uses agent-based execution with full
tool support.

Key Features:
- Full MCP server integration via MultiServerMCPClient
- Agent-based execution (not direct LLM calls)
- Planner for creating plans as Markdown files
- HITL support with structured decisions
- Context compression for large token contexts
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
    human_feedback_tool,
    HITL_TOOL_MARKER,
)
from backend.src.tools.search import LoggedTavilySearch
from backend.src.utils.context_manager import ContextManager, validate_message_content
from backend.src.utils.json_utils import repair_json_output, sanitize_tool_response

# ADJUST THIS 
from backend.src.module.dev.types import State
from backend.src.config.tool_filter_config import apply_tool_filter

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
) -> Command[Literal["coder"]]:
    """
    Execute the planner agent step.
    
    This is the core execution logic that handles:
    - Building agent input with context
    - Applying context compression
    - Managing recursion limits
    - Error handling and diagnostics
    - HITL detection
    
    Routing:
        - On success → coder
    """
    logger.debug(f"[_execute_agent_step] Starting execution for agent: {agent_name}")
    
    messages = list(state.get("messages", []))
    agent_input = {"messages": messages}

    # Get recursion limit from environment
    default_recursion_limit = 1000
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)
        if parsed_limit > 0:
            recursion_limit = parsed_limit
        else:
            recursion_limit = default_recursion_limit
    except ValueError:
        recursion_limit = default_recursion_limit

    logger.info(f"Agent input: {agent_input}")
    
    # Validate message content before invoking agent
    try:
        validated_messages = validate_message_content(agent_input["messages"])
        agent_input["messages"] = validated_messages
    except Exception as validation_error:
        logger.error(f"Error validating agent input messages: {validation_error}")
    
    # Execute the agent using streaming
    try:
        agent_config = {
            "recursion_limit": recursion_limit,
            "configurable": config.get("configurable", {}) if config else {},
        }
        
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
                # Convert merged chunk to AIMessage for storage
                # This preserves all accumulated content and tool_call IDs
                collected_messages.append(current_ai_chunk)
                current_ai_chunk = None
        
        print(f"[DEBUG EXEC] About to call agent.astream() with {len(agent_input.get('messages', []))} messages", flush=True)
        print(f"[DEBUG EXEC] agent_config: {agent_config}", flush=True)
        
        async for chunk in agent.astream(
            agent_input,
            stream_mode=["messages", "updates"],
            subgraphs=True,
            config=agent_config,
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                if isinstance(chunk, dict) and "messages" in chunk:
                    collected_messages = _extract_messages(chunk["messages"])
                continue
            
            _namespace, stream_mode, data = chunk
            
            if stream_mode == "messages":
                if isinstance(data, tuple) and len(data) == 2:
                    message, _metadata = data
                    
                    # Properly merge AIMessageChunks
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
                if isinstance(data, dict):
                    for node_name, node_data in data.items():
                        if isinstance(node_data, dict) and "messages" in node_data:
                            collected_messages = _extract_messages(node_data["messages"])
        
        # Finalize any remaining chunk after streaming completes
        _finalize_current_chunk()
        
        result = {"messages": collected_messages}
        
    except Exception as e:
        import traceback
        import json as json_module
        
        # ===== COMPREHENSIVE ERROR CAPTURE =====
        print(f"\n{'='*60}", flush=True)
        print(f"[ERROR PLANNER] Exception caught in _execute_agent_step", flush=True)
        print(f"[ERROR PLANNER] Exception type: {type(e).__name__}", flush=True)
        print(f"[ERROR PLANNER] Exception str: {str(e)}", flush=True)
        print(f"[ERROR PLANNER] Exception repr: {repr(e)}", flush=True)
        
        # Capture ALL exception attributes
        error_attrs = {}
        for attr in dir(e):
            if not attr.startswith('_'):
                try:
                    val = getattr(e, attr)
                    if not callable(val):
                        error_attrs[attr] = str(val)[:500]  # Truncate long values
                except:
                    pass
        print(f"[ERROR PLANNER] Exception attributes: {error_attrs}", flush=True)
        
        # Try to get API response body
        error_body = ""
        if hasattr(e, 'response'):
            try:
                resp = e.response
                print(f"[ERROR PLANNER] e.response type: {type(resp)}", flush=True)
                if hasattr(resp, 'text'):
                    print(f"[ERROR PLANNER] e.response.text: {resp.text[:1000]}", flush=True)
                    error_body = f"\n\nAPI Response Body:\n{resp.text}"
                if hasattr(resp, 'json'):
                    try:
                        print(f"[ERROR PLANNER] e.response.json(): {resp.json()}", flush=True)
                    except:
                        pass
            except Exception as resp_err:
                print(f"[ERROR PLANNER] Error reading response: {resp_err}", flush=True)
        
        if hasattr(e, 'body'):
            try:
                print(f"[ERROR PLANNER] e.body: {e.body}", flush=True)
                error_body += f"\n\nError Body:\n{e.body}"
            except:
                pass
        
        if hasattr(e, 'message'):
            print(f"[ERROR PLANNER] e.message: {e.message}", flush=True)
        
        print(f"{'='*60}\n", flush=True)
        
        full_error_str = f"{repr(e)}{error_body}"
        logger.error(f"Full exception: {full_error_str}")
        
        error_traceback = traceback.format_exc()
        error_message = f"Error executing {agent_name} agent: {str(e)}"
        logger.exception(error_message)
        print(f"[ERROR PLANNER] Full traceback:\n{error_traceback}", flush=True)
        
        # Include full error details in the response so it's visible in the test output
        detailed_error = f"[ERROR] {agent_name.capitalize()} Agent Error\n\nError Details:\n{full_error_str}\n\nException Attributes:\n{json_module.dumps(error_attrs, indent=2)}"

        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [
                    HumanMessage(content=detailed_error, name=agent_name)
                ],
                "needs_human_feedback": False,
                "hitl_questions": None,
            },
            goto="__end__",
        )

    # Process the result
    response_content = result["messages"][-1].content if result.get("messages") else ""
    response_content = sanitize_tool_response(str(response_content))
    
    logger.debug(f"{agent_name.capitalize()} full response: {response_content}")

    agent_messages = result.get("messages", [])
    
    return Command(
        update={
            **preserve_state_meta_fields(state),
            "messages": agent_messages,
        },
        goto="coder",
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
    *,
    tool_filter_role: str | None = None,
) -> Command[Literal["coder"]]:
    """
    Set up an agent with appropriate tools and execute a step.

    This function handles:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools (default + MCP)
    3. Executes the agent on the current step
    """
    # ===== DEBUG: Log config details =====
    print(f"\n{'='*60}", flush=True)
    print(f"[DEBUG SETUP] _setup_and_execute_agent_step called", flush=True)
    print(f"[DEBUG SETUP] agent_type: {agent_type}", flush=True)
    print(f"[DEBUG SETUP] config: {config}", flush=True)
    print(f"[DEBUG SETUP] config['configurable']: {config.get('configurable', {}) if config else 'None'}", flush=True)
    print(f"[DEBUG SETUP] default_tools count: {len(default_tools)}", flush=True)
    print(f"[DEBUG SETUP] default_tools names: {[t.name if hasattr(t, 'name') else str(t)[:50] for t in default_tools]}", flush=True)
    
    configurable = Configuration.from_runnable_config(config)
    
    print(f"[DEBUG SETUP] configurable.mcp_url: {configurable.mcp_url}", flush=True)
    print(f"[DEBUG SETUP] configurable.thread_id: {configurable.thread_id}", flush=True)
    print(f"[DEBUG SETUP] configurable.codex_url: {configurable.codex_url}", flush=True)
    print(f"[DEBUG SETUP] configurable.mcp_settings: {configurable.mcp_settings}", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    mcp_servers = {}
    enabled_tools = {}

    # Extract MCP server configuration
    if configurable.mcp_settings:
        servers = configurable.mcp_settings.get("servers", {})
        for server_name, server_config in servers.items():
            if (
                server_config.get("enabled_tools")
                and agent_type in server_config.get("add_to_agents", [])
            ):
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name

    # Add dynamic sandbox MCP server if URL is provided
    if configurable.mcp_url:
        logger.info(f"Adding dynamic sandbox MCP server at {configurable.mcp_url}")
        print(f"[DEBUG SETUP] Adding sandbox MCP server at {configurable.mcp_url}", flush=True)
        mcp_servers["sandbox"] = {
            "transport": "http",
            "url": f"{configurable.mcp_url}/mcp",
        }
    else:
        print(f"[DEBUG SETUP] NO mcp_url - MCP tools will NOT be loaded!", flush=True)

    # Build tools list starting with defaults
    loaded_tools = default_tools[:]
    
    # Load MCP tools if any MCP servers are configured
    if mcp_servers:
        try:
            logger.info(f"Loading MCP tools from {len(mcp_servers)} server(s)")
            client = MultiServerMCPClient(mcp_servers)
            all_tools = await client.get_tools()
            
            for tool in all_tools:
                is_static_allowed = tool.name in enabled_tools
                is_dynamic_sandbox = bool(configurable.mcp_url)
                
                if is_static_allowed or is_dynamic_sandbox:
                    source = enabled_tools.get(tool.name, "sandbox" if is_dynamic_sandbox else "unknown")
                    tool.description = f"Powered by '{source}'.\n{tool.description}"
                    loaded_tools.append(tool)
                    logger.debug(f"Loaded MCP tool: {tool.name} from {source}")
            
            logger.info(f"Successfully loaded {len(loaded_tools) - len(default_tools)} MCP tools")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
    
    # Add CodexAgentTool if available
    if configurable.codex_url:
        try:
            from backend.src.agents.tools.codex_agent import create_codex_tool
            codex_tool = create_codex_tool(
                codex_url=f"{configurable.codex_url}/messages",
                timeout=300,
                session_id=configurable.thread_id,
            )
            loaded_tools.append(codex_tool)
            logger.info(f"[CODEX] Added CodexAgentTool")
        except Exception as codex_error:
            logger.warning(f"[CODEX] Failed to add CodexAgentTool: {codex_error}")

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
    
    # Load system prompt from local prompts folder
    try:
        local_system_prompt = get_prompt_template(agent_type)
        logger.debug(f"Loaded local prompt for {agent_type}")
        print(f"[DEBUG SETUP] Loaded prompt for {agent_type}, length: {len(local_system_prompt) if local_system_prompt else 0}", flush=True)
    except Exception as e:
        logger.warning(f"Failed to load local prompt for {agent_type}: {e}")
        print(f"[DEBUG SETUP] FAILED to load prompt for {agent_type}: {e}", flush=True)
        local_system_prompt = None
    
    # ===== DEBUG: Log final tools being passed to agent =====
    print(f"\n{'='*60}", flush=True)
    print(f"[DEBUG SETUP] Creating agent with {len(loaded_tools)} total tools:", flush=True)
    for i, tool in enumerate(loaded_tools):
        tool_name = getattr(tool, 'name', str(tool)[:50])
        tool_desc = getattr(tool, 'description', 'N/A')[:100]
        print(f"[DEBUG SETUP]   {i+1}. {tool_name}: {tool_desc}...", flush=True)
        # Try to log tool schema if available
        if hasattr(tool, 'args_schema'):
            try:
                schema = tool.args_schema.schema() if hasattr(tool.args_schema, 'schema') else str(tool.args_schema)
                print(f"[DEBUG SETUP]      Schema: {str(schema)[:200]}...", flush=True)
            except Exception as schema_err:
                print(f"[DEBUG SETUP]      Schema error: {schema_err}", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    try:
        agent = create_deepagent(
            agent_type,
            agent_type,
            loaded_tools,
            prompt_template=None,  # Don't load from root prompts
            system_prompt=local_system_prompt,  # Use locally loaded prompt
            use_default_middleware=True,
            middleware_config=custom_config
        )
        print(f"[DEBUG SETUP] Agent created successfully, type: {type(agent)}", flush=True)
    except Exception as agent_err:
        print(f"[DEBUG SETUP] FAILED to create agent: {agent_err}", flush=True)
        import traceback
        print(f"[DEBUG SETUP] Agent creation traceback:\n{traceback.format_exc()}", flush=True)
        raise
    
    return await _execute_agent_step(state, agent, agent_type, config)


# =============================================================================
# Planner Node - Main Entry Point
# =============================================================================

async def planner_node(
    state: State, config: RunnableConfig
) -> Command[Literal["coder"]]:
    """
    Planner node - uses agent to process user query and data files.
    
    This is the entry point for the planner workflow that:
    1. Processes the user query and understands requirements
    2. Invokes Planner to create a robust plan
    3. Saves plan as Markdown file (plan_iteration_N.md)
    
    Routing:
        - On success → coder (to implement the plan)
    """
    logger.info("Planner node running.")
    
    # DEBUG: Print to stdout with flush to ensure logs are visible
    print(f"[DEBUG PLANNER] planner_node called", flush=True)
    print(f"[DEBUG PLANNER] config: {config}", flush=True)
    print(f"[DEBUG PLANNER] config['configurable'] if exists: {config.get('configurable', {}) if config else 'None'}", flush=True)
    
    configurable = Configuration.from_runnable_config(config)
    
    print(f"[DEBUG PLANNER] configurable.mcp_url: {configurable.mcp_url}", flush=True)
    print(f"[DEBUG PLANNER] configurable.thread_id: {configurable.thread_id}", flush=True)
    print(f"[DEBUG PLANNER] state messages count: {len(state.get('messages', []))}", flush=True)
    
    # Build tools list
    tools = []
    
    # Add human feedback tool if enabled
    if configurable.enable_feedback_tool:
        tools.append(human_feedback_tool)
        logger.info("[planner_node] Human feedback tool added for HITL support")

    # Add research tools if enabled
    if configurable.enable_added_tools:
        tools.extend([
            people_search_tool, company_search_tool, paper_search_tool, 
            get_paper_details_tool, search_authors_tool, get_author_details_tool, 
            get_author_papers_tool, semantic_scholar_search_tool, arxiv_search_tool, 
            pubmed_central_tool, create_view_image_tool()
        ])
        logger.info("[planner_node] Added external tools")
    
    # Add web search tools if enabled
    if configurable.enable_web_search:
        tools.extend([get_web_search_tool(configurable.max_search_results), crawl_tool])
        logger.info("[planner_node] Web search tools added")
    
    # Add retriever tool if resources are available
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        tools.insert(0, retriever_tool)
    
    if not tools:
        logger.warning("[planner_node] No tools available.")
    
    logger.info(f"[planner_node] Total tools count: {len(tools)}")
    
    return await _setup_and_execute_agent_step(
        state,
        config,
        "planner",
        tools,
    )


__all__ = [
    "planner_node",
    "_execute_agent_step",
    "_setup_and_execute_agent_step",
    "preserve_state_meta_fields",
]
