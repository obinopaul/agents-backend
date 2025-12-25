"""LLM Factory - Provider-based LLM instantiation.

This module provides a unified factory for creating LLM instances from different
providers using their native LangChain packages.

Supported providers:
- openai: langchain_openai.ChatOpenAI
- anthropic: langchain_anthropic.ChatAnthropic
- gemini: langchain_google_genai.ChatGoogleGenerativeAI
- deepseek: langchain_deepseek.ChatDeepSeek
- groq: langchain_groq.ChatGroq
- huggingface: langchain_huggingface.ChatHuggingFace
"""

import logging
from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel

from backend.core.conf import settings
from backend.src.config.agents import LLMProvider, get_provider_display_name, get_provider_package

logger = logging.getLogger(__name__)


def _create_openai_llm() -> BaseChatModel:
    """Create OpenAI LLM client using langchain-openai.
    
    Uses ChatOpenAI from langchain_openai package.
    Supports custom base_url for proxies/emulators.
    
    Returns:
        ChatOpenAI instance configured from settings.
    """
    from langchain_openai import ChatOpenAI
    
    kwargs = {
        "model": settings.OPENAI_MODEL,
        "api_key": settings.OPENAI_API_KEY,
        "max_retries": settings.LLM_MAX_RETRIES,
        "temperature": settings.LLM_TEMPERATURE,
    }
    
    # Add optional base_url for proxies/emulators
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    
    logger.info(f"Creating OpenAI LLM: model={settings.OPENAI_MODEL}")
    return ChatOpenAI(**kwargs)


def _create_anthropic_llm() -> BaseChatModel:
    """Create Anthropic LLM client using langchain-anthropic.
    
    Uses ChatAnthropic from langchain_anthropic package.
    
    Returns:
        ChatAnthropic instance configured from settings.
    """
    from langchain_anthropic import ChatAnthropic
    
    logger.info(f"Creating Anthropic LLM: model={settings.ANTHROPIC_MODEL}")
    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        max_retries=settings.LLM_MAX_RETRIES,
        temperature=settings.LLM_TEMPERATURE,
    )


def _create_gemini_llm() -> BaseChatModel:
    """Create Google Gemini LLM client using langchain-google-genai.
    
    Uses ChatGoogleGenerativeAI from langchain_google_genai package.
    Supports optional Vertex AI configuration.
    
    Returns:
        ChatGoogleGenerativeAI instance configured from settings.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    kwargs = {
        "model": settings.GEMINI_MODEL,
        "google_api_key": settings.GOOGLE_API_KEY,
        "temperature": settings.LLM_TEMPERATURE,
    }
    
    # Add Vertex AI configuration if enabled
    if settings.GOOGLE_GENAI_USE_VERTEXAI:
        kwargs["vertexai"] = True
        if settings.GOOGLE_CLOUD_PROJECT:
            kwargs["project"] = settings.GOOGLE_CLOUD_PROJECT
    
    logger.info(f"Creating Gemini LLM: model={settings.GEMINI_MODEL}, vertexai={settings.GOOGLE_GENAI_USE_VERTEXAI}")
    return ChatGoogleGenerativeAI(**kwargs)


def _create_deepseek_llm() -> BaseChatModel:
    """Create DeepSeek LLM client using langchain-deepseek.
    
    Uses ChatDeepSeek from langchain_deepseek package.
    
    Returns:
        ChatDeepSeek instance configured from settings.
    """
    from langchain_deepseek import ChatDeepSeek
    
    logger.info(f"Creating DeepSeek LLM: model={settings.DEEPSEEK_MODEL}")
    return ChatDeepSeek(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        max_retries=settings.LLM_MAX_RETRIES,
        temperature=settings.LLM_TEMPERATURE,
    )


def _create_groq_llm() -> BaseChatModel:
    """Create Groq LLM client using langchain-groq.
    
    Uses ChatGroq from langchain_groq package.
    
    Returns:
        ChatGroq instance configured from settings.
    """
    from langchain_groq import ChatGroq
    
    logger.info(f"Creating Groq LLM: model={settings.GROQ_MODEL}")
    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        max_retries=settings.LLM_MAX_RETRIES,
        temperature=settings.LLM_TEMPERATURE,
    )


def _create_huggingface_llm() -> BaseChatModel:
    """Create HuggingFace LLM client using langchain-huggingface.
    
    Uses ChatHuggingFace with HuggingFaceEndpoint from langchain_huggingface package.
    
    Returns:
        ChatHuggingFace instance configured from settings.
    """
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    
    logger.info(f"Creating HuggingFace LLM: repo_id={settings.HUGGINGFACE_REPO_ID}")
    
    # Create the endpoint
    endpoint = HuggingFaceEndpoint(
        repo_id=settings.HUGGINGFACE_REPO_ID,
        huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY,
        task="text-generation",
    )
    
    return ChatHuggingFace(llm=endpoint)


def _create_ollama_llm() -> BaseChatModel:
    """Create Ollama LLM client using langchain-ollama.
    
    For running open-source models locally via Ollama.
    Uses ChatOllama from langchain_ollama package.
    
    Returns:
        ChatOllama instance configured from settings.
    """
    from langchain_ollama import ChatOllama
    
    logger.info(f"Creating Ollama LLM: model={settings.OLLAMA_MODEL}, base_url={settings.OLLAMA_BASE_URL}")
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
    )


def _create_openai_compat_llm() -> BaseChatModel:
    """Create OpenAI-compatible LLM client using langchain-openai.
    
    For custom deployed models using OpenAI-compatible APIs.
    Examples: vLLM, TGI, LocalAI, LMStudio, etc.
    Uses ChatOpenAI with a custom base_url.
    
    Returns:
        ChatOpenAI instance configured for custom endpoint.
        
    Raises:
        ValueError: If OPENAI_COMPAT_BASE_URL is not set.
    """
    from langchain_openai import ChatOpenAI
    
    if not settings.OPENAI_COMPAT_BASE_URL:
        raise ValueError(
            "OPENAI_COMPAT_BASE_URL is required for the 'openai_compat' provider. "
            "Please set the base URL for your OpenAI-compatible endpoint."
        )
    
    if not settings.OPENAI_COMPAT_MODEL:
        raise ValueError(
            "OPENAI_COMPAT_MODEL is required for the 'openai_compat' provider. "
            "Please set the model name for your deployment."
        )
    
    logger.info(
        f"Creating OpenAI-Compatible LLM: model={settings.OPENAI_COMPAT_MODEL}, "
        f"base_url={settings.OPENAI_COMPAT_BASE_URL}"
    )
    
    kwargs = {
        "model": settings.OPENAI_COMPAT_MODEL,
        "base_url": settings.OPENAI_COMPAT_BASE_URL,
        "max_retries": settings.LLM_MAX_RETRIES,
        "temperature": settings.LLM_TEMPERATURE,
    }
    
    # Only add API key if provided (some local deployments don't require it)
    if settings.OPENAI_COMPAT_API_KEY:
        kwargs["api_key"] = settings.OPENAI_COMPAT_API_KEY
    else:
        # Set a dummy key for providers that require the field but don't validate
        kwargs["api_key"] = "not-needed"
    
    return ChatOpenAI(**kwargs)


# Provider factory mapping
_PROVIDER_FACTORIES: dict[str, callable] = {
    "openai": _create_openai_llm,
    "anthropic": _create_anthropic_llm,
    "gemini": _create_gemini_llm,
    "deepseek": _create_deepseek_llm,
    "groq": _create_groq_llm,
    "huggingface": _create_huggingface_llm,
    "ollama": _create_ollama_llm,
    "openai_compat": _create_openai_compat_llm,
}

# Cache for LLM instance
_llm_cache: BaseChatModel | None = None


def get_llm() -> BaseChatModel:
    """Get the configured LLM instance.
    
    Returns a cached instance of the LLM based on the configured provider.
    The provider is determined by the LLM_PROVIDER environment variable.
    
    Returns:
        BaseChatModel: The configured LLM instance.
        
    Raises:
        ValueError: If an unsupported provider is configured.
        ImportError: If the required LangChain package is not installed.
    """
    global _llm_cache
    
    if _llm_cache is not None:
        return _llm_cache
    
    provider: str = settings.LLM_PROVIDER
    
    if provider not in _PROVIDER_FACTORIES:
        supported = list(_PROVIDER_FACTORIES.keys())
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported providers: {supported}"
        )
    
    try:
        logger.info(f"Initializing LLM provider: {get_provider_display_name(provider)}")
        _llm_cache = _PROVIDER_FACTORIES[provider]()
        logger.info(f"LLM provider '{get_provider_display_name(provider)}' initialized successfully")
        return _llm_cache
    except ImportError as e:
        package = get_provider_package(provider)
        raise ImportError(
            f"Failed to import LLM provider '{provider}'. "
            f"Please install the required package: pip install {package}\n"
            f"Original error: {e}"
        ) from e


def clear_llm_cache() -> None:
    """Clear the cached LLM instance.
    
    Useful for testing or when settings change at runtime.
    """
    global _llm_cache
    _llm_cache = None
    logger.info("LLM cache cleared")


def get_llm_token_limit() -> int:
    """Get the configured token limit for the LLM.
    
    Returns:
        int: The maximum token limit from settings.
    """
    return settings.LLM_TOKEN_LIMIT


# =============================================================================
# Fallback/Supplementary LLM Functions
# =============================================================================

def get_fallback_llm() -> BaseChatModel:
    """Get a fallback/supplementary LLM instance for middleware operations.
    
    This creates a separate LLM instance for middleware operations like
    summarization, tool emulation, etc. It uses FALLBACK_LLM_PROVIDER and
    FALLBACK_LLM_MODEL if configured, otherwise falls back to the primary LLM.
    
    Returns:
        BaseChatModel: A configured LLM instance for middleware use.
    """
    # Check if fallback provider is configured
    fallback_provider = settings.FALLBACK_LLM_PROVIDER
    fallback_model = settings.FALLBACK_LLM_MODEL
    
    if fallback_provider and fallback_model:
        logger.info(f"Creating fallback LLM: provider={fallback_provider}, model={fallback_model}")
        return create_llm_by_provider(fallback_provider, fallback_model)
    
    # If no fallback configured, return a fresh instance of the primary LLM
    logger.debug("No fallback LLM configured, using primary LLM provider")
    provider = settings.LLM_PROVIDER
    return _PROVIDER_FACTORIES[provider]()


def create_llm_by_provider(provider: str, model: str = None) -> BaseChatModel:
    """Create an LLM instance for a specific provider and model.
    
    This allows creating LLM instances for any supported provider,
    useful for fallback chains or middleware that needs different models.
    
    Args:
        provider: The LLM provider (e.g., 'openai', 'anthropic', 'groq')
        model: Optional model override. If not provided, uses the default
               model from settings for that provider.
               
    Returns:
        BaseChatModel: A configured LLM instance.
        
    Raises:
        ValueError: If an unsupported provider is specified.
    """
    if provider not in _PROVIDER_FACTORIES:
        supported = list(_PROVIDER_FACTORIES.keys())
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported providers: {supported}"
        )
    
    # Create LLM with model override if provided
    if model:
        return _create_llm_with_model_override(provider, model)
    
    return _PROVIDER_FACTORIES[provider]()


def _create_llm_with_model_override(provider: str, model: str) -> BaseChatModel:
    """Create an LLM with a specific model override.
    
    Args:
        provider: The LLM provider
        model: The model name to use
        
    Returns:
        BaseChatModel: A configured LLM instance with the specified model.
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": model,
            "api_key": settings.OPENAI_API_KEY,
            "max_retries": settings.LLM_MAX_RETRIES,
            "temperature": settings.LLM_TEMPERATURE,
        }
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        return ChatOpenAI(**kwargs)
    
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            max_retries=settings.LLM_MAX_RETRIES,
            temperature=settings.LLM_TEMPERATURE,
        )
    
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = {
            "model": model,
            "google_api_key": settings.GOOGLE_API_KEY,
            "temperature": settings.LLM_TEMPERATURE,
        }
        if settings.GOOGLE_GENAI_USE_VERTEXAI:
            kwargs["vertexai"] = True
            if settings.GOOGLE_CLOUD_PROJECT:
                kwargs["project"] = settings.GOOGLE_CLOUD_PROJECT
        return ChatGoogleGenerativeAI(**kwargs)
    
    elif provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(
            model=model,
            api_key=settings.DEEPSEEK_API_KEY,
            max_retries=settings.LLM_MAX_RETRIES,
            temperature=settings.LLM_TEMPERATURE,
        )
    
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            api_key=settings.GROQ_API_KEY,
            max_retries=settings.LLM_MAX_RETRIES,
            temperature=settings.LLM_TEMPERATURE,
        )
    
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )
    
    elif provider == "openai_compat":
        from langchain_openai import ChatOpenAI
        if not settings.OPENAI_COMPAT_BASE_URL:
            raise ValueError("OPENAI_COMPAT_BASE_URL is required for openai_compat provider")
        kwargs = {
            "model": model,
            "base_url": settings.OPENAI_COMPAT_BASE_URL,
            "max_retries": settings.LLM_MAX_RETRIES,
            "temperature": settings.LLM_TEMPERATURE,
        }
        if settings.OPENAI_COMPAT_API_KEY:
            kwargs["api_key"] = settings.OPENAI_COMPAT_API_KEY
        else:
            kwargs["api_key"] = "not-needed"
        return ChatOpenAI(**kwargs)
    
    else:
        # Fallback to default factory
        return _PROVIDER_FACTORIES[provider]()


def get_fallback_model_identifiers() -> list[str]:
    """Get the list of fallback model identifiers from settings.
    
    Parses MIDDLEWARE_FALLBACK_MODELS which is a comma-separated string
    of model identifiers (e.g., "gpt-4o-mini,anthropic:claude-3-5-sonnet").
    
    Returns:
        list[str]: List of model identifier strings for ModelFallbackMiddleware.
    """
    fallback_models_str = settings.MIDDLEWARE_FALLBACK_MODELS
    if not fallback_models_str:
        return []
    
    # Parse comma-separated list and strip whitespace
    models = [m.strip() for m in fallback_models_str.split(',') if m.strip()]
    return models


# =============================================================================
# Backwards Compatibility Layer (Deprecated)
# =============================================================================
# These functions are kept for backwards compatibility during migration.
# They will be removed in a future version.

def get_llm_by_type(llm_type: str = "basic") -> BaseChatModel:
    """DEPRECATED: Use get_llm() instead.
    
    This function is kept for backwards compatibility during migration.
    It ignores the llm_type parameter and returns the configured LLM.
    
    Args:
        llm_type: Ignored. Previously used to select between 'basic', 'reasoning', etc.
        
    Returns:
        BaseChatModel: The configured LLM instance.
    """
    logger.warning(
        f"get_llm_by_type('{llm_type}') is DEPRECATED. "
        "The llm_type parameter is now ignored. Use get_llm() instead."
    )
    return get_llm()


def get_llm_token_limit_by_type(llm_type: str = "basic") -> int:
    """DEPRECATED: Use get_llm_token_limit() instead.
    
    This function is kept for backwards compatibility during migration.
    It ignores the llm_type parameter and returns the configured token limit.
    
    Args:
        llm_type: Ignored. Previously used to select between 'basic', 'reasoning', etc.
        
    Returns:
        int: The configured token limit.
    """
    logger.warning(
        f"get_llm_token_limit_by_type('{llm_type}') is DEPRECATED. "
        "The llm_type parameter is now ignored. Use get_llm_token_limit() instead."
    )
    return get_llm_token_limit()


def get_configured_llm_models() -> dict[str, list[str]]:
    """DEPRECATED: Returns current provider configuration.
    
    This function is kept for backwards compatibility.
    Returns a dict with the current provider and model.
    
    Returns:
        dict: Provider to model list mapping.
    """
    logger.warning(
        "get_configured_llm_models() is DEPRECATED. "
        "Use settings.LLM_PROVIDER directly instead."
    )
    provider = settings.LLM_PROVIDER
    
    # Build model info based on provider
    model_map = {
        "openai": settings.OPENAI_MODEL,
        "anthropic": settings.ANTHROPIC_MODEL,
        "gemini": settings.GEMINI_MODEL,
        "deepseek": settings.DEEPSEEK_MODEL,
        "groq": settings.GROQ_MODEL,
        "huggingface": settings.HUGGINGFACE_REPO_ID,
    }
    
    model = model_map.get(provider, "unknown")
    return {provider: [model]}
