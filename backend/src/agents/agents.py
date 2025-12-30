import logging
from typing import Any, List, Optional, Sequence

from langchain.agents import create_agent as langchain_create_agent
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
    # Built-in middleware
    SummarizationMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ModelFallbackMiddleware,
)
from langchain_core.messages import SystemMessage

from backend.core.conf import settings
from backend.src.agents.tool_interceptor import wrap_tools_with_interceptor
from backend.src.llms.llm import (
    get_llm,
    get_fallback_llm,
    get_fallback_model_identifiers,
)
from backend.src.prompts.template import get_prompt_template

logger = logging.getLogger(__name__)


# =============================================================================
# Middleware LLM Configuration
# =============================================================================

def _get_middleware_llm():
    """Get an LLM instance for middleware operations.
    
    Uses the fallback/supplementary LLM if configured, otherwise
    uses the primary LLM. This keeps middleware operations independent
    from the main agent LLM.
    
    Returns:
        A configured LLM instance for middleware use
    """
    return get_fallback_llm()


def build_default_middleware(
    enable_summarization: bool = None,
    enable_model_retry: bool = None,
    enable_tool_retry: bool = None,
    enable_model_call_limit: bool = None,
    enable_tool_call_limit: bool = None,
    enable_model_fallback: bool = None,
    summarization_trigger_tokens: int = None,
    summarization_keep_messages: int = None,
    model_max_retries: int = None,
    model_backoff_factor: float = None,
    model_initial_delay: float = None,
    tool_max_retries: int = None,
    tool_backoff_factor: float = None,
    tool_initial_delay: float = None,
    model_call_thread_limit: int = None,
    model_call_run_limit: int = None,
    tool_call_thread_limit: int = None,
    tool_call_run_limit: int = None,
    fallback_models: List[str] = None,
) -> List[Any]:
    """Build a list of default middleware for production agents.
    
    This function creates essential middleware for robust agent operation:
    - ModelFallbackMiddleware: Try alternative models when primary fails
    - SummarizationMiddleware: Compress long conversations to fit context windows
    - ModelRetryMiddleware: Retry failed model calls with exponential backoff
    - ToolRetryMiddleware: Retry failed tool calls with exponential backoff
    - ModelCallLimitMiddleware: Prevent excessive model API calls
    - ToolCallLimitMiddleware: Prevent excessive tool executions
    
    All parameters default to values from environment variables via settings.
    Pass explicit values to override settings for specific use cases.
    
    Args:
        enable_summarization: Enable conversation summarization
        enable_model_retry: Enable model call retry logic
        enable_tool_retry: Enable tool call retry logic
        enable_model_call_limit: Enable model call limits
        enable_tool_call_limit: Enable tool call limits
        enable_model_fallback: Enable fallback to alternative models
        summarization_trigger_tokens: Token count to trigger summarization
        summarization_keep_messages: Number of recent messages to preserve
        model_max_retries: Max retries for model calls
        model_backoff_factor: Backoff multiplier for model retries
        model_initial_delay: Initial delay (seconds) for model retries
        tool_max_retries: Max retries for tool calls
        tool_backoff_factor: Backoff multiplier for tool retries
        tool_initial_delay: Initial delay (seconds) for tool retries
        model_call_thread_limit: Max model calls per thread
        model_call_run_limit: Max model calls per run
        tool_call_thread_limit: Max tool calls per thread
        tool_call_run_limit: Max tool calls per run
        fallback_models: List of model identifiers for fallback chain
        
    Returns:
        List of configured middleware instances
    """
    # Use settings values as defaults (allow None to be overridden)
    if enable_summarization is None:
        enable_summarization = settings.MIDDLEWARE_ENABLE_SUMMARIZATION
    if enable_model_retry is None:
        enable_model_retry = settings.MIDDLEWARE_ENABLE_MODEL_RETRY
    if enable_tool_retry is None:
        enable_tool_retry = settings.MIDDLEWARE_ENABLE_TOOL_RETRY
    if enable_model_call_limit is None:
        enable_model_call_limit = settings.MIDDLEWARE_ENABLE_MODEL_CALL_LIMIT
    if enable_tool_call_limit is None:
        enable_tool_call_limit = settings.MIDDLEWARE_ENABLE_TOOL_CALL_LIMIT
    if enable_model_fallback is None:
        enable_model_fallback = settings.MIDDLEWARE_ENABLE_MODEL_FALLBACK
        
    if summarization_trigger_tokens is None:
        summarization_trigger_tokens = settings.MIDDLEWARE_SUMMARIZATION_TRIGGER_TOKENS
    if summarization_keep_messages is None:
        summarization_keep_messages = settings.MIDDLEWARE_SUMMARIZATION_KEEP_MESSAGES
        
    if model_max_retries is None:
        model_max_retries = settings.MIDDLEWARE_MODEL_MAX_RETRIES
    if model_backoff_factor is None:
        model_backoff_factor = settings.MIDDLEWARE_MODEL_BACKOFF_FACTOR
    if model_initial_delay is None:
        model_initial_delay = settings.MIDDLEWARE_MODEL_INITIAL_DELAY
        
    if tool_max_retries is None:
        tool_max_retries = settings.MIDDLEWARE_TOOL_MAX_RETRIES
    if tool_backoff_factor is None:
        tool_backoff_factor = settings.MIDDLEWARE_TOOL_BACKOFF_FACTOR
    if tool_initial_delay is None:
        tool_initial_delay = settings.MIDDLEWARE_TOOL_INITIAL_DELAY
        
    if model_call_thread_limit is None:
        model_call_thread_limit = settings.MIDDLEWARE_MODEL_CALL_THREAD_LIMIT
    if model_call_run_limit is None:
        model_call_run_limit = settings.MIDDLEWARE_MODEL_CALL_RUN_LIMIT
        
    if tool_call_thread_limit is None:
        tool_call_thread_limit = settings.MIDDLEWARE_TOOL_CALL_THREAD_LIMIT
    if tool_call_run_limit is None:
        tool_call_run_limit = settings.MIDDLEWARE_TOOL_CALL_RUN_LIMIT
        
    if fallback_models is None:
        fallback_models = get_fallback_model_identifiers()
    
    middleware = []
    
    # Model fallback middleware - tries alternative models on failure
    # Should be first to catch failures and route to fallback models
    if enable_model_fallback and fallback_models:
        middleware.append(
            ModelFallbackMiddleware(
                fallback_models=fallback_models,
            )
        )
        logger.debug(f"Added ModelFallbackMiddleware (fallbacks={fallback_models})")
    
    # Model retry middleware - handles transient API failures
    # Should be early in the stack to catch failures from downstream middleware
    if enable_model_retry:
        middleware.append(
            ModelRetryMiddleware(
                max_retries=model_max_retries,
                backoff_factor=model_backoff_factor,
                initial_delay=model_initial_delay,
            )
        )
        logger.debug(f"Added ModelRetryMiddleware (max_retries={model_max_retries})")
    
    # Tool retry middleware - handles transient tool failures
    if enable_tool_retry:
        middleware.append(
            ToolRetryMiddleware(
                max_retries=tool_max_retries,
                backoff_factor=tool_backoff_factor,
                initial_delay=tool_initial_delay,
            )
        )
        logger.debug(f"Added ToolRetryMiddleware (max_retries={tool_max_retries})")
    
    # Summarization middleware - compresses long conversations
    # Uses a separate LLM instance for summarization
    if enable_summarization:
        summarization_llm = _get_middleware_llm()
        middleware.append(
            SummarizationMiddleware(
                model=summarization_llm,
                trigger=("tokens", summarization_trigger_tokens),
                keep=("messages", summarization_keep_messages),
            )
        )
        logger.debug(
            f"Added SummarizationMiddleware "
            f"(trigger={summarization_trigger_tokens} tokens, keep={summarization_keep_messages} messages)"
        )
    
    # Model call limit middleware - prevents runaway costs
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
    
    # Tool call limit middleware - prevents excessive tool usage
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
    
    return middleware


def _create_context_compression_middleware(compress_fn: callable):
    """Create middleware for context compression before model calls.
    
    Uses the wrap_model_call decorator to create async middleware that compresses
    messages before they're sent to the model.
    
    Note: The middleware function MUST be async to support both sync and async
    invocation patterns (invoke/ainvoke, stream/astream).
    
    Args:
        compress_fn: Function that takes state dict and returns compressed state
        
    Returns:
        A middleware function compatible with create_agent
    """
    @wrap_model_call
    async def context_compression_middleware(request: ModelRequest, handler) -> ModelResponse:
        """Compress context before model invocation (async version)."""
        try:
            messages = request.state.get("messages", [])
            if messages:
                compressed_state = compress_fn({"messages": messages})
                compressed_messages = compressed_state.get("messages", messages)
                # Override the request with compressed messages
                new_state = {**request.state, "messages": compressed_messages}
                return await handler(request.override(state=new_state))
        except Exception as e:
            logger.warning(f"Context compression middleware failed: {e}")
        
        return await handler(request)
    
    return context_compression_middleware


def create_agent(
    agent_name: str,
    agent_type: str,
    tools: list,
    prompt_template: str,
    pre_model_hook: callable = None,
    interrupt_before_tools: Optional[List[str]] = None,
    middleware: Optional[Sequence[Any]] = None,
    use_default_middleware: bool = True,
    middleware_config: Optional[dict] = None,
):
    """Factory function to create agents with consistent configuration.

    Uses langchain.agents.create_agent (LangChain v1) with the correct signature.
    Includes production-ready built-in middleware by default.

    Args:
        agent_name: Name of the agent
        agent_type: Type of agent (researcher, coder, etc.) - for logging purposes
        tools: List of tools available to the agent
        prompt_template: Name of the prompt template to use
        pre_model_hook: Optional hook to preprocess state before model invocation
                        (converted to middleware internally)
        interrupt_before_tools: Optional list of tool names to interrupt before execution
        middleware: Optional list of additional/custom middleware instances
                    (appended after default middleware)
        use_default_middleware: Whether to include default production middleware
                               (SummarizationMiddleware, ModelRetryMiddleware, etc.)
        middleware_config: Optional dict to configure default middleware.
                          Keys: enable_summarization, enable_model_retry, enable_tool_retry,
                                enable_model_call_limit, enable_tool_call_limit, etc.

    Returns:
        A configured agent graph (CompiledStateGraph)
    """
    logger.debug(
        f"Creating agent '{agent_name}' of type '{agent_type}' "
        f"with {len(tools)} tools and template '{prompt_template}'"
    )
    
    # Wrap tools with interrupt logic if specified
    processed_tools = tools
    if interrupt_before_tools:
        logger.info(
            f"Creating agent '{agent_name}' with tool-specific interrupts: {interrupt_before_tools}"
        )
        logger.debug(f"Wrapping {len(tools)} tools for agent '{agent_name}'")
        processed_tools = wrap_tools_with_interceptor(tools, interrupt_before_tools)
        logger.debug(f"Agent '{agent_name}' tool wrapping completed")
    else:
        logger.debug(f"Agent '{agent_name}' has no interrupt-before-tools configured")

    # Get the configured LLM (uses LLM_PROVIDER from settings)
    llm = get_llm()
    logger.debug(f"Agent '{agent_name}' using LLM provider from settings")
    
    # Get the system prompt string from template
    # LangChain v1 create_agent expects a string or SystemMessage, not a callable
    try:
        system_prompt = get_prompt_template(prompt_template)
        logger.debug(f"Loaded prompt template '{prompt_template}'")
    except Exception as e:
        logger.warning(f"Failed to load prompt template '{prompt_template}': {e}")
        system_prompt = f"You are a helpful {agent_type} agent named {agent_name}."
    
    # Build middleware list
    middleware_list = []
    
    # Add default production middleware if enabled
    if use_default_middleware:
        config = middleware_config or {}
        default_mw = build_default_middleware(**config)
        middleware_list.extend(default_mw)
        logger.debug(f"Added {len(default_mw)} default middleware for agent '{agent_name}'")
    
    # Convert pre_model_hook to middleware if provided
    if pre_model_hook:
        compression_middleware = _create_context_compression_middleware(pre_model_hook)
        middleware_list.append(compression_middleware)
        logger.debug(f"Added context compression middleware for agent '{agent_name}'")
    
    # Add custom/additional middleware
    if middleware:
        middleware_list.extend(middleware)
        logger.debug(f"Added {len(middleware)} custom middleware for agent '{agent_name}'")
    
    logger.debug(f"Creating ReAct agent '{agent_name}'")
    logger.info(f"Agent '{agent_name}' total middleware count: {len(middleware_list)}")
    
    # Create agent using LangChain v1 create_agent signature
    # See: https://docs.langchain.com/oss/python/langchain/agents
    agent = langchain_create_agent(
        model=llm,
        tools=processed_tools,
        system_prompt=system_prompt,
        middleware=middleware_list if middleware_list else (),
        name=agent_name,
        debug=False,  # Set to True for verbose logging
    )
    
    logger.info(f"Agent '{agent_name}' created successfully with LangChain v1 create_agent")
    
    return agent
