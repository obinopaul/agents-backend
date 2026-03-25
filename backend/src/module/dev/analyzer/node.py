"""
Analyzer Node - Refactored Implementation.

This module contains the refactored analyzer_node that follows the robust 
base_node pattern from nodes.py. It uses agent-based execution with full
tool support and includes a workflow subagent for complex development tasks.

Key Features:
- Full MCP server integration via MultiServerMCPClient
- Agent-based execution (not direct LLM calls)
- Workflow subagent (CompiledSubAgent) for complex development tasks
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
from .subagents import get_subagents

# Import CompiledSubAgent for workflow integration (using local fork with config propagation fix)
from backend.src.module.subagents import CompiledSubAgent, SUBAGENT_AVAILABLE

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

from backend.app.agent.models import (
    HITLDecisionType,
    HITLRequest,
    HITLResponse,
    ActionRequest,
    ReviewConfig,
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
        "needs_human_feedback": state.get("needs_human_feedback", False),
        "hitl_questions": state.get("hitl_questions", None),
    }


# =============================================================================
# HITL Detection and Parsing
# =============================================================================

def _parse_hitl_marker(content: str) -> Optional[Dict[str, Any]]:
    """Parse the HITL marker from tool response to extract questions."""
    if HITL_TOOL_MARKER not in content:
        return None
    
    try:
        json_part = content.split(HITL_TOOL_MARKER, 1)[1].strip()
        return json.loads(json_part)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Failed to parse HITL marker: {e}")
        return None


def _detect_feedback_request(messages: list, agent_name: str = "agent") -> tuple[bool, Optional[List[str]]]:
    """Detect if the agent explicitly requested human feedback."""
    for message in messages:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.get('name') == "request_human_input":
                    questions = tool_call.get('args', {}).get('questions', [])
                    logger.info(f"[HITL] {agent_name} called request_human_input with {len(questions)} question(s)")
                    return True, questions
                
                # if tool_call.get('name') == "__interrupt__":
                #     questions = message.content
                #     logger.info(f"[HITL] {agent_name} called __interrupt__")
                #     return True, questions
        
        if isinstance(message, ToolMessage):
            content = str(message.content) if message.content else ""
            if HITL_TOOL_MARKER in content:
                parsed = _parse_hitl_marker(content)
                if parsed:
                    questions = parsed.get('questions', [])
                    logger.info(f"[HITL] {agent_name} HITL request detected: {len(questions)} question(s)")
                    return True, questions
    
    return False, None


# =============================================================================
# Agent Execution Helpers
# =============================================================================

async def _execute_agent_step(
    state: State, agent, agent_name: str, config: RunnableConfig = None
) -> Command[Literal["human_feedback", "__end__"]]:
    """
    Execute the analyzer agent step.
    
    This is the core execution logic that handles:
    - Building agent input with context
    - Applying context compression
    - Managing recursion limits
    - Error handling and diagnostics
    - HITL detection
    
    Routing:
        - If HITL requested → human_feedback
        - On success → coder
        - On error → __end__
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
                # Append merged chunk (preserves tool_call IDs from first chunk)
                collected_messages.append(current_ai_chunk)
                current_ai_chunk = None
        
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
                if isinstance(data, dict):
                    for node_name, node_data in data.items():
                        if isinstance(node_data, dict) and "messages" in node_data:
                            collected_messages = _extract_messages(node_data["messages"])
        
        # Finalize any remaining chunk after streaming completes
        _finalize_current_chunk()
        
        result = {"messages": collected_messages}
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"Error executing {agent_name} agent: {str(e)}"
        logger.exception(error_message)
        
        detailed_error = f"[ERROR] {agent_name.capitalize()} Agent Error\n\nError Details:\n{str(e)}"

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
    
    # HITL Routing Decision
    needs_feedback, hitl_questions = _detect_feedback_request(agent_messages, agent_name)
    
    configurable = Configuration.from_runnable_config(config) if config else Configuration()
    
    if configurable.always_require_feedback:
        needs_feedback = True
        if not hitl_questions:
            hitl_questions = ["Please review the agent's response."]
    
    # Determine next node
    if needs_feedback:
        next_node = "human_feedback"
        logger.info(f"[HITL] Routing to human_feedback. Questions: {hitl_questions}")
    else:
        # Route to end - complex work is handled via workflow subagent (task() tool)
        next_node = "__end__"
        logger.info(f"[Analyzer] Analysis complete, routing to end")

    return Command(
        update={
            **preserve_state_meta_fields(state),
            "messages": agent_messages,
            "needs_human_feedback": needs_feedback,
            "hitl_questions": hitl_questions,
        },
        goto=next_node,
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
    *,
    tool_filter_role: str | None = None,
) -> Command[Literal["human_feedback", "__end__"]]:
    """
    Set up an agent with appropriate tools and execute a step.

    This function handles:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools (default + MCP)
    3. Adds DS* subagents (including planner)
    4. Executes the agent on the current step
    """
    configurable = Configuration.from_runnable_config(config)
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
        mcp_servers["sandbox"] = {
            "transport": "http",
            "url": f"{configurable.mcp_url}/mcp",
        }

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
        "enable_persistent_tasks": True,  # Requires store - disable for local testing
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

    # Get subagents including planner
    subagents = get_subagents(model=get_llm(), include_planner=True)
    
    # Add workflow subgraph as CompiledSubAgent for complex development tasks
    if SUBAGENT_AVAILABLE and CompiledSubAgent is not None:
        try:
            from backend.src.module.dev.sub_builder import graph as workflow_graph
            
            workflow_subagent = CompiledSubAgent(
                name="development-workflow",
                description=(
                    "Execute complex development tasks that require code creation, "
                    "execution, and verification. Use this when the user asks for: "
                    "code/app development, data analysis with code, file creation, "
                    "or multi-step technical work. This workflow handles: "
                    "planning → coding → execution → verification with automatic iteration."
                ),
                runnable=workflow_graph,
            )
            subagents.append(workflow_subagent)
            logger.info("[analyzer_node] Added development-workflow CompiledSubAgent")
        except Exception as e:
            logger.warning(f"[analyzer_node] Failed to add workflow subagent: {e}")
    else:
        logger.warning("[analyzer_node] CompiledSubAgent not available, skipping workflow subagent")
    
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
# Analyzer Node - Main Entry Point
# =============================================================================

async def analyzer_node(
    state: State, config: RunnableConfig
) -> Command[Literal["human_feedback", "__end__"]]:
    """
    Analyzer node - uses agent to process user query and data files.
    
    This is the entry point for the analyzer workflow that:
    1. Processes the user query and understands requirements
    2. Analyzes data files in the sandbox (if any exist)
    3. Invokes Planner subagent to create a robust plan
    4. Saves plan as Markdown file (plan_iteration_N.md)
    
    Routing:
        - If HITL requested → human_feedback
        - On success → coder (to implement the plan)
        - On error → __end__
    """
    logger.info("Analyzer node running.")
    
    configurable = Configuration.from_runnable_config(config)
    
    # Build tools list
    tools = []
    
    # Add human feedback tool if enabled
    if configurable.enable_feedback_tool:
        tools.append(human_feedback_tool)
        logger.info("[analyzer_node] Human feedback tool added for HITL support")

    # Add research tools if enabled
    if configurable.enable_added_tools:
        tools.extend([
            people_search_tool, company_search_tool, paper_search_tool, 
            get_paper_details_tool, search_authors_tool, get_author_details_tool, 
            get_author_papers_tool, semantic_scholar_search_tool, arxiv_search_tool, 
            pubmed_central_tool, create_view_image_tool()
        ])
        logger.info("[analyzer_node] Added external tools")
    
    # Add web search tools if enabled
    if configurable.enable_web_search:
        tools.extend([get_web_search_tool(configurable.max_search_results), crawl_tool])
        logger.info("[analyzer_node] Web search tools added")
    
    # Add retriever tool if resources are available
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        tools.insert(0, retriever_tool)
    
    if not tools:
        logger.warning("[analyzer_node] No tools available.")
    
    logger.info(f"[analyzer_node] Total tools count: {len(tools)}")
    
    return await _setup_and_execute_agent_step(
        state,
        config,
        "analyzer",
        tools,
    )


# =============================================================================
# Human Feedback Node
# =============================================================================

def human_feedback_node(
    state: State, config: RunnableConfig
) -> Command[Literal["analyzer", "__end__"]]:
    """
    Human feedback node with structured HITL decision handling.
    
    Decisions:
        - APPROVE: Continue to coder
        - EDIT: Loop back to analyzer
        - REJECT: End workflow
    """
    logger.info("Human feedback node running with structured HITL.")
    
    hitl_questions = state.get("hitl_questions", None)
    
    hitl_request = {
        "questions": hitl_questions or [],
        "allowed_decisions": ["approve", "edit", "reject"],
        "context": {"message_count": len(state.get("messages", []))},
    }
    
    if hitl_questions:
        hitl_request["prompt"] = "The agent needs your input on the following:"
    else:
        hitl_request["prompt"] = "Review the agent's response and choose an action:"
    
    response = interrupt(hitl_request)
    
    logger.info(f"HITL response received: {response}")
    
    # Handle None - assume approval
    if not response:
        return Command(
            update={
                "needs_human_feedback": False,
                "hitl_questions": None,
                **preserve_state_meta_fields(state),
            },
            goto="__end__"
        )
    
    # Handle string responses
    if isinstance(response, str):
        response_upper = response.strip().upper()
        
        if response_upper in ("APPROVED", "ACCEPTED", "OK", "YES"):
            return Command(
                update={"needs_human_feedback": False, "hitl_questions": None},
                goto="__end__"
            )
        
        if response_upper in ("REJECTED", "REJECT", "NO", "CANCEL"):
            messages = list(state.get("messages", []))
            messages.append(HumanMessage(content="[REJECTED] User rejected.", name="human_decision"))
            return Command(
                update={
                    "messages": messages,
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                },
                goto="__end__"
            )
        
        # Treat as feedback - loop back to analyzer
        messages = list(state.get("messages", []))
        messages.append(HumanMessage(content=response.strip(), name="human_feedback"))
        return Command(
            update={"messages": messages, "needs_human_feedback": False, "hitl_questions": None},
            goto="analyzer",
        )
    
    # Handle dict responses
    if isinstance(response, dict):
        decision = response.get("decision", "").lower()
        feedback = response.get("feedback", "")
        answers = response.get("answers", [])
        
        if decision == "approve":
            return Command(
                update={"needs_human_feedback": False, "hitl_questions": None},
                goto="__end__"
            )
        
        if decision == "reject":
            messages = list(state.get("messages", []))
            rejection_msg = f"[REJECTED] User rejected. Reason: {feedback}" if feedback else "[REJECTED]"
            messages.append(HumanMessage(content=rejection_msg, name="human_decision"))
            return Command(
                update={
                    "messages": messages,
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                },
                goto="__end__"
            )
        
        # Edit or answers provided - loop back
        if decision == "edit" or answers or feedback:
            messages = list(state.get("messages", []))
            content_parts = []
            if feedback:
                content_parts.append(feedback)
            if answers:
                for i, answer in enumerate(answers):
                    q = hitl_questions[i] if hitl_questions and i < len(hitl_questions) else f"Q{i+1}"
                    content_parts.append(f"Q: {q}\nA: {answer}")
            
            combined = "\n\n".join(content_parts) if content_parts else "Please continue."
            messages.append(HumanMessage(content=combined, name="human_feedback"))
            
            return Command(
                update={"messages": messages, "needs_human_feedback": False, "hitl_questions": None},
                goto="analyzer",
            )
    
    # Fallback
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=str(response), name="human_feedback"))
    return Command(
        update={"messages": messages, "needs_human_feedback": False, "hitl_questions": None},
        goto="analyzer",
    )


__all__ = [
    "analyzer_node",
    "human_feedback_node",
    "_execute_agent_step",
    "_setup_and_execute_agent_step",
    "preserve_state_meta_fields",
]
