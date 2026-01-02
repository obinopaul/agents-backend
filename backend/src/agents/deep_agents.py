"""Deep Agents - Enhanced agent creation with planning, subagents, and advanced middleware.

This module provides create_agent() as an enhanced alternative to the base agents.py,
with built-in support for:
- TodoListMiddleware for task planning (stores todos in agent state)
- SubAgentMiddleware for spawning sub-agents for parallel work
- HumanInTheLoopMiddleware with interrupt_on for tool-specific HITL
- SummarizationMiddleware for context management
- Response caching via cache parameter
- Persistent storage via store parameter
- Typed context via context_schema parameter

Usage:
    from backend.src.agents.deep_agents import create_agent
    
    agent = create_agent(
        agent_name="researcher",
        agent_type="researcher",
        tools=my_tools,
        prompt_template="researcher",
        interrupt_on={"dangerous_tool": True},  # Pause before this tool
        subagents=[
            SubAgent(name="helper", description="Helper agent", prompt="You help with tasks"),
        ],
    )
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any, List, Optional

from langchain.agents import create_agent as langchain_create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
    TodoListMiddleware,
    SummarizationMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ModelFallbackMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

# PersistentTaskMiddleware for robust task management
from backend.src.agents.middleware.persistent_task_middleware import (
    PersistentTaskMiddleware,
)

# ViewImageMiddleware for vision model support
from backend.src.agents.middleware.view_image_middleware import (
    ViewImageMiddleware,
)

# BackgroundSubagentMiddleware for async/parallel subagent execution
from backend.src.agents.middleware.background_middleware import (
    BackgroundSubagentMiddleware,
    BackgroundSubagentOrchestrator,
)

# Optional: SubAgent support from deepagents package
try:
    from deepagents.middleware.subagents import (
        CompiledSubAgent,
        SubAgent,
        SubAgentMiddleware,
    )
    from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
    SUBAGENT_AVAILABLE = True
except ImportError:
    SUBAGENT_AVAILABLE = False
    SubAgent = None
    CompiledSubAgent = None
    SubAgentMiddleware = None
    SubAgentMiddleware = None
    PatchToolCallsMiddleware = None

from backend.src.agents.subagents import create_default_subagents
from backend.core.conf import settings
from backend.src.llms.llm import (
    get_llm,
    get_fallback_llm,
    get_fallback_model_identifiers,
)
from backend.src.prompts.template import get_prompt_template

logger = logging.getLogger(__name__)


# =============================================================================
# Base Agent Prompt (from DeepAgents)
# =============================================================================

BASE_AGENT_PROMPT = """In order to complete the objective that the user asks of you, you have access to a number of standard tools.

When working on complex tasks:
1. Use the write_todos tool to plan your approach and track progress
2. Break down large tasks into smaller, manageable steps
3. Mark todos as complete as you finish them
4. If a task requires specialized work, consider delegating to a subagent
"""


# =============================================================================
# Default Model Configuration
# =============================================================================

def get_default_model() -> BaseChatModel:
    """Get the default model for deep agents.
    
    Uses the project's configured LLM from settings.
    
    Returns:
        Configured LLM instance.
    """
    return get_llm()


def _get_middleware_llm() -> BaseChatModel:
    """Get an LLM instance for middleware operations.
    
    Uses the fallback/supplementary LLM if configured, otherwise
    uses the primary LLM. This keeps middleware operations independent
    from the main agent LLM.
    
    Returns:
        A configured LLM instance for middleware use.
    """
    return get_fallback_llm()


# =============================================================================
# Summarization Configuration
# =============================================================================

def _get_summarization_config(model: BaseChatModel) -> tuple:
    """Determine summarization trigger and keep settings based on model profile.
    
    If the model has profile information with max_input_tokens, use fraction-based
    settings. Otherwise, use token-based defaults.
    
    Args:
        model: The LLM model to check profile for.
        
    Returns:
        Tuple of (trigger, keep) configuration.
    """
    if (
        hasattr(model, 'profile')
        and model.profile is not None
        and isinstance(model.profile, dict)
        and "max_input_tokens" in model.profile
        and isinstance(model.profile["max_input_tokens"], int)
    ):
        # Fraction-based: trigger at 85% capacity, keep 10% of context
        trigger = ("fraction", 0.85)
        keep = ("fraction", 0.10)
    else:
        # Token-based defaults
        trigger = ("tokens", settings.MIDDLEWARE_SUMMARIZATION_TRIGGER_TOKENS)
        keep = ("messages", settings.MIDDLEWARE_SUMMARIZATION_KEEP_MESSAGES)
    
    return trigger, keep


# =============================================================================
# Deep Agent Middleware Stack Builder
# =============================================================================

def build_deep_middleware(
    model: BaseChatModel,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    subagents: list | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    custom_middleware: Sequence[AgentMiddleware] = (),
    # Summarization settings
    enable_summarization: bool = True,
    summarization_trigger_tokens: int = None,
    summarization_keep_messages: int = None,
    # Retry settings
    enable_model_retry: bool = None,
    model_max_retries: int = None,
    enable_tool_retry: bool = None,
    tool_max_retries: int = None,
    # Limit settings
    enable_model_call_limit: bool = None,
    model_call_thread_limit: int = None,
    model_call_run_limit: int = None,
    enable_tool_call_limit: bool = None,
    tool_call_thread_limit: int = None,
    tool_call_run_limit: int = None,
    # Fallback settings
    enable_model_fallback: bool = None,
    fallback_models: List[str] = None,
    # Prompt caching (Anthropic-specific)
    enable_prompt_caching: bool = True,
    # Background subagent settings
    enable_background_tasks: bool = False,
    background_task_timeout: float = 60.0,
) -> list[AgentMiddleware]:
    """Build the deep agent middleware stack.
    
    This creates a comprehensive middleware stack with:
    1. TodoListMiddleware - Task planning with write_todos tool
    2. SubAgentMiddleware - Spawn sub-agents for parallel work (if available)
    3. SummarizationMiddleware - Context compression
    4. AnthropicPromptCachingMiddleware - Prompt caching for Anthropic models
    5. PatchToolCallsMiddleware - Tool call fixes (if available)
    6. ModelRetryMiddleware - Retry failed model calls
    7. ToolRetryMiddleware - Retry failed tool calls
    8. ModelCallLimitMiddleware - Limit model API calls
    9. ToolCallLimitMiddleware - Limit tool executions
    10. ModelFallbackMiddleware - Fallback to alternative models
    11. HumanInTheLoopMiddleware - Tool-specific HITL (if interrupt_on provided)
    
    Args:
        model: The main LLM model.
        tools: Tools available to the agent.
        subagents: List of SubAgent configurations for SubAgentMiddleware.
        interrupt_on: Dict mapping tool names to interrupt configs.
        custom_middleware: Additional middleware to append at the end.
        enable_summarization: Enable context summarization.
        summarization_trigger_tokens: Token count to trigger summarization.
        summarization_keep_messages: Messages to preserve during summarization.
        enable_model_retry: Enable model call retry logic.
        model_max_retries: Max retries for model calls.
        enable_tool_retry: Enable tool call retry logic.
        tool_max_retries: Max retries for tool calls.
        enable_model_call_limit: Enable model call limits.
        model_call_thread_limit: Max model calls per thread.
        model_call_run_limit: Max model calls per run.
        enable_tool_call_limit: Enable tool call limits.
        tool_call_thread_limit: Max tool calls per thread.
        tool_call_run_limit: Max tool calls per run.
        enable_model_fallback: Enable fallback to alternative models.
        fallback_models: List of model identifiers for fallback.
        enable_prompt_caching: Enable Anthropic prompt caching.
        enable_background_tasks: Enable background/parallel subagent execution (opt-in).
        background_task_timeout: Timeout for background tasks in seconds (default: 60).
        
    Returns:
        List of configured middleware instances.
    """
    # Apply settings defaults
    if enable_model_retry is None:
        enable_model_retry = settings.MIDDLEWARE_ENABLE_MODEL_RETRY
    if model_max_retries is None:
        model_max_retries = settings.MIDDLEWARE_MODEL_MAX_RETRIES
    if enable_tool_retry is None:
        enable_tool_retry = settings.MIDDLEWARE_ENABLE_TOOL_RETRY
    if tool_max_retries is None:
        tool_max_retries = settings.MIDDLEWARE_TOOL_MAX_RETRIES
    if enable_model_call_limit is None:
        enable_model_call_limit = settings.MIDDLEWARE_ENABLE_MODEL_CALL_LIMIT
    if model_call_thread_limit is None:
        model_call_thread_limit = settings.MIDDLEWARE_MODEL_CALL_THREAD_LIMIT
    if model_call_run_limit is None:
        model_call_run_limit = settings.MIDDLEWARE_MODEL_CALL_RUN_LIMIT
    if enable_tool_call_limit is None:
        enable_tool_call_limit = settings.MIDDLEWARE_ENABLE_TOOL_CALL_LIMIT
    if tool_call_thread_limit is None:
        tool_call_thread_limit = settings.MIDDLEWARE_TOOL_CALL_THREAD_LIMIT
    if tool_call_run_limit is None:
        tool_call_run_limit = settings.MIDDLEWARE_TOOL_CALL_RUN_LIMIT
    if enable_model_fallback is None:
        enable_model_fallback = settings.MIDDLEWARE_ENABLE_MODEL_FALLBACK
    if fallback_models is None:
        fallback_models = get_fallback_model_identifiers()
    
    # Get summarization config
    trigger, keep = _get_summarization_config(model)
    if summarization_trigger_tokens is not None:
        trigger = ("tokens", summarization_trigger_tokens)
    if summarization_keep_messages is not None:
        keep = ("messages", summarization_keep_messages)
    
    middleware = []
    
    # -------------------------------------------------------------------------
    # Core Deep Agent Middleware
    # -------------------------------------------------------------------------
    
    # 1. TodoListMiddleware - Adds write_todos tool for task planning
    # Todos are stored in agent state, not external files
    middleware.append(TodoListMiddleware())
    logger.debug("Added TodoListMiddleware for task planning")
    
    # 2. PersistentTaskMiddleware - Persistent task management with sections
    # Uses LangGraph Store for persistence across sessions
    middleware.append(PersistentTaskMiddleware())
    logger.debug("Added PersistentTaskMiddleware for persistent task management")
    
    # 2.5. ViewImageMiddleware - Enable vision models to see images
    # Intercepts view_image tool calls and injects images into message history
    middleware.append(ViewImageMiddleware(validate_urls=True, strict_validation=True))
    logger.debug("Added ViewImageMiddleware for vision model support")
    
    # 3. Subagent & Background System Configuration
    
    # 3.1 Initialize Background Middleware (if enabled)
    # We do this first to get the registry for dependency injection
    bg_registry = None
    bg_middleware_instance = None
    
    if enable_background_tasks:
        bg_middleware_instance = BackgroundSubagentMiddleware(
            timeout=background_task_timeout,
            enabled=True,
        )
        bg_registry = bg_middleware_instance.registry
        logger.debug("Initialized BackgroundSubagentMiddleware (pre-injection)")

    # 3.2 Add Background Middleware to stack
    # Must be BEFORE SubAgentMiddleware to intercept 'background_task' and rewrite to 'task'
    if bg_middleware_instance:
        middleware.append(bg_middleware_instance)
        logger.debug(f"Added BackgroundSubagentMiddleware (timeout={background_task_timeout}s)")

    # 3.3 Prepare Subagents (Inject Counter if registry exists)
    # If no subagents provided, create defaults with injected middleware
    effective_subagents = subagents
    if not effective_subagents:
        effective_subagents = create_default_subagents(registry=bg_registry, model=model)

    # 3.4 Add SubAgent Middleware - Spawn sub-agents for parallel work
    if SUBAGENT_AVAILABLE and SubAgentMiddleware is not None:
        middleware.append(
            SubAgentMiddleware(
                default_model=model,
                default_tools=tools if tools else [],
                subagents=effective_subagents if effective_subagents else [],
                default_middleware=[
                    TodoListMiddleware(),
                    PersistentTaskMiddleware(),  # Add persistent tasks to subagents
                    SummarizationMiddleware(
                        model=_get_middleware_llm(),
                        trigger=trigger,
                        keep=keep,
                        trim_tokens_to_summarize=None,
                    ),
                    AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
                ],
                default_interrupt_on=interrupt_on,
                general_purpose_agent=True,
            )
        )
        logger.debug("Added SubAgentMiddleware for sub-agent spawning")
    else:
        logger.debug("SubAgentMiddleware not available (deepagents package not installed)")
    
    # 4. SummarizationMiddleware - Compress long conversations
    if enable_summarization:
        middleware.append(
            SummarizationMiddleware(
                model=_get_middleware_llm(),
                trigger=trigger,
                keep=keep,
                trim_tokens_to_summarize=None,
            )
        )
        logger.debug(f"Added SummarizationMiddleware (trigger={trigger}, keep={keep})")
    
    # 4. AnthropicPromptCachingMiddleware - Prompt caching for Anthropic models
    if enable_prompt_caching:
        middleware.append(
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")
        )
        logger.debug("Added AnthropicPromptCachingMiddleware")
    
    # 5. PatchToolCallsMiddleware - Fix tool call issues
    if SUBAGENT_AVAILABLE and PatchToolCallsMiddleware is not None:
        middleware.append(PatchToolCallsMiddleware())
        logger.debug("Added PatchToolCallsMiddleware")
    
    # -------------------------------------------------------------------------
    # Production Middleware (from agents.py)
    # -------------------------------------------------------------------------
    
    # 6. ModelFallbackMiddleware - Try alternative models on failure
    if enable_model_fallback and fallback_models:
        middleware.append(
            ModelFallbackMiddleware(fallback_models=fallback_models)
        )
        logger.debug(f"Added ModelFallbackMiddleware (fallbacks={fallback_models})")
    
    # 7. ModelRetryMiddleware - Retry failed model calls
    if enable_model_retry:
        middleware.append(
            ModelRetryMiddleware(
                max_retries=model_max_retries,
                backoff_factor=settings.MIDDLEWARE_MODEL_BACKOFF_FACTOR,
                initial_delay=settings.MIDDLEWARE_MODEL_INITIAL_DELAY,
            )
        )
        logger.debug(f"Added ModelRetryMiddleware (max_retries={model_max_retries})")
    
    # 8. ToolRetryMiddleware - Retry failed tool calls
    if enable_tool_retry:
        middleware.append(
            ToolRetryMiddleware(
                max_retries=tool_max_retries,
                backoff_factor=settings.MIDDLEWARE_TOOL_BACKOFF_FACTOR,
                initial_delay=settings.MIDDLEWARE_TOOL_INITIAL_DELAY,
            )
        )
        logger.debug(f"Added ToolRetryMiddleware (max_retries={tool_max_retries})")
    
    # 9. ModelCallLimitMiddleware - Prevent runaway costs
    if enable_model_call_limit:
        middleware.append(
            ModelCallLimitMiddleware(
                thread_limit=model_call_thread_limit,
                run_limit=model_call_run_limit,
                exit_behavior="end",
            )
        )
        logger.debug(
            f"Added ModelCallLimitMiddleware "
            f"(thread_limit={model_call_thread_limit}, run_limit={model_call_run_limit})"
        )
    
    # 10. ToolCallLimitMiddleware - Prevent excessive tool usage
    if enable_tool_call_limit:
        middleware.append(
            ToolCallLimitMiddleware(
                thread_limit=tool_call_thread_limit,
                run_limit=tool_call_run_limit,
            )
        )
        logger.debug(
            f"Added ToolCallLimitMiddleware "
            f"(thread_limit={tool_call_thread_limit}, run_limit={tool_call_run_limit})"
        )
    
    # -------------------------------------------------------------------------
    # Human-in-the-Loop Middleware (OPTIONAL - Disabled by Default)
    # -------------------------------------------------------------------------
    # This is a SAFETY NET for specific dangerous tools, NOT the primary HITL.
    # 
    # Your primary HITL uses:
    # - request_human_input tool (agent-driven)
    # - human_feedback_node with AG-UI protocol
    # - Supports rich decisions: approve, edit, reject, feedback
    #
    # This middleware is for automatic guardrails on specific tools:
    # - Example: interrupt_on={"delete_file": True} always pauses before delete
    # - Use for tools where you don't trust the agent to ask
    #
    # Only added if interrupt_on is explicitly provided.
    if interrupt_on is not None:
        middleware.append(
            HumanInTheLoopMiddleware(interrupt_on=interrupt_on)
        )
        logger.debug(f"Added HumanInTheLoopMiddleware (interrupt_on={list(interrupt_on.keys())})")
    
    # -------------------------------------------------------------------------
    # Custom Middleware
    # -------------------------------------------------------------------------
    
    if custom_middleware:
        middleware.extend(custom_middleware)
        logger.debug(f"Added {len(custom_middleware)} custom middleware")
    
    return middleware


# =============================================================================
# Create Agent Factory Function
# =============================================================================

def create_agent(
    agent_name: str,
    agent_type: str,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    prompt_template: str = None,
    *,
    # Model configuration
    model: str | BaseChatModel | None = None,
    # Middleware configuration
    middleware: Sequence[AgentMiddleware] = (),
    use_default_middleware: bool = True,
    middleware_config: Optional[dict] = None,
    # Deep agent features
    subagents: list | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    # LangGraph features
    response_format: Any = None,
    context_schema: type[Any] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    cache: BaseCache | None = None,
    # Debug and naming
    debug: bool = False,
    name: str | None = None,
    # Recursion limit
    recursion_limit: int = 1000,
) -> CompiledStateGraph:
    """Create a deep agent with planning, subagents, and advanced middleware.
    
    This is an enhanced version of agents.py create_agent() with additional
    features from the DeepAgents architecture:
    
    - TodoListMiddleware: Agent can plan tasks with write_todos tool
    - SubAgentMiddleware: Agent can spawn sub-agents for parallel work
    - interrupt_on: Pause execution before specific tools for HITL
    - cache: Response caching for efficiency
    - store: Persistent storage across runs
    - context_schema: Typed agent context
    
    Args:
        agent_name: Name of the agent.
        agent_type: Type of agent (researcher, coder, etc.) for logging.
        tools: Tools available to the agent.
        prompt_template: Name of the prompt template to use.
        model: The model to use. Defaults to configured LLM from settings.
        middleware: Additional middleware to apply after default middleware.
        use_default_middleware: Whether to include default deep middleware.
        middleware_config: Dict to configure default middleware parameters.
        subagents: List of SubAgent configurations for spawning sub-agents.
        interrupt_on: Dict mapping tool names to interrupt configs for HITL.
            Example: {"dangerous_tool": True} or 
                     {"tool_name": InterruptOnConfig(before=True, after=False)}
        response_format: Structured output response format.
        context_schema: Schema for typed agent context.
        checkpointer: Checkpointer for persisting agent state.
        store: Store for persistent storage across runs.
        cache: Cache for response caching.
        debug: Enable debug mode.
        name: Override agent name passed to LangChain.
        recursion_limit: Max recursion depth for agent execution.
        
    Returns:
        A configured deep agent graph (CompiledStateGraph).
        
    Example:
        >>> agent = create_agent(
        ...     agent_name="researcher",
        ...     agent_type="researcher", 
        ...     tools=[web_search_tool, crawl_tool],
        ...     prompt_template="researcher",
        ...     interrupt_on={"dangerous_action": True},
        ...     subagents=[
        ...         SubAgent(
        ...             name="writer",
        ...             description="Writes content",
        ...             prompt="You are a content writer",
        ...         ),
        ...     ],
        ... )
    """
    logger.debug(
        f"Creating deep agent '{agent_name}' of type '{agent_type}' "
        f"with {len(tools) if tools else 0} tools"
    )
    
    # Get the model
    if model is None:
        model = get_default_model()
    elif isinstance(model, str):
        from langchain.chat_models import init_chat_model
        model = init_chat_model(model)
    
    logger.debug(f"Deep agent '{agent_name}' using model: {type(model).__name__}")
    
    # Get the system prompt
    system_prompt = None
    if prompt_template:
        try:
            system_prompt = get_prompt_template(prompt_template)
            logger.debug(f"Loaded prompt template '{prompt_template}'")
        except Exception as e:
            logger.warning(f"Failed to load prompt template '{prompt_template}': {e}")
            system_prompt = f"You are a helpful {agent_type} agent named {agent_name}."
    
    # Combine with base agent prompt for deep agent features
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{BASE_AGENT_PROMPT}"
    else:
        full_prompt = BASE_AGENT_PROMPT
    
    # Build middleware
    middleware_list = []
    
    if use_default_middleware:
        config = middleware_config or {}
        deep_mw = build_deep_middleware(
            model=model,
            tools=tools,
            subagents=subagents,
            interrupt_on=interrupt_on,
            **config,
        )
        middleware_list.extend(deep_mw)
        logger.debug(f"Added {len(deep_mw)} default deep middleware for agent '{agent_name}'")
    
    # Add custom middleware
    if middleware:
        middleware_list.extend(middleware)
        logger.debug(f"Added {len(middleware)} custom middleware for agent '{agent_name}'")
    
    logger.info(f"Deep agent '{agent_name}' total middleware count: {len(middleware_list)}")
    
    # Create the agent using LangChain create_agent
    agent = langchain_create_agent(
        model=model,
        tools=tools if tools else [],
        system_prompt=full_prompt,
        middleware=middleware_list if middleware_list else (),
        response_format=response_format,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        cache=cache,
        debug=debug,
        name=name or agent_name,
    )
    
    # Apply recursion limit
    agent = agent.with_config({"recursion_limit": recursion_limit})
    
    logger.info(
        f"Deep agent '{agent_name}' created successfully with "
        f"TodoListMiddleware, SubAgentMiddleware, and {len(middleware_list)} total middleware"
    )
    
    return agent


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "create_agent",
    "build_deep_middleware",
    "get_default_model",
    "SubAgent",
    "CompiledSubAgent",
    "InterruptOnConfig",
    "SUBAGENT_AVAILABLE",
]
