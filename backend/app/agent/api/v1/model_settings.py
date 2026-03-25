"""User Model Settings API endpoints.

Provides user-facing API for retrieving available LLM models from
the backend configuration and (future) user-configured models.

Endpoints:
- GET /user-settings/models - List all available models
- GET /user-settings/models/{model_id} - Get specific model info
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.agent.schema.model_setting import (
    APIType,
    ModelInfo,
    ModelSettingsResponse,
    ModelSource,
    get_model_capabilities,
)
from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.src.config.agents import PROVIDER_DISPLAY_NAMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-settings/models", tags=["User Model Settings"])


# =============================================================================
# Helper Functions
# =============================================================================

def _get_api_type_from_provider(provider: str) -> APIType:
    """Convert provider string to APIType enum."""
    provider_map = {
        "openai": APIType.OPENAI,
        "anthropic": APIType.ANTHROPIC,
        "gemini": APIType.GEMINI,
        "deepseek": APIType.DEEPSEEK,
        "groq": APIType.GROQ,
        "huggingface": APIType.HUGGINGFACE,
        "ollama": APIType.OLLAMA,
        "openai_compat": APIType.OPENAI_COMPAT,
    }
    return provider_map.get(provider.lower(), APIType.CUSTOM)


def _get_model_name_for_provider(provider: str) -> str:
    """Get the configured model name for a provider from settings."""
    model_map = {
        "openai": settings.OPENAI_MODEL,
        "anthropic": settings.ANTHROPIC_MODEL,
        "gemini": settings.GEMINI_MODEL,
        "deepseek": settings.DEEPSEEK_MODEL,
        "groq": settings.GROQ_MODEL,
        "huggingface": settings.HUGGINGFACE_REPO_ID,
        "ollama": settings.OLLAMA_MODEL,
        "openai_compat": settings.OPENAI_COMPAT_MODEL,
    }
    return model_map.get(provider.lower(), "")


def _check_provider_configured(provider: str) -> bool:
    """Check if a provider has API key configured."""
    key_map = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "gemini": settings.GOOGLE_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
        "groq": settings.GROQ_API_KEY,
        "huggingface": settings.HUGGINGFACE_API_KEY,
        "ollama": True,  # Ollama doesn't need API key
        "openai_compat": settings.OPENAI_COMPAT_API_KEY or settings.OPENAI_COMPAT_BASE_URL,
    }
    api_key = key_map.get(provider.lower())
    return bool(api_key)


def _get_base_url_for_provider(provider: str) -> Optional[str]:
    """Get base URL for a provider if configured."""
    if provider == "openai" and settings.OPENAI_BASE_URL:
        return settings.OPENAI_BASE_URL
    if provider == "ollama":
        return settings.OLLAMA_BASE_URL
    if provider == "openai_compat":
        return settings.OPENAI_COMPAT_BASE_URL
    return None


def _build_model_info(provider: str, model_name: str, is_primary: bool = False) -> ModelInfo:
    """Build a ModelInfo object for a provider/model combination.
    
    Args:
        provider: LLM provider name
        model_name: Model name/identifier
        is_primary: Whether this is the primary configured model
        
    Returns:
        ModelInfo with all available information
    """
    api_type = _get_api_type_from_provider(provider)
    display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider.title())
    capabilities = get_model_capabilities(provider, model_name)
    is_configured = _check_provider_configured(provider)
    
    # Build unique ID
    model_id = f"{provider}:{model_name}"
    
    # Get model-specific display name or fall back to provider name
    model_display_name = capabilities.get("display_name", model_name)
    if is_primary:
        description = f"Primary {display_name} model (from backend config)"
    else:
        description = f"{display_name} model"
    
    return ModelInfo(
        id=model_id,
        model=model_name,
        api_type=api_type,
        display_name=model_display_name,
        description=description,
        source=ModelSource.SYSTEM,
        base_url=_get_base_url_for_provider(provider),
        context_length=capabilities.get("context_length"),
        supports_function_calling=capabilities.get("supports_function_calling", True),
        supports_vision=capabilities.get("supports_vision", False),
        supports_streaming=True,
        is_active=is_primary,
        is_configured=is_configured,
    )


def _get_all_available_models() -> list[ModelInfo]:
    """Get all available models from backend configuration.
    
    For SaaS mode, returns ALL known models from KNOWN_MODELS registry,
    organized by provider with configured providers marked accordingly.
    Users don't need to provide API keys - the backend handles all configuration.
    
    Returns:
        List of ModelInfo objects for all available models
    """
    from backend.app.agent.schema.model_setting import KNOWN_MODELS
    
    models = []
    primary_provider = settings.LLM_PROVIDER
    primary_model = _get_model_name_for_provider(primary_provider)
    
    # Define provider order for display (most popular first)
    provider_order = [
        "openai", "anthropic", "gemini", "deepseek",
        "groq", "huggingface", "ollama", "openai_compat"
    ]
    
    # Add all models from KNOWN_MODELS registry
    for provider in provider_order:
        provider_models = KNOWN_MODELS.get(provider, {})
        is_provider_configured = _check_provider_configured(provider)
        
        for model_name, model_config in provider_models.items():
            # Determine if this is the active/primary model
            is_primary = (provider == primary_provider and model_name == primary_model)
            
            api_type = _get_api_type_from_provider(provider)
            display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider.title())
            
            model_info = ModelInfo(
                id=f"{provider}:{model_name}",
                model=model_name,
                api_type=api_type,
                display_name=model_config.get("display_name", model_name),
                description=f"{display_name} model",
                source=ModelSource.SYSTEM,
                base_url=_get_base_url_for_provider(provider),
                context_length=model_config.get("context_length"),
                supports_function_calling=model_config.get("supports_function_calling", True),
                supports_vision=model_config.get("supports_vision", False),
                supports_streaming=True,
                is_active=is_primary,
                is_configured=is_provider_configured,
            )
            models.append(model_info)
    
    return models


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "",
    response_model=ModelSettingsResponse,
    summary="List available LLM models",
    description="""
    Get all available LLM models for the current user (SaaS mode).
    
    Returns ALL models from the system registry organized by provider.
    Models from configured providers are marked as available.
    The primary model (LLM_PROVIDER) is marked as active.
    
    Users do not need to provide API keys - the backend handles all configuration.
    """,
    dependencies=[DependsJwtAuth],
)
async def list_available_models() -> ModelSettingsResponse:
    """List all available LLM models.
    
    Returns all models from the system registry.
    The primary model is determined by LLM_PROVIDER env variable.
    """
    try:
        models = _get_all_available_models()
        
        # Find the primary/active model ID
        primary_id = None
        for model in models:
            if model.is_active:
                primary_id = model.id
                break
        
        logger.info(
            f"Returning {len(models)} available models, "
            f"primary={settings.LLM_PROVIDER}:{_get_model_name_for_provider(settings.LLM_PROVIDER)}"
        )
        
        return ModelSettingsResponse(
            models=models,
            default_model_id=primary_id,
            total=len(models),
        )
    except Exception as e:
        logger.error(f"Error fetching available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{model_id}",
    response_model=ModelInfo,
    summary="Get model by ID",
    description="Get specific model information by its ID (format: provider:model_name).",
    dependencies=[DependsJwtAuth],
)
async def get_model_by_id(model_id: str) -> ModelInfo:
    """Get specific model information.
    
    Args:
        model_id: Model ID in format 'provider:model_name'
        
    Returns:
        ModelInfo for the requested model
        
    Raises:
        404 if model not found
    """
    # Parse model_id
    if ":" not in model_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid model_id format. Expected 'provider:model_name'"
        )
    
    provider, model_name = model_id.split(":", 1)
    
    # Check if provider is valid and configured
    if not _check_provider_configured(provider):
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider}' is not configured"
        )
    
    # Check if this is the configured model for the provider
    configured_model = _get_model_name_for_provider(provider)
    if model_name != configured_model:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found for provider '{provider}'"
        )
    
    is_primary = provider == settings.LLM_PROVIDER
    return _build_model_info(provider, model_name, is_primary=is_primary)


@router.get(
    "/providers/list",
    summary="List available providers",
    description="Get a list of all LLM providers and their configuration status.",
    dependencies=[DependsJwtAuth],
)
async def list_providers() -> dict:
    """List all available LLM providers with configuration status.
    
    Returns:
        Dictionary with provider information
    """
    providers = []
    
    for provider in ["openai", "anthropic", "gemini", "deepseek", "groq", "huggingface", "ollama", "openai_compat"]:
        is_configured = _check_provider_configured(provider)
        is_primary = provider == settings.LLM_PROVIDER
        
        providers.append({
            "id": provider,
            "display_name": PROVIDER_DISPLAY_NAMES.get(provider, provider.title()),
            "is_configured": is_configured,
            "is_primary": is_primary,
            "model": _get_model_name_for_provider(provider) if is_configured else None,
        })
    
    return {
        "providers": providers,
        "primary_provider": settings.LLM_PROVIDER,
        "total": len(providers),
    }
