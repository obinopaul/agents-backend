"""
Simplified Graph Nodes for a Robust LangGraph Agent.

This module provides the node implementations for a streamlined 3-node graph:
1. background_investigator - Optional initial web search investigation  
2. base - Main agent node with full tool support (MCP, web search, RAG, Python REPL, HITL)
3. human_feedback - Human-in-the-loop with structured decisions (approve/edit/reject)

Key Features:
- Full MCP server integration via MultiServerMCPClient
- All tools: web_search, crawl, RAG retriever, python_repl, request_human_input
- Context compression for large token contexts
- Structured HITL with proper decision types
- Web search validation
- Prompt templates
"""

import json
import logging
import os
from functools import partial
from typing import Annotated, Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command, interrupt

from backend.src.agents import create_agent
from backend.src.config.configuration import Configuration
from backend.src.llms.llm import get_llm, get_llm_token_limit
from backend.src.prompts.template import apply_prompt_template
from backend.src.tools import (
    crawl_tool,
    get_retriever_tool,
    get_web_search_tool,
    human_feedback_tool,
    python_repl_tool,
    HITL_TOOL_MARKER,
)
from backend.src.tools.search import LoggedTavilySearch
from backend.src.utils.context_manager import ContextManager, validate_message_content
from backend.src.utils.json_utils import repair_json_output, sanitize_tool_response

from backend.src.config import SELECTED_SEARCH_ENGINE, SearchEngine
from backend.src.graph.types import State
from backend.src.graph.utils import (
    get_message_content,
    is_user_message,
)

# Import HITL models for structured decision handling
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
    
    These fields are critical for workflow continuity and should be explicitly
    included in all Command.update dicts to prevent them from reverting to defaults.
    
    Args:
        state: Current state object
        
    Returns:
        Dict of meta fields to preserve
    """
    return {
        "resources": state.get("resources", []),
        "enable_background_investigation": state.get("enable_background_investigation", True),
        # HITL fields - preserve across transitions
        "needs_human_feedback": state.get("needs_human_feedback", False),
        "hitl_questions": state.get("hitl_questions", None),
    }


# =============================================================================
# Background Investigation Node
# =============================================================================

def background_investigation_node(state: State, config: RunnableConfig):
    """
    Background investigation node that performs initial web search.
    
    This node runs before the main agent to gather context about the user's query.
    It uses either Tavily or a configured search engine to fetch relevant results.
    Uses the last user message as the search query.
    
    Args:
        state: Current workflow state
        config: Runnable configuration with settings
        
    Returns:
        Dict with background_investigation_results field
    """
    logger.info("Background investigation node is running.")
    configurable = Configuration.from_runnable_config(config)

    # Background investigation relies on web search; skip entirely when web search is disabled
    if not configurable.enable_web_search:
        logger.info("Web search is disabled, skipping background investigation.")
        return {"background_investigation_results": json.dumps([], ensure_ascii=False)}
    
    # Also skip if explicitly disabled in state
    if not state.get("enable_background_investigation", True):
        logger.info("Background investigation is disabled in state, skipping.")
        return {"background_investigation_results": json.dumps([], ensure_ascii=False)}

    # Get the last user message as the search query
    messages = state.get("messages", [])
    query = ""
    for msg in reversed(messages):
        # Handle both dict and message object formats
        if isinstance(msg, dict):
            if msg.get("role") in ("user", "human"):
                query = msg.get("content", "")
                break
        elif hasattr(msg, "content"):
            # Check if it's a HumanMessage
            msg_type = type(msg).__name__
            if msg_type == "HumanMessage" or getattr(msg, "type", "") == "human":
                query = str(msg.content) if msg.content else ""
                break
    
    if not query:
        logger.warning("No user message found for background investigation.")
        return {"background_investigation_results": json.dumps([], ensure_ascii=False)}
    
    logger.info(f"Background investigation query: {query[:100]}...")
    background_investigation_results = []
    
    if SELECTED_SEARCH_ENGINE == SearchEngine.TAVILY.value:
        searched_content = LoggedTavilySearch(
            max_results=configurable.max_search_results
        ).invoke(query)
        
        # Check if the searched_content is a tuple, then we need to unpack it
        if isinstance(searched_content, tuple):
            searched_content = searched_content[0]
        
        # Handle string JSON response (new format from fixed Tavily tool)
        if isinstance(searched_content, str):
            try:
                parsed = json.loads(searched_content)
                if isinstance(parsed, dict) and "error" in parsed:
                    logger.error(f"Tavily search error: {parsed['error']}")
                    background_investigation_results = []
                elif isinstance(parsed, list):
                    background_investigation_results = [
                        f"## {elem.get('title', 'Untitled')}\n\n{elem.get('content', 'No content')}" 
                        for elem in parsed
                    ]
                else:
                    logger.error(f"Unexpected Tavily response format: {searched_content}")
                    background_investigation_results = []
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Tavily response as JSON: {searched_content}")
                background_investigation_results = []
        # Handle legacy list format
        elif isinstance(searched_content, list):
            background_investigation_results = [
                f"## {elem['title']}\n\n{elem['content']}" for elem in searched_content
            ]
            return {
                "background_investigation_results": "\n\n".join(
                    background_investigation_results
                )
            }
        else:
            logger.error(
                f"Tavily search returned malformed response: {searched_content}"
            )
            background_investigation_results = []
    else:
        # Use configured web search tool
        background_investigation_results = get_web_search_tool(
            configurable.max_search_results
        ).invoke(query)
    
    return {
        "background_investigation_results": json.dumps(
            background_investigation_results, ensure_ascii=False
        )
    }


# =============================================================================
# Validation Utilities
# =============================================================================

def validate_web_search_usage(messages: list, agent_name: str = "agent") -> bool:
    """
    Validate if the agent has used the web search tool during execution.
    
    Args:
        messages: List of messages from the agent execution
        agent_name: Name of the agent (for logging purposes)
        
    Returns:
        bool: True if web search tool was used, False otherwise
    """
    web_search_used = False
    
    for message in messages:
        # Check for ToolMessage instances indicating web search was used
        if isinstance(message, ToolMessage) and message.name == "web_search":
            web_search_used = True
            logger.info(f"[VALIDATION] {agent_name} received ToolMessage from web_search tool")
            break
            
        # Check for AIMessage content that mentions tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.get('name') == "web_search":
                    web_search_used = True
                    logger.info(f"[VALIDATION] {agent_name} called web_search tool")
                    break
            # break outer loop if web search was used
            if web_search_used:
                break
                    
        # Check for message name attribute
        if hasattr(message, 'name') and message.name == "web_search":
            web_search_used = True
            logger.info(f"[VALIDATION] {agent_name} used web_search tool")
            break
    
    if not web_search_used:
        logger.warning(f"[VALIDATION] {agent_name} did not use web_search tool")
        
    return web_search_used


# =============================================================================
# HITL Detection and Parsing
# =============================================================================

def _parse_hitl_marker(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse the HITL marker from tool response to extract questions.
    
    Format: [HITL_REQUEST]{"questions": ["question1", "question2"]}
    
    Returns:
        Dict with 'questions' list if valid, None otherwise
    """
    if HITL_TOOL_MARKER not in content:
        return None
    
    try:
        json_part = content.split(HITL_TOOL_MARKER, 1)[1].strip()
        return json.loads(json_part)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Failed to parse HITL marker: {e}")
        return None


def _detect_feedback_request(messages: list, agent_name: str = "agent") -> tuple[bool, Optional[List[str]]]:
    """
    Detect if the agent explicitly requested human feedback.
    
    This checks for:
    1. Use of the request_human_input tool (new structured format)
    2. The [HITL_REQUEST] marker in tool responses
    
    Args:
        messages: List of messages from agent execution
        agent_name: Name of the agent (for logging)
        
    Returns:
        Tuple of (needs_feedback: bool, questions: Optional[List[str]])
        - needs_feedback: True if HITL was requested
        - questions: List of questions to ask the user, or None
    """
    for message in messages:
        # Check for tool calls to request_human_input
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.get('name') == "request_human_input":
                    questions = tool_call.get('args', {}).get('questions', [])
                    logger.info(f"[HITL] {agent_name} called request_human_input with {len(questions)} question(s)")
                    return True, questions
        
        # Check for ToolMessage with HITL marker
        if isinstance(message, ToolMessage):
            content = str(message.content) if message.content else ""
            
            # New structured format
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
    Helper function to execute the base agent step.
    
    This is the core execution logic that handles:
    - Building agent input with context
    - Applying context compression
    - Managing recursion limits
    - Error handling and diagnostics
    - Web search validation
    - HITL detection: Routes to human_feedback only if agent requests it
    
    Args:
        state: Current workflow state
        agent: The configured agent to execute
        agent_name: Name of the agent for logging
        config: Runnable configuration
        
    Returns:
        Command to update state and route to human_feedback
    """
    logger.debug(f"[_execute_agent_step] Starting execution for agent: {agent_name}")
    
    # Build agent input messages - convert dict messages to proper message objects
    raw_messages = list(state.get("messages", []))
    messages = []
    for msg in raw_messages:
        if isinstance(msg, dict):
            # Convert dict to proper message object
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "human"):
                messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        else:
            # Already a message object
            messages.append(msg)
    
    # Add background investigation context if available
    if state.get("background_investigation_results"):
        bg_results = state.get("background_investigation_results")
        # Check if already added to prevent duplication
        if not any(
            isinstance(m, HumanMessage) and "background investigation" in str(m.content).lower() 
            for m in messages
        ):
            messages.append(
                HumanMessage(
                    content=f"# Background Investigation Results\n\n{bg_results}",
                    name="system"
                )
            )

    # Add resources context for RAG
    if state.get("resources"):
        resources_info = "**The user mentioned the following resource files:**\n\n"
        for resource in state.get("resources"):
            resources_info += f"- {resource.title} ({resource.description})\n"

        messages.append(
            HumanMessage(
                content=resources_info
                + "\n\n"
                + "You MUST use the **local_search_tool** to retrieve the information from the resource files.",
                name="system"
            )
        )

    # Add citation reminder
    messages.append(
        HumanMessage(
            content="IMPORTANT: DO NOT include inline citations in the text. Instead, track all sources and include a References section at the end using link reference format. Include an empty line between each citation for better readability. Use this format for each reference:\n- [Source Title](URL)\n\n- [Another Source](URL)",
            name="system",
        )
    )

    agent_input = {"messages": messages}

    # Get recursion limit from environment
    default_recursion_limit = 25
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
    
    # Apply context compression to prevent token overflow
    llm_token_limit = get_llm_token_limit()
    if llm_token_limit:
        try:
            token_count_before = sum(
                len(str(msg.content).split()) for msg in agent_input.get("messages", []) if hasattr(msg, "content")
            )
            compressed_state = ContextManager(llm_token_limit, preserve_prefix_message_count=3).compress_messages(
                {"messages": agent_input["messages"]}
            )
            agent_input["messages"] = compressed_state.get("messages", [])
            token_count_after = sum(
                len(str(msg.content).split()) for msg in agent_input.get("messages", []) if hasattr(msg, "content")
            )
            logger.info(
                f"Context compression for {agent_name}: {len(compressed_state.get('messages', []))} messages, "
                f"estimated tokens before: ~{token_count_before}, after: ~{token_count_after}"
            )
        except Exception as compression_error:
            logger.warning(f"Context compression failed: {compression_error}")
    
    # Execute the agent
    try:
        result = await agent.ainvoke(
            input=agent_input, config={"recursion_limit": recursion_limit}
        )
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

        # On error, end the workflow (user can start a new conversation)
        return Command(
            update={
                **preserve_state_meta_fields(state),
                "messages": [
                    HumanMessage(
                        content=detailed_error,
                        name=agent_name,
                    )
                ],
                "needs_human_feedback": False,
                "hitl_questions": None,
            },
            goto="__end__",
        )

    # Process the result
    response_content = result["messages"][-1].content if result.get("messages") else ""
    
    # Sanitize response to remove extra tokens and truncate if needed
    response_content = sanitize_tool_response(str(response_content))
    
    logger.debug(f"{agent_name.capitalize()} full response: {response_content}")

    # Validate web search usage if enforcement is enabled
    web_search_validated = True
    validation_info = ""

    configurable = Configuration.from_runnable_config(config) if config else Configuration()
    # Skip validation if web search is disabled (user intentionally disabled it)
    if configurable.enforce_researcher_search and configurable.enable_web_search:
        web_search_validated = validate_web_search_usage(result.get("messages", []), agent_name)
        
        # If web search was not used, add a warning to the response
        if not web_search_validated:
            logger.warning(f"[VALIDATION] {agent_name} did not use web_search tool. Adding reminder to response.")
            validation_info = (
                "\n\n[WARNING] This response was completed without using the web_search tool. "
                "Please verify that the information provided is accurate and up-to-date."
            )

    # Include all messages from agent result to preserve intermediate tool calls/results
    agent_messages = result.get("messages", [])
    logger.debug(
        f"{agent_name.capitalize()} returned {len(agent_messages)} messages. "
        f"Message types: {[type(msg).__name__ for msg in agent_messages]}"
    )
    
    # Count tool messages for logging
    tool_message_count = sum(1 for msg in agent_messages if isinstance(msg, ToolMessage))
    if tool_message_count > 0:
        logger.info(
            f"{agent_name.capitalize()} agent made {tool_message_count} tool calls. "
            f"All tool results will be preserved and streamed to frontend."
        )

    # ==========================================================================
    # HITL Routing Decision
    # ==========================================================================
    # Determine whether to route to human_feedback or __end__
    # 
    # Route to human_feedback if:
    # 1. Agent explicitly called request_human_input tool
    # 2. Configuration has always_require_feedback=True (legacy mode)
    #
    # Otherwise, route to __end__ (task complete)
    # ==========================================================================
    
    needs_feedback, hitl_questions = _detect_feedback_request(agent_messages, agent_name)
    
    # Check for legacy mode (always require feedback)
    if configurable.always_require_feedback:
        logger.info(f"[HITL] always_require_feedback is enabled, routing to human_feedback")
        needs_feedback = True
        if not hitl_questions:
            hitl_questions = ["Please review the agent's response."]
    
    # Determine next node
    if needs_feedback:
        next_node = "human_feedback"
        logger.info(f"[HITL] Routing to human_feedback. Questions: {hitl_questions}")
    else:
        next_node = "__end__"
        logger.info(f"[HITL] Task complete, routing to __end__")

    return Command(
        update={
            **preserve_state_meta_fields(state),  # Base preserved fields first
            "messages": agent_messages,
            "needs_human_feedback": needs_feedback,
            "hitl_questions": hitl_questions,  # List of questions for the user
        },
        goto=next_node,
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
) -> Command[Literal["human_feedback", "__end__"]]:
    """
    Helper function to set up an agent with appropriate tools and execute a step.

    This function handles the common logic for agent setup:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools (default + MCP)
    3. Executes the agent on the current step

    Args:
        state: The current state
        config: The runnable config
        agent_type: The type of agent (e.g., "researcher", "base")
        default_tools: The default tools to add to the agent

    Returns:
        Command to update state and go to human_feedback
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

    # Create context compression hook
    llm_token_limit = get_llm_token_limit()
    pre_model_hook = partial(ContextManager(llm_token_limit, 3).compress_messages)
    
    # Create the agent with all tools
    logger.info(f"Creating agent '{agent_type}' with {len(loaded_tools)} tools")
    agent = create_agent(
        agent_type,
        agent_type,
        loaded_tools,
        agent_type,  # Uses prompt template matching agent type
        # pre_model_hook,
        # interrupt_before_tools=configurable.interrupt_before_tools,
    )
    
    return await _execute_agent_step(state, agent, agent_type, config)


# =============================================================================
# Base Node - Main Agent Execution
# =============================================================================

async def base_node(
    state: State, config: RunnableConfig
) -> Command[Literal["human_feedback", "__end__"]]:
    """
    Base node that handles the robust execution of agent tasks.
    
    This is the main agent node that:
    1. Configures all available tools (web search, RAG, crawl, Python REPL, HITL)
    2. Loads MCP tools if configured
    3. Creates a ReAct agent with the configured tools
    4. Executes the agent and processes results
    5. Routes to human_feedback ONLY if agent requests it, otherwise to __end__
    
    The node uses the 'researcher' agent type for robust tool usage and prompting.
    
    Routing Logic:
    - If agent calls request_human_feedback tool → human_feedback
    - If always_require_feedback config is True → human_feedback (legacy mode)
    - Otherwise → __end__ (task complete)
    
    Args:
        state: Current workflow state with messages and context
        config: Runnable configuration with tool settings
        
    Returns:
        Command to update state and route to human_feedback or __end__
    """
    logger.info("Base node running.")
    
    configurable = Configuration.from_runnable_config(config)
    logger.debug(f"[base_node] Max search results: {configurable.max_search_results}")
    
    # Build tools list based on configuration
    tools = []
    
    # Add human feedback tool if enabled (allows agent to request clarification)
    if configurable.enable_feedback_tool:
        tools.append(human_feedback_tool)
        logger.info("[base_node] Human feedback tool added for HITL support")
    
    # Add web search and crawl tools only if web search is enabled
    if configurable.enable_web_search:
        tools.extend([get_web_search_tool(configurable.max_search_results), crawl_tool])
        logger.info("[base_node] Web search tools added")
    else:
        logger.info("[base_node] Web search is disabled, using only local tools")
    
    # Add Python REPL tool for code execution
    tools.append(python_repl_tool)
    logger.debug("[base_node] Python REPL tool added")
    
    # Add retriever tool if resources are available (RAG)
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        logger.debug("[base_node] Adding retriever tool to tools list")
        tools.insert(0, retriever_tool)  # RAG tool gets priority
    
    # Warn if no tools are available
    if not tools:
        logger.warning("[base_node] No tools available. Agent will operate in pure reasoning mode.")
    
    logger.info(f"[base_node] Total tools count: {len(tools)}")
    logger.debug(f"[base_node] Tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]}")
    logger.info(f"[base_node] enforce_researcher_search={configurable.enforce_researcher_search}, "
                f"enable_web_search={configurable.enable_web_search}")
    logger.info(f"[base_node] HITL config: always_require_feedback={configurable.always_require_feedback}, "
                f"enable_feedback_tool={configurable.enable_feedback_tool}")
    
    # Use 'general' as the agent type for ALL tools including slides, files, etc.
    # The 'general' prompt emphasizes actually calling tools rather than just describing
    return await _setup_and_execute_agent_step(
        state,
        config,
        "general",  # General-purpose agent with full tool usage
        tools,
    )


# =============================================================================
# Human Feedback Node
# =============================================================================

def human_feedback_node(
    state: State, config: RunnableConfig
) -> Command[Literal["base", "__end__"]]:
    """
    Human feedback node with structured HITL decision handling.
    
    This node provides a human-in-the-loop checkpoint where:
    - The user reviews agent's work or answers agent's questions
    - Makes structured decisions: APPROVE, EDIT, or REJECT
    - Provides feedback for edit/reject decisions
    
    This node is only reached when:
    - Agent explicitly calls request_human_input tool with questions
    - Configuration has always_require_feedback=True (legacy mode)
    
    Decisions:
    - APPROVE: Finish the workflow, agent's work is accepted
    - EDIT: Add modifications and loop back to base for another iteration
    - REJECT: End workflow with rejection message
    
    Args:
        state: Current workflow state
        config: Runnable configuration
        
    Returns:
        Command to either end workflow or loop back to base node
    """
    logger.info("Human feedback node running with structured HITL.")
    
    # Get the questions the agent wants answered (if any)
    hitl_questions = state.get("hitl_questions", None)
    
    # Build structured HITL request
    hitl_request = {
        "questions": hitl_questions or [],
        "allowed_decisions": ["approve", "edit", "reject"],
        "context": {
            "message_count": len(state.get("messages", [])),
        }
    }
    
    # Add a prompt based on context
    if hitl_questions:
        hitl_request["prompt"] = "The agent needs your input on the following:"
    else:
        hitl_request["prompt"] = "Review the agent's response and choose an action:"
    
    logger.info(f"HITL request: {hitl_request}")
    
    # Interrupt for user decision - returns structured response
    response = interrupt(hitl_request)
    
    # Parse the response - can be:
    # - String: "APPROVED" or plain feedback text
    # - Dict: {"decision": "approve|edit|reject", "feedback": "...", "answers": [...]}
    logger.info(f"HITL response received: {response}")
    
    # Handle None - assume approval
    if not response:
        logger.info("Empty response received, assuming approval.")
        return Command(
            update={
                "needs_human_feedback": False,
                "hitl_questions": None,
                **preserve_state_meta_fields(state),
            },
            goto="__end__"
        )
    
    # Handle string responses (legacy format)
    if isinstance(response, str):
        response_upper = response.strip().upper()
        
        # Check for approval
        if response_upper in ("APPROVED", "ACCEPTED", "OK", "YES"):
            logger.info("User approved the result (string format).")
            return Command(
                update={
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                    **preserve_state_meta_fields(state),
                },
                goto="__end__"
            )
        
        # Check for rejection
        if response_upper in ("REJECTED", "REJECT", "NO", "CANCEL"):
            logger.info("User rejected the result (string format).")
            messages = list(state.get("messages", []))
            messages.append(HumanMessage(
                content=f"[REJECTED] User rejected the agent's work.",
                name="human_decision"
            ))
            return Command(
                update={
                    "messages": messages,
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                    **preserve_state_meta_fields(state),
                },
                goto="__end__"
            )
        
        # Treat as feedback (edit decision) - loop back
        logger.info(f"User provided feedback for edit: {response}")
        messages = list(state.get("messages", []))
        messages.append(HumanMessage(content=response.strip(), name="human_feedback"))
        return Command(
            update={
                "messages": messages,
                "needs_human_feedback": False,
                "hitl_questions": None,
                **preserve_state_meta_fields(state),
            },
            goto="base",
        )
    
    # Handle dict responses (structured format from UI)
    if isinstance(response, dict):
        decision = response.get("decision", "").lower()
        feedback = response.get("feedback", "")
        answers = response.get("answers", [])
        
        # APPROVE decision - end workflow
        if decision == "approve":
            logger.info("User approved (structured decision).")
            return Command(
                update={
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                    **preserve_state_meta_fields(state),
                },
                goto="__end__"
            )
        
        # REJECT decision - end with rejection message
        if decision == "reject":
            logger.info(f"User rejected (structured decision). Reason: {feedback}")
            messages = list(state.get("messages", []))
            rejection_msg = f"[REJECTED] User rejected the agent's work."
            if feedback:
                rejection_msg += f" Reason: {feedback}"
            messages.append(HumanMessage(content=rejection_msg, name="human_decision"))
            return Command(
                update={
                    "messages": messages,
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                    **preserve_state_meta_fields(state),
                },
                goto="__end__"
            )
        
        # EDIT decision or answers provided - add to messages and loop back
        if decision == "edit" or answers or feedback:
            logger.info(f"User requested edit. Feedback: {feedback}, Answers: {answers}")
            messages = list(state.get("messages", []))
            
            # Build the feedback message
            content_parts = []
            if feedback:
                content_parts.append(feedback)
            if answers:
                # Format answers to questions
                for i, answer in enumerate(answers):
                    q = hitl_questions[i] if hitl_questions and i < len(hitl_questions) else f"Question {i+1}"
                    content_parts.append(f"Q: {q}\nA: {answer}")
            
            combined_content = "\n\n".join(content_parts) if content_parts else "Please continue with the changes."
            messages.append(HumanMessage(content=combined_content, name="human_feedback"))
            
            return Command(
                update={
                    "messages": messages,
                    "needs_human_feedback": False,
                    "hitl_questions": None,
                    **preserve_state_meta_fields(state),
                },
                goto="base",
            )
    
    # Fallback - treat unknown response as feedback
    logger.warning(f"Unexpected HITL response format: {type(response)} - treating as feedback")
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=str(response), name="human_feedback"))
    return Command(
        update={
            "messages": messages,
            "needs_human_feedback": False,
            "hitl_questions": None,
            **preserve_state_meta_fields(state),
        },
        goto="base",
    )
