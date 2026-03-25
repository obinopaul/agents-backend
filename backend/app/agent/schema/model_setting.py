"""User Model Settings Pydantic schemas.

Provides schemas for the user-settings/models endpoint that returns
available LLM models from the backend configuration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class APIType(str, Enum):
    """Supported LLM API types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    OPENAI_COMPAT = "openai_compat"
    CUSTOM = "custom"


class ModelSource(str, Enum):
    """Source of the model configuration."""
    SYSTEM = "system"  # Configured in backend settings
    USER = "user"      # User-provided API key (future)


class ModelCapabilities(BaseModel):
    """Model capability flags."""
    supports_function_calling: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_json_mode: bool = False
    max_context_length: Optional[int] = None


class ModelInfo(BaseModel):
    """LLM model information for frontend display.
    
    Matches the frontend IModel interface in settings.ts.
    """
    id: str = Field(..., description="Unique model identifier")
    model: str = Field(..., description="Model name (e.g., 'gpt-4o', 'claude-sonnet-4')")
    api_type: APIType = Field(..., description="API provider type")
    display_name: str = Field(..., description="Human-readable display name")
    description: Optional[str] = Field(None, description="Model description")
    source: ModelSource = Field(default=ModelSource.SYSTEM, description="Configuration source")
    
    # Optional configuration fields
    base_url: Optional[str] = Field(None, description="Base URL for API endpoint")
    context_length: Optional[int] = Field(None, description="Maximum context length in tokens")
    input_price_per_token: Optional[float] = Field(None, description="Input cost per token")
    output_price_per_token: Optional[float] = Field(None, description="Output cost per token")
    
    # Capability flags
    supports_function_calling: bool = Field(default=True, description="Supports tool calling")
    supports_vision: bool = Field(default=False, description="Supports image inputs")
    supports_streaming: bool = Field(default=True, description="Supports streaming responses")
    
    # Metadata
    is_active: bool = Field(default=True, description="Whether model is currently active")
    is_configured: bool = Field(default=False, description="Whether API key is configured")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    class Config:
        use_enum_values = True


class ModelSettingsResponse(BaseModel):
    """Response for GET /user-settings/models endpoint.
    
    Returns list of available models matching frontend GetAvailableModelsResponse.
    """
    models: list[ModelInfo] = Field(default_factory=list, description="List of available models")
    default_model_id: Optional[str] = Field(None, description="Currently active/default model ID")
    total: int = Field(default=0, description="Total number of models")

    class Config:
        use_enum_values = True


class ModelSettingCreate(BaseModel):
    """Request to create/configure a user model setting.
    
    For future use when users can add their own API keys.
    """
    model: str = Field(..., description="Model name")
    api_type: APIType = Field(..., description="API provider type")
    api_key: str = Field(..., description="API key for the model")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    max_retries: int = Field(default=3, description="Maximum retries")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Generation temperature")
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata")


class ModelSettingUpdate(BaseModel):
    """Request to update an existing model setting."""
    api_key: Optional[str] = Field(None, description="New API key")
    base_url: Optional[str] = Field(None, description="New base URL")
    max_retries: Optional[int] = Field(None, description="New max retries")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="New temperature")
    is_active: Optional[bool] = Field(None, description="Active status")
    metadata: Optional[dict[str, Any]] = Field(None, description="New metadata")


# =============================================================================
# Provider-specific model configurations
# =============================================================================

# Known models per provider with their capabilities - comprehensive list for SaaS
KNOWN_MODELS: dict[str, dict[str, Any]] = {
    "openai": {
        "gpt-5": {
            "display_name": "GPT-5",
            "context_length": 128000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "gpt-5.1": {
            "display_name": "GPT-5.1",
            "context_length": 128000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "gpt-5.2": {
            "display_name": "GPT-5.2",
            "context_length": 128000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "o4-mini": {
            "display_name": "o4 Mini",
            "context_length": 128000,
            "supports_vision": False,
            "supports_function_calling": True,
        },
    },
    "anthropic": {
        "claude-sonnet-4-5-20250929": {
            "display_name": "Claude Sonnet 4.5",
            "context_length": 200000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "claude-sonnet-4-20250514": {
            "display_name": "Claude Sonnet 4",
            "context_length": 200000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "claude-opus-4-20250514": {
            "display_name": "Claude Opus 4",
            "context_length": 200000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "claude-3-7-sonnet-20250219": {
            "display_name": "Claude 3.7 Sonnet",
            "context_length": 200000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "claude-3-5-sonnet-20241022": {
            "display_name": "Claude 3.5 Sonnet",
            "context_length": 200000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
    },
    "gemini": {
        "gemini-2.5-flash": {
            "display_name": "Gemini 2.5 Flash",
            "context_length": 1000000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "gemini-2.5-pro": {
            "display_name": "Gemini 2.5 Pro",
            "context_length": 1000000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
        "gemini-2.0-flash": {
            "display_name": "Gemini 2.0 Flash",
            "context_length": 1000000,
            "supports_vision": True,
            "supports_function_calling": True,
        },
    },
    "deepseek": {
        "deepseek-chat": {
            "display_name": "DeepSeek Chat",
            "context_length": 64000,
            "supports_vision": False,
            "supports_function_calling": True,
        },
        "deepseek-reasoner": {
            "display_name": "DeepSeek Reasoner",
            "context_length": 64000,
            "supports_vision": False,
            "supports_function_calling": True,
        },
    },
    "groq": {
        "llama-3.1-8b-instant": {
            "display_name": "Llama 3.1 8B (Groq)",
            "context_length": 131072,
            "supports_vision": False,
            "supports_function_calling": True,
        },
        "llama-3.1-70b-versatile": {
            "display_name": "Llama 3.1 70B (Groq)",
            "context_length": 131072,
            "supports_vision": False,
            "supports_function_calling": True,
        },
        "mixtral-8x7b-32768": {
            "display_name": "Mixtral 8x7B (Groq)",
            "context_length": 32768,
            "supports_vision": False,
            "supports_function_calling": True,
        },
    },
    "huggingface": {
        "microsoft/Phi-3-mini-4k-instruct": {
            "display_name": "Phi-3 Mini 4K",
            "context_length": 4096,
            "supports_vision": False,
            "supports_function_calling": False,
        },
        "meta-llama/Meta-Llama-3-8B-Instruct": {
            "display_name": "Llama 3 8B (HF)",
            "context_length": 8192,
            "supports_vision": False,
            "supports_function_calling": False,
        },
    },
    "ollama": {
        "llama3": {
            "display_name": "Llama 3 (Local)",
            "context_length": 8192,
            "supports_vision": False,
            "supports_function_calling": True,
        },
        "codellama": {
            "display_name": "Code Llama (Local)",
            "context_length": 16384,
            "supports_vision": False,
            "supports_function_calling": False,
        },
        "mistral": {
            "display_name": "Mistral (Local)",
            "context_length": 8192,
            "supports_vision": False,
            "supports_function_calling": True,
        },
    },
}


def get_model_capabilities(provider: str, model: str) -> dict[str, Any]:
    """Get known capabilities for a model.
    
    Args:
        provider: LLM provider name
        model: Model name
        
    Returns:
        Dictionary of model capabilities
    """
    provider_models = KNOWN_MODELS.get(provider, {})
    return provider_models.get(model, {
        "display_name": model.replace("-", " ").title(),
        "context_length": None,
        "supports_vision": False,
        "supports_function_calling": True,
    })
