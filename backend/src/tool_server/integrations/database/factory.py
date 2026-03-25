"""Database client factory for dynamic database provisioning.

This module provides production-grade database provisioning clients for:
- PostgreSQL via Neon Cloud (default)
- Redis via Upstash REST API
- MySQL via PlanetScale API

Each client supports:
- Creating new databases dynamically
- Listing existing databases for quota management
- Deleting databases for cleanup
- Automatic resource management (free up quota when limits exceeded)

Usage:
    from backend.src.tool_server.integrations.database import create_database_client, DatabaseConfig
    
    config = DatabaseConfig()  # Loads from environment
    client = create_database_client("postgres", config)  # or "redis", "mysql"
    connection_string = await client.get_database_connection()
"""

from abc import ABC, abstractmethod
import asyncio
import base64
import logging
import uuid
from typing import Optional

import aiohttp

from .config import DatabaseConfig


logger = logging.getLogger(__name__)

# =============================================================================
# Error Messages
# =============================================================================

NEON_DB_KEY_ERROR_MSG = (
    "Neon API key not configured. Set DATABASE_NEON_DB_API_KEY environment variable. "
    "Get your API key from https://console.neon.tech/app/settings/api-keys"
)

UPSTASH_KEY_ERROR_MSG = (
    "Upstash credentials not configured. Set DATABASE_UPSTASH_EMAIL and DATABASE_UPSTASH_API_KEY "
    "environment variables. Get your credentials from https://console.upstash.com/account/api"
)

PLANETSCALE_KEY_ERROR_MSG = (
    "PlanetScale credentials not configured. Set DATABASE_PLANETSCALE_SERVICE_TOKEN_ID, "
    "DATABASE_PLANETSCALE_SERVICE_TOKEN, and DATABASE_PLANETSCALE_ORGANIZATION environment variables. "
    "Create a service token at https://app.planetscale.com/{org}/settings/service-tokens"
)

# =============================================================================
# Default Settings
# =============================================================================

DEFAULT_TIMEOUT = 45  # seconds for API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries
MAX_DATABASES_BEFORE_CLEANUP = 90  # Start cleanup before hitting 100 limit


# =============================================================================
# Base Class
# =============================================================================

class DatabaseClient(ABC):
    """Abstract base class for database provisioning clients."""
    
    @abstractmethod
    async def get_database_connection(self) -> str:
        """Get a database connection string.
        
        Creates a new database if needed, manages quotas, and returns
        a ready-to-use connection string.
        
        Returns:
            Connection string in the appropriate format for the database type.
            
        Raises:
            ValueError: If required credentials are not configured.
            Exception: If database creation fails.
        """
        pass


# =============================================================================
# PostgreSQL (Neon) Client
# =============================================================================

class PostgresDatabaseClient(DatabaseClient):
    """PostgreSQL database provisioning via Neon Cloud.
    
    Creates serverless PostgreSQL databases on Neon. Each database is a 
    separate Neon project with its own resources.
    
    API Reference: https://api-docs.neon.tech/reference/getting-started-with-neon-api
    """
    
    BASE_URL = "https://console.neon.tech/api/v2"
    
    def __init__(self, setting: DatabaseConfig):
        self.setting = setting
        self.neon_db_api_key = setting.neon_db_api_key

    def _get_headers(self) -> dict:
        """Get authorization headers for Neon API."""
        return {
            "Authorization": f"Bearer {self.neon_db_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_all_postgres_databases(self) -> list[dict]:
        """Get all PostgreSQL databases (Neon projects).
        
        Returns:
            List of project dicts with 'id' and 'name' keys.
        """
        if not self.neon_db_api_key:
            raise ValueError(NEON_DB_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.BASE_URL}/projects?limit=100",
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Failed to list Neon projects: {response.status} - {text}")
                    
                    data = await response.json()
                    projects = data.get("projects", [])
                    return [{"id": p["id"], "name": p.get("name", "")} for p in projects]
                    
        except aiohttp.ClientError as e:
            raise Exception(f"Network error listing Neon databases: {str(e)}")

    async def delete_postgres_database(self, database_id: str) -> bool:
        """Delete a Neon project (PostgreSQL database).
        
        Args:
            database_id: The Neon project ID to delete.
            
        Returns:
            True if deletion was successful.
        """
        if not self.neon_db_api_key:
            raise ValueError(NEON_DB_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.delete(
                    f"{self.BASE_URL}/projects/{database_id}",
                    headers=headers,
                ) as response:
                    if response.status in (200, 204):
                        logger.info(f"Deleted Neon database: {database_id}")
                        return True
                    else:
                        text = await response.text()
                        raise Exception(
                            f"Failed to delete Neon database: {response.status} - {text}"
                        )
        except aiohttp.ClientError as e:
            raise Exception(f"Network error deleting Neon database: {str(e)}")

    async def free_up_database_resources(self) -> None:
        """Free up database resources by deleting oldest projects.
        
        Neon has project limits. This method deletes the oldest projects
        when approaching the limit.
        """
        if not self.neon_db_api_key:
            raise ValueError(NEON_DB_KEY_ERROR_MSG)
            
        databases = await self.get_all_postgres_databases()
        
        while len(databases) >= MAX_DATABASES_BEFORE_CLEANUP:
            logger.warning(f"Neon quota approaching: {len(databases)} databases. Cleaning up oldest...")
            # Delete oldest (first in list)
            await self.delete_postgres_database(databases[0]["id"])
            databases = await self.get_all_postgres_databases()
            await asyncio.sleep(1)  # Rate limit protection

    async def create_postgresql(self) -> str:
        """Create a new PostgreSQL database on Neon.
        
        Returns:
            PostgreSQL connection string.
        """
        if not self.neon_db_api_key:
            raise ValueError(NEON_DB_KEY_ERROR_MSG)

        headers = self._get_headers()
        payload = {
            "project": {
                "pg_version": 17,
                "name": f"sandbox-{uuid.uuid4().hex[:8]}",
            }
        }

        for attempt in range(MAX_RETRIES):
            try:
                timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.BASE_URL}/projects",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status == 201:
                            project_data = await response.json()
                            connection_uris = project_data.get("connection_uris", [])
                            if connection_uris:
                                uri = connection_uris[0]["connection_uri"]
                                logger.info(f"Created Neon PostgreSQL database")
                                return uri
                            raise Exception("No connection URIs in Neon response")
                        else:
                            text = await response.text()
                            
                            # Check for quota exceeded
                            if "limit" in text.lower() or response.status == 402:
                                logger.warning("Neon quota exceeded, cleaning up...")
                                await self.free_up_database_resources()
                                continue
                                
                            raise Exception(
                                f"Failed to create Neon project: {response.status} - {text}"
                            )
            except aiohttp.ClientError as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Neon API error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise Exception(f"Network error creating Neon database: {str(e)}")
        
        raise Exception("Failed to create Neon database after all retries")

    async def get_database_connection(self) -> str:
        """Get a PostgreSQL connection string.
        
        Manages quotas and creates a new database.
        
        Returns:
            PostgreSQL connection URI.
        """
        await self.free_up_database_resources()
        return await self.create_postgresql()


# =============================================================================
# Redis (Upstash) Client
# =============================================================================

class UpstashRedisDatabaseClient(DatabaseClient):
    """Redis database provisioning via Upstash REST API.
    
    Creates serverless Redis databases on Upstash. Each database is isolated
    with its own credentials and endpoint.
    
    API Reference: https://upstash.com/docs/devops/developer-api
    """
    
    BASE_URL = "https://api.upstash.com/v2"
    
    def __init__(self, setting: DatabaseConfig):
        self.setting = setting
        self.email = setting.upstash_email
        self.api_key = setting.upstash_api_key
        self.region = setting.upstash_region or "us-east-1"

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header for Upstash API.
        
        Upstash uses Basic Auth with email:api_key format.
        """
        if not self.email or not self.api_key:
            raise ValueError(UPSTASH_KEY_ERROR_MSG)
            
        credentials = f"{self.email}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def _get_headers(self) -> dict:
        """Get authorization headers for Upstash API."""
        return {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_all_redis_databases(self) -> list[dict]:
        """Get all Redis databases from Upstash.
        
        Returns:
            List of database dicts with 'database_id', 'database_name', etc.
        """
        if not self.email or not self.api_key:
            raise ValueError(UPSTASH_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.BASE_URL}/redis/databases",
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Failed to list Upstash databases: {response.status} - {text}")
                    
                    databases = await response.json()
                    # Response is a list directly
                    if isinstance(databases, list):
                        return databases
                    return []
                    
        except aiohttp.ClientError as e:
            raise Exception(f"Network error listing Upstash databases: {str(e)}")

    async def delete_redis_database(self, database_id: str) -> bool:
        """Delete an Upstash Redis database.
        
        Args:
            database_id: The Upstash database ID to delete.
            
        Returns:
            True if deletion was successful.
        """
        if not self.email or not self.api_key:
            raise ValueError(UPSTASH_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.delete(
                    f"{self.BASE_URL}/redis/database/{database_id}",
                    headers=headers,
                ) as response:
                    if response.status in (200, 204):
                        logger.info(f"Deleted Upstash Redis database: {database_id}")
                        return True
                    else:
                        text = await response.text()
                        raise Exception(
                            f"Failed to delete Upstash database: {response.status} - {text}"
                        )
        except aiohttp.ClientError as e:
            raise Exception(f"Network error deleting Upstash database: {str(e)}")

    async def free_up_database_resources(self) -> None:
        """Free up database resources by deleting oldest databases.
        
        Upstash has database limits per account. This method deletes
        the oldest databases when approaching the limit.
        """
        if not self.email or not self.api_key:
            raise ValueError(UPSTASH_KEY_ERROR_MSG)
            
        databases = await self.get_all_redis_databases()
        
        while len(databases) >= MAX_DATABASES_BEFORE_CLEANUP:
            logger.warning(f"Upstash quota approaching: {len(databases)} databases. Cleaning up oldest...")
            # Delete oldest by creation_time (first in list is usually oldest)
            oldest = databases[0]
            await self.delete_redis_database(oldest["database_id"])
            databases = await self.get_all_redis_databases()
            await asyncio.sleep(1)  # Rate limit protection

    async def create_redis_database(self) -> str:
        """Create a new Redis database on Upstash.
        
        Returns:
            Redis connection string in format: rediss://default:{password}@{endpoint}:{port}
        """
        if not self.email or not self.api_key:
            raise ValueError(UPSTASH_KEY_ERROR_MSG)

        headers = self._get_headers()
        
        # Generate unique database name
        db_name = f"sandbox-{uuid.uuid4().hex[:8]}"
        
        # Note: Upstash deprecated regional databases.
        # All databases are now "global" with a primary_region.
        # region="global" means multi-region, primary_region is where writes go.
        payload = {
            "name": db_name,
            "region": "global",             # Must be "global" for new databases
            "primary_region": self.region,  # AWS region for primary writes (e.g., "us-west-1")
            "tls": True,                    # Always use TLS for security
        }




        for attempt in range(MAX_RETRIES):
            try:
                timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.BASE_URL}/redis/database",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status in (200, 201):
                            data = await response.json()
                            
                            # Extract connection details
                            endpoint = data.get("endpoint")
                            port = data.get("port", 6379)
                            password = data.get("password")
                            
                            if not endpoint or not password:
                                raise Exception(
                                    f"Incomplete Upstash response. Missing endpoint or password. "
                                    f"Got: {list(data.keys())}"
                                )
                            
                            # Build connection string
                            # Format: rediss://default:{password}@{endpoint}:{port}
                            connection_string = f"rediss://default:{password}@{endpoint}:{port}"
                            
                            logger.info(f"Created Upstash Redis database: {db_name}")
                            return connection_string
                            
                        else:
                            text = await response.text()
                            
                            # Check for quota exceeded
                            if "limit" in text.lower() or "quota" in text.lower() or response.status == 402:
                                logger.warning("Upstash quota exceeded, cleaning up...")
                                await self.free_up_database_resources()
                                continue
                                
                            raise Exception(
                                f"Failed to create Upstash database: {response.status} - {text}"
                            )
                            
            except aiohttp.ClientError as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Upstash API error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise Exception(f"Network error creating Upstash database: {str(e)}")
        
        raise Exception("Failed to create Upstash Redis database after all retries")

    async def get_database_connection(self) -> str:
        """Get a Redis connection string.
        
        Manages quotas and creates a new database.
        
        Returns:
            Redis connection URI (rediss://...).
        """
        await self.free_up_database_resources()
        return await self.create_redis_database()


# =============================================================================
# MySQL (PlanetScale) Client
# =============================================================================

class PlanetScaleMySQLDatabaseClient(DatabaseClient):
    """MySQL database provisioning via PlanetScale API.
    
    Creates serverless MySQL databases on PlanetScale. Each database is
    a separate PlanetScale database with its own branches and credentials.
    
    API Reference: https://planetscale.com/docs/api/reference/getting-started-with-planetscale-api
    """
    
    BASE_URL = "https://api.planetscale.com/v1"
    
    def __init__(self, setting: DatabaseConfig):
        self.setting = setting
        self.token_id = setting.planetscale_service_token_id
        self.token = setting.planetscale_service_token
        self.organization = setting.planetscale_organization
        self.region = setting.planetscale_region or "us-east-1"

    def _get_headers(self) -> dict:
        """Get authorization headers for PlanetScale API.
        
        PlanetScale uses a custom format: {token_id}:{token}
        """
        if not self.token_id or not self.token:
            raise ValueError(PLANETSCALE_KEY_ERROR_MSG)
        if not self.organization:
            raise ValueError(
                "PlanetScale organization not configured. "
                "Set DATABASE_PLANETSCALE_ORGANIZATION environment variable."
            )
            
        return {
            "Authorization": f"{self.token_id}:{self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_all_mysql_databases(self) -> list[dict]:
        """Get all MySQL databases from PlanetScale.
        
        Returns:
            List of database dicts with 'id', 'name', etc.
        """
        if not self.token_id or not self.token or not self.organization:
            raise ValueError(PLANETSCALE_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.BASE_URL}/organizations/{self.organization}/databases",
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Failed to list PlanetScale databases: {response.status} - {text}")
                    
                    data = await response.json()
                    databases = data.get("data", [])
                    return databases
                    
        except aiohttp.ClientError as e:
            raise Exception(f"Network error listing PlanetScale databases: {str(e)}")

    async def delete_mysql_database(self, database_name: str) -> bool:
        """Delete a PlanetScale MySQL database.
        
        Args:
            database_name: The database name to delete.
            
        Returns:
            True if deletion was successful.
        """
        if not self.token_id or not self.token or not self.organization:
            raise ValueError(PLANETSCALE_KEY_ERROR_MSG)
            
        headers = self._get_headers()
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.delete(
                    f"{self.BASE_URL}/organizations/{self.organization}/databases/{database_name}",
                    headers=headers,
                ) as response:
                    if response.status in (200, 204):
                        logger.info(f"Deleted PlanetScale database: {database_name}")
                        return True
                    else:
                        text = await response.text()
                        raise Exception(
                            f"Failed to delete PlanetScale database: {response.status} - {text}"
                        )
        except aiohttp.ClientError as e:
            raise Exception(f"Network error deleting PlanetScale database: {str(e)}")

    async def free_up_database_resources(self) -> None:
        """Free up database resources by deleting oldest databases.
        
        PlanetScale has database limits per organization. This method deletes
        the oldest databases when approaching the limit.
        """
        if not self.token_id or not self.token or not self.organization:
            raise ValueError(PLANETSCALE_KEY_ERROR_MSG)
            
        databases = await self.get_all_mysql_databases()
        
        while len(databases) >= MAX_DATABASES_BEFORE_CLEANUP:
            logger.warning(f"PlanetScale quota approaching: {len(databases)} databases. Cleaning up oldest...")
            # Delete oldest (first in list)
            oldest = databases[0]
            await self.delete_mysql_database(oldest["name"])
            databases = await self.get_all_mysql_databases()
            await asyncio.sleep(1)  # Rate limit protection

    async def _create_database_password(self, database_name: str, branch: str = "main") -> dict:
        """Create a password for the database branch.
        
        PlanetScale requires creating a password to get connection credentials.
        
        Args:
            database_name: The database name.
            branch: The branch name (default: main).
            
        Returns:
            Dict with username, plain_text (password), hostname.
        """
        headers = self._get_headers()
        
        payload = {
            "role": "admin",  # Full access
            "name": f"sandbox-{uuid.uuid4().hex[:8]}",
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.BASE_URL}/organizations/{self.organization}/databases/{database_name}/branches/{branch}/passwords",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status in (200, 201):
                        data = await response.json()
                        return data
                    else:
                        text = await response.text()
                        raise Exception(
                            f"Failed to create PlanetScale password: {response.status} - {text}"
                        )
        except aiohttp.ClientError as e:
            raise Exception(f"Network error creating PlanetScale password: {str(e)}")

    async def create_mysql_database(self) -> str:
        """Create a new MySQL database on PlanetScale.
        
        This is a two-step process:
        1. Create the database
        2. Create a password to get connection credentials
        
        Returns:
            MySQL connection string in format: mysql://{user}:{pass}@{host}/{db}?sslaccept=strict
        """
        if not self.token_id or not self.token or not self.organization:
            raise ValueError(PLANETSCALE_KEY_ERROR_MSG)

        headers = self._get_headers()
        
        # Generate unique database name (PlanetScale has naming restrictions)
        db_name = f"sandbox-{uuid.uuid4().hex[:8]}"
        
        payload = {
            "name": db_name,
            "region": self.region,
        }

        for attempt in range(MAX_RETRIES):
            try:
                timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # Step 1: Create database
                    async with session.post(
                        f"{self.BASE_URL}/organizations/{self.organization}/databases",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status in (200, 201):
                            db_data = await response.json()
                            logger.info(f"Created PlanetScale database: {db_name}")
                        elif response.status == 402:
                            logger.warning("PlanetScale quota exceeded, cleaning up...")
                            await self.free_up_database_resources()
                            continue
                        else:
                            text = await response.text()
                            
                            # Check for quota exceeded
                            if "limit" in text.lower() or "quota" in text.lower():
                                logger.warning("PlanetScale quota exceeded, cleaning up...")
                                await self.free_up_database_resources()
                                continue
                                
                            raise Exception(
                                f"Failed to create PlanetScale database: {response.status} - {text}"
                            )
                
                # Wait for database to be ready
                await asyncio.sleep(3)
                
                # Step 2: Create password to get connection credentials
                password_data = await self._create_database_password(db_name)
                
                username = password_data.get("username")
                password = password_data.get("plain_text")
                hostname = password_data.get("hostname")
                
                if not username or not password or not hostname:
                    raise Exception(
                        f"Incomplete PlanetScale password response. "
                        f"Got: {list(password_data.keys())}"
                    )
                
                # Build connection string
                # Format: mysql://{user}:{pass}@{host}/{database}?sslaccept=strict
                connection_string = (
                    f"mysql://{username}:{password}@{hostname}/{db_name}"
                    "?sslaccept=strict"
                )
                
                logger.info(f"Created PlanetScale MySQL database: {db_name}")
                return connection_string
                
            except aiohttp.ClientError as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"PlanetScale API error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise Exception(f"Network error creating PlanetScale database: {str(e)}")
        
        raise Exception("Failed to create PlanetScale MySQL database after all retries")

    async def get_database_connection(self) -> str:
        """Get a MySQL connection string.
        
        Manages quotas and creates a new database.
        
        Returns:
            MySQL connection URI.
        """
        await self.free_up_database_resources()
        return await self.create_mysql_database()


# =============================================================================
# Legacy Clients (for backward compatibility)
# =============================================================================

class RedisDatabaseClient(UpstashRedisDatabaseClient):
    """Alias for UpstashRedisDatabaseClient for backward compatibility."""
    pass


class MySQLDatabaseClient(PlanetScaleMySQLDatabaseClient):
    """Alias for PlanetScaleMySQLDatabaseClient for backward compatibility."""
    pass


# =============================================================================
# Factory Function
# =============================================================================

def create_database_client(
    database_type: str, 
    setting: DatabaseConfig,
) -> DatabaseClient:
    """Create a database client for the specified database type.
    
    Args:
        database_type: One of "postgres" (default), "redis", or "mysql".
        setting: DatabaseConfig with API credentials.
        
    Returns:
        DatabaseClient instance for the specified type.
        
    Raises:
        ValueError: If database_type is not supported.
    """
    database_type = database_type.lower().strip()
    
    if database_type in ("postgres", "postgresql", "pg", "neon"):
        return PostgresDatabaseClient(setting)
    elif database_type in ("redis", "upstash"):
        return UpstashRedisDatabaseClient(setting)
    elif database_type in ("mysql", "planetscale"):
        return PlanetScaleMySQLDatabaseClient(setting)
    else:
        supported = ["postgres", "redis", "mysql"]
        raise ValueError(
            f"Unsupported database type: '{database_type}'. "
            f"Supported types: {supported}"
        )


# =============================================================================
# Main (for testing)
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        """Test all database clients."""
        config = DatabaseConfig()
        
        print("=" * 60)
        print("Testing Database Clients")
        print("=" * 60)
        
        # Test Postgres (Neon)
        print("\n[1] Testing PostgreSQL (Neon)...")
        try:
            client = create_database_client("postgres", config)
            connection = await client.get_database_connection()
            print(f"    ✅ PostgreSQL: {connection[:50]}...")
        except Exception as e:
            print(f"    ❌ PostgreSQL failed: {e}")
        
        # Test Redis (Upstash)
        print("\n[2] Testing Redis (Upstash)...")
        try:
            client = create_database_client("redis", config)
            connection = await client.get_database_connection()
            print(f"    ✅ Redis: {connection[:50]}...")
        except Exception as e:
            print(f"    ❌ Redis failed: {e}")
        
        # Test MySQL (PlanetScale)
        print("\n[3] Testing MySQL (PlanetScale)...")
        try:
            client = create_database_client("mysql", config)
            connection = await client.get_database_connection()
            print(f"    ✅ MySQL: {connection[:50]}...")
        except Exception as e:
            print(f"    ❌ MySQL failed: {e}")
        
        print("\n" + "=" * 60)
        print("Testing Complete")
        print("=" * 60)

    asyncio.run(main())
