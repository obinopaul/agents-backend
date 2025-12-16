"""Configuration for the sandbox server."""

from typing import Any, Dict, Optional
import os
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxServerConfig(BaseModel):
    """Configuration for the sandbox server."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8100, description="Server port")
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ii_sandbox",
        description="Database URL"
    )


class SandboxConfig(BaseModel):
    """Configuration for sandbox management.
    
    Adapts backend.core.conf.settings to Sandbox configuration.
    """
    
    def __init__(self, **data):
        from backend.core.conf import settings
        
        # Default values from settings
        data.setdefault("provider_type", "e2b")
        data.setdefault("timeout_seconds", 60 * 60 * 2) # 2 hours
        data.setdefault("pause_before_timeout_seconds", 60 * 10) # 10 minutes
        data.setdefault("timeout_buffer_seconds", 60 * 10)
        
        # Redis settings from main app
        data.setdefault("redis_url", settings.REDIS_URL) 
        data.setdefault("redis_tls_ca_path", None)
        data.setdefault("queue_name", "sandbox_lifecycle")
        data.setdefault("max_retries", 3)
        data.setdefault("queue_provider", "redis")
        
        # E2B settings
        # Try to find E2B keys in settings or env
        data.setdefault("e2b_api_key", getattr(settings, "E2B_API_KEY", None) or os.getenv("E2B_API_KEY"))
        data.setdefault("e2b_template_id", getattr(settings, "E2B_TEMPLATE_ID", "base") or os.getenv("E2B_TEMPLATE_ID", "base"))
        
        data.setdefault("default_cpu_limit", 1000)
        data.setdefault("default_memory_limit", 512)
        data.setdefault("default_disk_limit", 1024)
        data.setdefault("default_network_enabled", True)
        
        super().__init__(**data)

    # Sandbox provider settings
    provider_type: str = Field(
        default="e2b",
        description="Type of sandbox provider to use (e.g., 'e2b', 'docker')",
    )

    # Timeout settings
    timeout_seconds: int = Field(
        default=60 * 60 * 2,
        ge=1,
        le=60 * 60 * 24,  # Max 24 hours
        description="Default timeout for sandboxes in seconds",
    )
    pause_before_timeout_seconds: int = Field(
        default=60 * 10,
        ge=1,
        le=60 * 60 * 24,  # Max 24 hours
        description="Pause before timeout for sandboxes in seconds",
    )
    timeout_buffer_seconds: int = Field(
        default=60 * 10,
        ge=1,
        le=60 * 60 * 24,  # Max 24 hours
        description="Buffer after scheduled pause for sandboxes in seconds",
    )

    # Redis queue settings
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for message queue",
    )

    redis_tls_ca_path: Optional[str] = Field(
        default=None, description="Path to the CA certificate for SSL"
    )

    queue_name: str = Field(
        default="sandbox_lifecycle",
        description="Name of the Redis queue for lifecycle events",
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries for failed operations",
    )

    # Optional queue provider type (for future extensibility)
    queue_provider: Optional[str] = Field(
        default="redis",
        description="Type of message queue provider ('redis', 'gcp_pubsub', or None)",
    )

    # E2B specific settings (if using E2B provider)
    e2b_api_key: Optional[str] = Field(
        default=None, description="API key for E2B sandbox provider"
    )

    e2b_template_id: Optional[str] = Field(
        default="default", description="Default E2B template to use for sandboxes"
    )

    # Resource limits defaults
    default_cpu_limit: int = Field(
        default=1000, ge=100, le=8000, description="Default CPU limit in millicores"
    )

    default_memory_limit: int = Field(
        default=512, ge=128, le=16384, description="Default memory limit in MB"
    )

    default_disk_limit: int = Field(
        default=1024, ge=256, le=102400, description="Default disk limit in MB"
    )

    default_network_enabled: bool = Field(
        default=True, description="Whether network access is enabled by default"
    )

    @model_validator(mode="after")
    def validate_queue_settings(self) -> "SandboxConfig":
        """Validate queue-related settings based on provider type."""
        if self.queue_provider == "redis" and not self.redis_url:
            raise ValueError("redis_url is required when queue_provider is 'redis'")

        if self.provider_type == "e2b" and not self.e2b_api_key:
            raise ValueError(
                "E2B API key is required. Set E2B_API_KEY environment variable"
            )

        return self

    @property
    def has_queue_provider(self) -> bool:
        """Check if a queue provider is configured."""
        return self.queue_provider is not None

    @property
    def sandbox_provider(self) -> str:
        """Alias for provider_type for backward compatibility."""
        return self.provider_type

    def get_provider_config(self) -> Dict[str, Any]:
        """Get provider-specific configuration."""
        if self.provider_type == "e2b":
            return {
                "api_key": self.e2b_api_key,
                "template": self.e2b_template_id,
            }
        # Add other provider configs as needed
        return {}

    def get_queue_config(self) -> Optional[Dict[str, Any]]:
        """Get queue provider configuration."""
        if not self.queue_provider:
            return None

        if self.queue_provider == "redis":
            return {
                "redis_url": self.redis_url,
                "queue_name": self.queue_name,
                "max_retries": self.max_retries,
            }

        # Add other queue provider configs as needed (e.g., GCP Pub/Sub)
        return None
