"""LLM Provider configuration for agents.

This module defines the available LLM providers and their display names.
The actual provider selection is done via the LLM_PROVIDER environment variable.
"""

from typing import Literal

# Define available LLM providers
LLMProvider = Literal[
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "groq",
    "huggingface",
    "ollama",
    "openai_compat",
]

# Provider display names for logging and UI
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Google Gemini",
    "deepseek": "DeepSeek",
    "groq": "Groq",
    "huggingface": "HuggingFace",
    "ollama": "Ollama (Local)",
    "openai_compat": "OpenAI-Compatible API",
}

# Provider package names for installation instructions
PROVIDER_PACKAGES: dict[str, str] = {
    "openai": "langchain-openai",
    "anthropic": "langchain-anthropic",
    "gemini": "langchain-google-genai",
    "deepseek": "langchain-deepseek",
    "groq": "langchain-groq",
    "huggingface": "langchain-huggingface",
    "ollama": "langchain-ollama",
    "openai_compat": "langchain-openai",  # Uses the same package as openai
}


def get_provider_display_name(provider: str) -> str:
    """Get the display name for a provider.
    
    Args:
        provider: Provider identifier (e.g., 'openai', 'anthropic')
        
    Returns:
        Human-readable provider name (e.g., 'OpenAI', 'Anthropic')
    """
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.title())


def get_provider_package(provider: str) -> str:
    """Get the pip package name for a provider.
    
    Args:
        provider: Provider identifier (e.g., 'openai', 'anthropic')
        
    Returns:
        Package name for pip install (e.g., 'langchain-openai')
    """
    return PROVIDER_PACKAGES.get(provider, f"langchain-{provider}")
