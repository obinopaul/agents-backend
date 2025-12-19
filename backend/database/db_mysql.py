"""
Backwards Compatibility Module for MySQL Database Access

This module provides a compatibility layer for code that expects MySQL-specific
database session management. It re-exports from the main db.py module which
supports both MySQL and PostgreSQL based on DATABASE_TYPE configuration.

Note: The actual database driver (asyncmy for MySQL, asyncpg for PostgreSQL)
is determined by the DATABASE_TYPE setting in core.conf.
"""

from backend.database.db import (
    async_db_session,
    async_engine,
    CurrentSession,
    CurrentSessionTransaction,
    get_db,
    get_db_transaction,
    create_tables,
    drop_tables,
    uuid4_str,
)

__all__ = [
    'async_db_session',
    'async_engine',
    'CurrentSession',
    'CurrentSessionTransaction',
    'get_db',
    'get_db_transaction',
    'create_tables',
    'drop_tables',
    'uuid4_str',
]
