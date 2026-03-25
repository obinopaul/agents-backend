"""
Verifier Node - Implementation.

This module contains the verifier_node that:
1. Analyzes the implementation using an agent with tools
2. Agent calls submit_verification tool to report structured result
3. Routes to __end__ if SUFFICIENT (with walkthrough)
4. Routes to planner if INSUFFICIENT (for new plan iteration)

Uses tool-based structured output instead of response_format to avoid
OpenAI strict mode schema validation issues with middleware tools.
"""

import logging
import os
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command

from backend.src.agents.deep_agents import create_agent as create_deepagent
from backend.src.config.configuration import Configuration
from backend.src.llms.llm import get_llm
from backend.src.module.dev.template import apply_prompt_template, get_prompt_template
from backend.src.tools import (
    crawl_tool,
    get_retriever_tool,
    get_web_search_tool,
)
from backend.src.tools.search import LoggedTavilySearch

from backend.src.module.dev.types import State, VerificationStatus
from .outputs import (
    VerificationResult,
    ImprovementArea,
    submit_verification,
    extract_verification_result,
)
from .subagents import get_subagents

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
# Message Formatters
# =============================================================================

def format_walkthrough_message(result: VerificationResult) -> str:
    """Format a walkthrough message for successful verification."""
    lines = [
        "# ✅ Implementation Verified - SUFFICIENT",
        "",
        "## What Was Built",
        result.walkthrough or "Implementation completed successfully.",
        "",
    ]
    
    if result.files_created:
        lines.append("## Files Created")
        for f in result.files_created:
            lines.append(f"- `{f}`")
        lines.append("")
    
    lines.extend([
        "## Verification Summary",
        result.reasoning,
        "",
        "**Status: COMPLETE** - Ready for delivery.",
    ])
    
    return "\n".join(lines)


def format_improvements_message(result: VerificationResult) -> str:
    """Format an improvements message for insufficient verification."""
    lines = [
        "# ⚠️ Implementation Needs Improvement",
        "",
        "## Areas for Improvement",
    ]
    
    for i, imp in enumerate(result.improvements, 1):
        lines.append(f"### {i}. {imp.area}")
        lines.append(f"**Issue:** {imp.issue}")
        lines.append(f"**Suggestion:** {imp.suggestion}")
        lines.append("")
    
    lines.extend([
        "## Reasoning",
        result.reasoning,
        "",
        "**Status: RETURNING TO PLANNER** - New plan iteration needed.",
    ])
    
    return "\n".join(lines)


# =============================================================================
# Verifier Node - Main Entry Point
# =============================================================================

async def verifier_node(
    state: State, config: RunnableConfig
) -> Command[Literal["planner", "__end__"]]:
    """
    Verifier node - analyzes implementation and decides if sufficient.
    
    This node:
    1. Uses an agent with tools to analyze the implementation
    2. Agent returns structured VerificationResult via response_format
    3. Based on status, routes to __end__ or analyzer with context
    
    Routing:
        - SUFFICIENT → __end__ with walkthrough summary
        - INSUFFICIENT → analyzer with improvement areas (new plan iteration)
    """
    logger.info("Verifier node running.")
    
    configurable = Configuration.from_runnable_config(config)
    
    # -------------------------------------------------------------------------
    # Build Tools
    # -------------------------------------------------------------------------
    
    tools = []
    
    # Add web search if enabled
    if configurable.enable_web_search:
        tools.extend([get_web_search_tool(configurable.max_search_results), crawl_tool])
        logger.info("[verifier_node] Web search tools added")
    
    # Add retriever tool if resources available
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        tools.insert(0, retriever_tool)
    
    # -------------------------------------------------------------------------
    # Load MCP Tools
    # -------------------------------------------------------------------------
    
    mcp_servers = {}
    enabled_tools = {}
    
    if configurable.mcp_settings:
        servers = configurable.mcp_settings.get("servers", {})
        for server_name, server_config in servers.items():
            if (
                server_config.get("enabled_tools")
                and "verifier" in server_config.get("add_to_agents", [])
            ):
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name
    
    # Add dynamic sandbox MCP server if URL provided
    if configurable.mcp_url:
        logger.info(f"Adding dynamic sandbox MCP server at {configurable.mcp_url}")
        mcp_servers["sandbox"] = {
            "transport": "http",
            "url": f"{configurable.mcp_url}/mcp",
        }
    
    # Load MCP tools
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
                    tools.append(tool)
                    logger.debug(f"Loaded MCP tool: {tool.name} from {source}")
            
            logger.info(f"Successfully loaded {len(all_tools)} MCP tools")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
    
    if not tools:
        logger.warning("[verifier_node] No tools available.")
    
    # Add the submit_verification tool (required for structured output)
    tools.append(submit_verification)
    logger.debug("[verifier_node] Added submit_verification tool for structured output")
    
    logger.info(f"[verifier_node] Total tools count: {len(tools)} (includes submit_verification)")
    
    # -------------------------------------------------------------------------
    # Create Agent with Tool-Based Structured Output
    # -------------------------------------------------------------------------
    
    # Get subagents
    subagents = get_subagents(model=get_llm(), include_reviewer=True)
    
    # Middleware configuration - all middleware now work since we use tool-based output
    custom_config = {
        # ===== MIDDLEWARE TOGGLES (all 10 available middleware) ===== 
        "enable_summarization": True,
        "enable_model_retry": False,
        "enable_tool_retry": False,
        "enable_model_call_limit": False,
        "enable_tool_call_limit": False,
        "enable_model_fallback": False,  # Requires all fallback model providers
        "enable_persistent_tasks": False,  # Re-enabled - no strict mode issues now
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
        local_system_prompt = get_prompt_template("verifier")
        logger.debug("Loaded local prompt for verifier")
    except Exception as e:
        logger.warning(f"Failed to load local prompt for verifier: {e}")
        local_system_prompt = None
    
    # Create agent WITHOUT response_format (uses submit_verification tool instead)
    # This avoids OpenAI strict mode schema validation issues with middleware tools
    agent = create_deepagent(
        "verifier",
        "verifier",
        tools,
        prompt_template=None,  # Don't load from root prompts
        system_prompt=local_system_prompt,  # Use locally loaded prompt
        use_default_middleware=True,
        middleware_config=custom_config,
        subagents=subagents,
        # NOTE: No response_format - using submit_verification tool instead
    )
    
    # -------------------------------------------------------------------------
    # Execute Agent
    # -------------------------------------------------------------------------
    
    messages = list(state.get("messages", []))
    
    # Get recursion limit
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
    
    agent_config = {
        "recursion_limit": recursion_limit,
        "configurable": config.get("configurable", {}) if config else {},
    }
    
    try:
        result = await agent.ainvoke(
            {"messages": messages},
            config=agent_config,
        )
    except Exception as e:
        logger.exception(f"Error executing verifier agent: {e}")
        # On error, route back to analyzer
        error_msg = f"[ERROR] Verification failed: {str(e)}"
        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [AIMessage(content=error_msg)],
                "verification_status": VerificationStatus.INSUFFICIENT,
            },
            goto="analyzer",
        )
    
    # -------------------------------------------------------------------------
    # Extract Verification Result from Tool Call
    # -------------------------------------------------------------------------
    
    # Extract VerificationResult from submit_verification tool call in messages
    agent_messages = result.get("messages", [])
    verification_result = extract_verification_result(agent_messages)
    
    if verification_result is None:
        # Fallback if submit_verification was not called
        logger.warning("[verifier_node] submit_verification tool was not called, defaulting to INSUFFICIENT")
        verification_result = VerificationResult(
            status="INSUFFICIENT",
            reasoning="Verification agent did not submit a result. The submit_verification tool was not called.",
            improvements=[
                ImprovementArea(
                    area="Verification Process",
                    issue="The verification agent did not complete its analysis",
                    suggestion="Please review the implementation manually or retry verification",
                )
            ],
        )
    
    logger.info(f"[verifier_node] Verification status: {verification_result.status}")
    
    # -------------------------------------------------------------------------
    # Route Based on Status
    # -------------------------------------------------------------------------
    
    if verification_result.status == "SUFFICIENT":
        # Success! Route to __end__ with walkthrough
        walkthrough_msg = format_walkthrough_message(verification_result)
        
        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [AIMessage(content=walkthrough_msg)],
                "verification_status": VerificationStatus.SUFFICIENT,
                "workflow_iteration_count": 0,  # Reset for next workflow
            },
            goto="__end__",
        )
    else:
        # Needs improvement - check iteration limit first
        current_iteration = state.get("workflow_iteration_count", 0)
        max_iterations = 5  # Default maximum iterations per workflow cycle
        
        if current_iteration >= max_iterations:
            # Reached max iterations - force END to prevent infinite loop
            logger.warning(
                f"[verifier_node] Reached maximum iterations ({max_iterations}). "
                f"Forcing END despite INSUFFICIENT status."
            )
            
            limit_msg = (
                f"## ⚠️ Workflow Iteration Limit Reached\n\n"
                f"The workflow has completed {max_iterations} iterations without achieving "
                f"a SUFFICIENT result. Stopping to prevent infinite loops.\n\n"
                f"**Last Status**: {verification_result.status}\n"
                f"**Reasoning**: {verification_result.reasoning}\n\n"
                f"You may want to try a different approach or provide additional guidance."
            )
            
            return Command(
                update={
                    **preserve_state_meta_fields(state),
                    "messages": [AIMessage(content=limit_msg)],
                    "verification_status": VerificationStatus.INSUFFICIENT,
                    "workflow_iteration_count": 0,  # Reset for next workflow
                },
                goto="__end__",
            )
        
        # Increment iteration count and route back to planner
        new_iteration = current_iteration + 1
        logger.info(
            f"[verifier_node] Iteration {new_iteration}/{max_iterations} - "
            f"Routing to planner for improvements"
        )
        
        improvements_msg = format_improvements_message(verification_result)
        
        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [AIMessage(content=improvements_msg)],
                "verification_status": VerificationStatus.INSUFFICIENT,
                "workflow_iteration_count": new_iteration,  # Increment counter
            },
            goto="planner",
        )


__all__ = [
    "verifier_node",
    "preserve_state_meta_fields",
    "format_walkthrough_message",
    "format_improvements_message",
]
