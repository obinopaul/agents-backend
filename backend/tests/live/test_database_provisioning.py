#!/usr/bin/env python3
"""
Comprehensive tests for database provisioning clients.

This test file validates the database provisioning integrations:
- PostgreSQL via Neon Cloud
- Redis via Upstash
- MySQL via PlanetScale

Prerequisites:
    Set the following environment variables in backend/.env:
    
    # PostgreSQL (Neon)
    DATABASE_NEON_DB_API_KEY=your_neon_api_key
    
    # Redis (Upstash)
    DATABASE_UPSTASH_EMAIL=your-email@example.com
    DATABASE_UPSTASH_API_KEY=your_upstash_api_key
    
    # MySQL (PlanetScale)
    DATABASE_PLANETSCALE_SERVICE_TOKEN_ID=your_token_id
    DATABASE_PLANETSCALE_SERVICE_TOKEN=your_service_token
    DATABASE_PLANETSCALE_ORGANIZATION=your_org_name

Usage:
    # Run all tests
    python backend/tests/live/test_database_provisioning.py
    
    # Run with verbose output
    python backend/tests/live/test_database_provisioning.py -v
    
    # Run specific database type only
    python backend/tests/live/test_database_provisioning.py --type postgres
    python backend/tests/live/test_database_provisioning.py --type redis
    python backend/tests/live/test_database_provisioning.py --type mysql

Note:
    These tests create REAL databases on the cloud providers.
    They are cleaned up automatically, but may incur costs.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.getcwd())

from backend.src.tool_server.integrations.database import (
    create_database_client,
    DatabaseConfig,
    PostgresDatabaseClient,
    UpstashRedisDatabaseClient,
    PlanetScaleMySQLDatabaseClient,
)


# =============================================================================
# Test Configuration
# =============================================================================

class TestConfig:
    """Test configuration and helper methods."""
    
    def __init__(self):
        self.config = DatabaseConfig()
        self.created_databases = {
            "postgres": [],
            "redis": [],
            "mysql": [],
        }
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }
    
    def has_postgres_credentials(self) -> bool:
        """Check if Neon credentials are configured."""
        return bool(self.config.neon_db_api_key)
    
    def has_redis_credentials(self) -> bool:
        """Check if Upstash credentials are configured."""
        return bool(self.config.upstash_email and self.config.upstash_api_key)
    
    def has_mysql_credentials(self) -> bool:
        """Check if PlanetScale credentials are configured."""
        return bool(
            self.config.planetscale_service_token_id and 
            self.config.planetscale_service_token and 
            self.config.planetscale_organization
        )


# =============================================================================
# Test Helpers
# =============================================================================

def print_header(title: str):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_subheader(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def print_result(test_name: str, passed: bool, message: str = ""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test_name}")
    if message:
        print(f"         {message}")


def print_skip(test_name: str, reason: str):
    """Print skipped test."""
    print(f"  ⏭️ SKIP: {test_name}")
    print(f"         {reason}")


def validate_connection_string(db_type: str, connection_string: str) -> tuple[bool, str]:
    """Validate connection string format.
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not connection_string:
        return False, "Connection string is empty"
    
    if db_type == "postgres":
        if not connection_string.startswith("postgresql://"):
            return False, f"Expected postgresql:// prefix, got: {connection_string[:30]}..."
        if "@" not in connection_string:
            return False, "Missing @ separator in connection string"
        return True, f"Valid PostgreSQL URI: {connection_string[:50]}..."
    
    elif db_type == "redis":
        if not connection_string.startswith("rediss://"):
            return False, f"Expected rediss:// prefix, got: {connection_string[:30]}..."
        if "@" not in connection_string:
            return False, "Missing @ separator in connection string"
        return True, f"Valid Redis URI: {connection_string[:50]}..."
    
    elif db_type == "mysql":
        if not connection_string.startswith("mysql://"):
            return False, f"Expected mysql:// prefix, got: {connection_string[:30]}..."
        if "@" not in connection_string:
            return False, "Missing @ separator in connection string"
        return True, f"Valid MySQL URI: {connection_string[:50]}..."
    
    return False, f"Unknown database type: {db_type}"


# =============================================================================
# PostgreSQL (Neon) Tests
# =============================================================================

async def test_postgres_credentials(ctx: TestConfig) -> bool:
    """Test PostgreSQL credential configuration."""
    if not ctx.has_postgres_credentials():
        print_skip("PostgreSQL credentials", "DATABASE_NEON_DB_API_KEY not set")
        ctx.test_results["skipped"] += 1
        return False
    
    print_result("PostgreSQL credentials", True, "Neon API key configured")
    ctx.test_results["passed"] += 1
    return True


async def test_postgres_list_databases(ctx: TestConfig) -> bool:
    """Test listing PostgreSQL databases."""
    if not ctx.has_postgres_credentials():
        print_skip("PostgreSQL list databases", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = PostgresDatabaseClient(ctx.config)
        databases = await client.get_all_postgres_databases()
        
        print_result(
            "PostgreSQL list databases", 
            True, 
            f"Found {len(databases)} existing databases"
        )
        ctx.test_results["passed"] += 1
        return True
        
    except Exception as e:
        print_result("PostgreSQL list databases", False, str(e))
        ctx.test_results["failed"] += 1
        return False


async def test_postgres_create_database(ctx: TestConfig) -> bool:
    """Test creating a PostgreSQL database."""
    if not ctx.has_postgres_credentials():
        print_skip("PostgreSQL create database", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = create_database_client("postgres", ctx.config)
        connection_string = await client.get_database_connection()
        
        is_valid, message = validate_connection_string("postgres", connection_string)
        
        if is_valid:
            print_result("PostgreSQL create database", True, message)
            ctx.test_results["passed"] += 1
            
            # Store for cleanup (extract project ID from connection string if needed)
            # For now, we'll rely on the quota management to clean up
            return True
        else:
            print_result("PostgreSQL create database", False, message)
            ctx.test_results["failed"] += 1
            return False
        
    except Exception as e:
        print_result("PostgreSQL create database", False, str(e))
        ctx.test_results["failed"] += 1
        return False


# =============================================================================
# Redis (Upstash) Tests
# =============================================================================

async def test_redis_credentials(ctx: TestConfig) -> bool:
    """Test Redis credential configuration."""
    if not ctx.has_redis_credentials():
        print_skip("Redis credentials", "DATABASE_UPSTASH_EMAIL and/or DATABASE_UPSTASH_API_KEY not set")
        ctx.test_results["skipped"] += 1
        return False
    
    print_result("Redis credentials", True, "Upstash credentials configured")
    ctx.test_results["passed"] += 1
    return True


async def test_redis_list_databases(ctx: TestConfig) -> bool:
    """Test listing Redis databases."""
    if not ctx.has_redis_credentials():
        print_skip("Redis list databases", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = UpstashRedisDatabaseClient(ctx.config)
        databases = await client.get_all_redis_databases()
        
        print_result(
            "Redis list databases", 
            True, 
            f"Found {len(databases)} existing databases"
        )
        ctx.test_results["passed"] += 1
        return True
        
    except Exception as e:
        print_result("Redis list databases", False, str(e))
        ctx.test_results["failed"] += 1
        return False


async def test_redis_create_database(ctx: TestConfig) -> bool:
    """Test creating a Redis database."""
    if not ctx.has_redis_credentials():
        print_skip("Redis create database", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = create_database_client("redis", ctx.config)
        connection_string = await client.get_database_connection()
        
        is_valid, message = validate_connection_string("redis", connection_string)
        
        if is_valid:
            print_result("Redis create database", True, message)
            ctx.test_results["passed"] += 1
            return True
        else:
            print_result("Redis create database", False, message)
            ctx.test_results["failed"] += 1
            return False
        
    except Exception as e:
        print_result("Redis create database", False, str(e))
        ctx.test_results["failed"] += 1
        return False


# =============================================================================
# MySQL (PlanetScale) Tests
# =============================================================================

async def test_mysql_credentials(ctx: TestConfig) -> bool:
    """Test MySQL credential configuration."""
    if not ctx.has_mysql_credentials():
        print_skip(
            "MySQL credentials", 
            "DATABASE_PLANETSCALE_* environment variables not fully set"
        )
        ctx.test_results["skipped"] += 1
        return False
    
    print_result("MySQL credentials", True, "PlanetScale credentials configured")
    ctx.test_results["passed"] += 1
    return True


async def test_mysql_list_databases(ctx: TestConfig) -> bool:
    """Test listing MySQL databases."""
    if not ctx.has_mysql_credentials():
        print_skip("MySQL list databases", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = PlanetScaleMySQLDatabaseClient(ctx.config)
        databases = await client.get_all_mysql_databases()
        
        print_result(
            "MySQL list databases", 
            True, 
            f"Found {len(databases)} existing databases"
        )
        ctx.test_results["passed"] += 1
        return True
        
    except Exception as e:
        print_result("MySQL list databases", False, str(e))
        ctx.test_results["failed"] += 1
        return False


async def test_mysql_create_database(ctx: TestConfig) -> bool:
    """Test creating a MySQL database."""
    if not ctx.has_mysql_credentials():
        print_skip("MySQL create database", "No credentials")
        ctx.test_results["skipped"] += 1
        return False
    
    try:
        client = create_database_client("mysql", ctx.config)
        connection_string = await client.get_database_connection()
        
        is_valid, message = validate_connection_string("mysql", connection_string)
        
        if is_valid:
            print_result("MySQL create database", True, message)
            ctx.test_results["passed"] += 1
            return True
        else:
            print_result("MySQL create database", False, message)
            ctx.test_results["failed"] += 1
            return False
        
    except Exception as e:
        print_result("MySQL create database", False, str(e))
        ctx.test_results["failed"] += 1
        return False


# =============================================================================
# Factory Function Tests
# =============================================================================

async def test_factory_function(ctx: TestConfig) -> bool:
    """Test the create_database_client factory function."""
    print_subheader("Factory Function Tests")
    
    all_passed = True
    
    # Test valid types
    valid_types = [
        ("postgres", PostgresDatabaseClient),
        ("postgresql", PostgresDatabaseClient),
        ("pg", PostgresDatabaseClient),
        ("neon", PostgresDatabaseClient),
        ("redis", UpstashRedisDatabaseClient),
        ("upstash", UpstashRedisDatabaseClient),
        ("mysql", PlanetScaleMySQLDatabaseClient),
        ("planetscale", PlanetScaleMySQLDatabaseClient),
    ]
    
    for db_type, expected_class in valid_types:
        try:
            client = create_database_client(db_type, ctx.config)
            if isinstance(client, expected_class):
                print_result(f"create_database_client('{db_type}')", True)
                ctx.test_results["passed"] += 1
            else:
                print_result(
                    f"create_database_client('{db_type}')", 
                    False, 
                    f"Expected {expected_class.__name__}, got {type(client).__name__}"
                )
                ctx.test_results["failed"] += 1
                all_passed = False
        except Exception as e:
            print_result(f"create_database_client('{db_type}')", False, str(e))
            ctx.test_results["failed"] += 1
            all_passed = False
    
    # Test invalid type
    try:
        create_database_client("invalid_db", ctx.config)
        print_result("create_database_client('invalid_db')", False, "Should have raised ValueError")
        ctx.test_results["failed"] += 1
        all_passed = False
    except ValueError as e:
        print_result("create_database_client('invalid_db') raises ValueError", True)
        ctx.test_results["passed"] += 1
    except Exception as e:
        print_result("create_database_client('invalid_db')", False, f"Wrong exception: {e}")
        ctx.test_results["failed"] += 1
        all_passed = False
    
    return all_passed


# =============================================================================
# Error Handling Tests
# =============================================================================

async def test_error_handling(ctx: TestConfig):
    """Test error handling for missing credentials."""
    print_subheader("Error Handling Tests")
    
    # Create empty config to test credential validation
    empty_config = DatabaseConfig(
        neon_db_api_key=None,
        upstash_email=None,
        upstash_api_key=None,
        planetscale_service_token_id=None,
        planetscale_service_token=None,
        planetscale_organization=None,
    )
    
    # Test Postgres with no credentials
    try:
        client = PostgresDatabaseClient(empty_config)
        await client.get_database_connection()
        print_result("Postgres missing credentials", False, "Should have raised ValueError")
        ctx.test_results["failed"] += 1
    except ValueError as e:
        if "Neon" in str(e):
            print_result("Postgres missing credentials raises ValueError", True)
            ctx.test_results["passed"] += 1
        else:
            print_result("Postgres missing credentials", False, f"Wrong error message: {e}")
            ctx.test_results["failed"] += 1
    except Exception as e:
        print_result("Postgres missing credentials", False, f"Wrong exception type: {type(e).__name__}")
        ctx.test_results["failed"] += 1
    
    # Test Redis with no credentials
    try:
        client = UpstashRedisDatabaseClient(empty_config)
        await client.get_database_connection()
        print_result("Redis missing credentials", False, "Should have raised ValueError")
        ctx.test_results["failed"] += 1
    except ValueError as e:
        if "Upstash" in str(e):
            print_result("Redis missing credentials raises ValueError", True)
            ctx.test_results["passed"] += 1
        else:
            print_result("Redis missing credentials", False, f"Wrong error message: {e}")
            ctx.test_results["failed"] += 1
    except Exception as e:
        print_result("Redis missing credentials", False, f"Wrong exception type: {type(e).__name__}")
        ctx.test_results["failed"] += 1
    
    # Test MySQL with no credentials
    try:
        client = PlanetScaleMySQLDatabaseClient(empty_config)
        await client.get_database_connection()
        print_result("MySQL missing credentials", False, "Should have raised ValueError")
        ctx.test_results["failed"] += 1
    except ValueError as e:
        if "PlanetScale" in str(e):
            print_result("MySQL missing credentials raises ValueError", True)
            ctx.test_results["passed"] += 1
        else:
            print_result("MySQL missing credentials", False, f"Wrong error message: {e}")
            ctx.test_results["failed"] += 1
    except Exception as e:
        print_result("MySQL missing credentials", False, f"Wrong exception type: {type(e).__name__}")
        ctx.test_results["failed"] += 1


# =============================================================================
# Main Test Runner
# =============================================================================

async def run_tests(db_type: str = None, skip_create: bool = False):
    """Run all tests or tests for a specific database type."""
    ctx = TestConfig()
    
    print_header("Database Provisioning Tests")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Filter: {db_type or 'all'}")
    print(f"  Skip create: {skip_create}")
    
    # Show credential status
    print_subheader("Credential Status")
    print(f"  PostgreSQL (Neon):     {'✅ Configured' if ctx.has_postgres_credentials() else '❌ Not configured'}")
    print(f"  Redis (Upstash):       {'✅ Configured' if ctx.has_redis_credentials() else '❌ Not configured'}")
    print(f"  MySQL (PlanetScale):   {'✅ Configured' if ctx.has_mysql_credentials() else '❌ Not configured'}")
    
    # Factory function tests (always run)
    await test_factory_function(ctx)
    
    # Error handling tests (always run)
    await test_error_handling(ctx)
    
    # PostgreSQL tests
    if db_type is None or db_type == "postgres":
        print_subheader("PostgreSQL (Neon) Tests")
        await test_postgres_credentials(ctx)
        await test_postgres_list_databases(ctx)
        if not skip_create:
            await test_postgres_create_database(ctx)
    
    # Redis tests
    if db_type is None or db_type == "redis":
        print_subheader("Redis (Upstash) Tests")
        await test_redis_credentials(ctx)
        await test_redis_list_databases(ctx)
        if not skip_create:
            await test_redis_create_database(ctx)
    
    # MySQL tests
    if db_type is None or db_type == "mysql":
        print_subheader("MySQL (PlanetScale) Tests")
        await test_mysql_credentials(ctx)
        await test_mysql_list_databases(ctx)
        if not skip_create:
            await test_mysql_create_database(ctx)
    
    # Print summary
    print_header("Test Summary")
    total = ctx.test_results["passed"] + ctx.test_results["failed"] + ctx.test_results["skipped"]
    print(f"  Total:   {total}")
    print(f"  Passed:  {ctx.test_results['passed']}")
    print(f"  Failed:  {ctx.test_results['failed']}")
    print(f"  Skipped: {ctx.test_results['skipped']}")
    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Return exit code
    return 0 if ctx.test_results["failed"] == 0 else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test database provisioning clients",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--type", "-t",
        choices=["postgres", "redis", "mysql"],
        help="Test only a specific database type",
    )
    parser.add_argument(
        "--skip-create", "-s",
        action="store_true",
        help="Skip database creation tests (only test list/credentials)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(run_tests(
        db_type=args.type,
        skip_create=args.skip_create,
    ))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
