"""Database configuration for external database providers.

This module configures API credentials for dynamically provisioning databases:
- Postgres via Neon Cloud (default)
- Redis via Upstash
- MySQL via PlanetScale

Environment variables use the DATABASE_ prefix.
"""

from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Configuration for database provisioning providers.
    
    All fields are loaded from environment variables with DATABASE_ prefix.
    Example: DATABASE_NEON_DB_API_KEY -> neon_db_api_key
    """
    
    # =========================================================================
    # PostgreSQL (Neon) - DEFAULT PROVIDER
    # https://console.neon.tech/api
    # =========================================================================
    neon_db_api_key: str | None = None
    
    # =========================================================================
    # Redis (Upstash)
    # https://upstash.com/docs/devops/developer-api
    # =========================================================================
    upstash_email: str | None = None
    upstash_api_key: str | None = None
    upstash_region: str = "us-east-1"  # Default region for new databases
    
    # =========================================================================
    # MySQL (PlanetScale)
    # https://planetscale.com/docs/api/reference/getting-started-with-planetscale-api
    # =========================================================================
    planetscale_service_token_id: str | None = None
    planetscale_service_token: str | None = None
    planetscale_organization: str | None = None
    planetscale_region: str = "us-east-1"  # Default region for new databases

    class Config:
        env_prefix = "DATABASE_"
        # Look for .env in multiple locations (project root and backend folder)
        env_file = ("backend/.env", ".env")
        extra = "ignore"