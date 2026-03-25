"""Database provisioning integration module.

This module provides dynamic database provisioning for sandbox applications.

Supported Providers:
- PostgreSQL via Neon Cloud (default)
- Redis via Upstash
- MySQL via PlanetScale

Usage:
    from backend.src.tool_server.integrations.database import (
        create_database_client,
        DatabaseConfig,
    )
    
    config = DatabaseConfig()  # Loads from environment
    client = create_database_client("postgres", config)
    connection_string = await client.get_database_connection()
"""

from .factory import (
    create_database_client,
    DatabaseClient,
    PostgresDatabaseClient,
    UpstashRedisDatabaseClient,
    PlanetScaleMySQLDatabaseClient,
    # Legacy aliases
    RedisDatabaseClient,
    MySQLDatabaseClient,
)
from .config import DatabaseConfig


__all__ = [
    # Factory function
    "create_database_client",
    # Config
    "DatabaseConfig",
    # Base class
    "DatabaseClient",
    # Specific clients
    "PostgresDatabaseClient",
    "UpstashRedisDatabaseClient",
    "PlanetScaleMySQLDatabaseClient",
    # Legacy aliases
    "RedisDatabaseClient",
    "MySQLDatabaseClient",
]