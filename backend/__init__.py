"""Backend package initialization.

This module provides lazy loading for database models to avoid heavy imports
when only using subpackages like tool_server.

Models are loaded on-demand when `load_all_models()` is called, which happens
automatically when the FastAPI app is created via `register_app()`.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

__version__ = '1.11.2'

# Lazy model loading - only load models when explicitly requested
_models_loaded = False


def load_all_models():
    """Load all database models for SQLAlchemy table creation.
    
    This should be called when starting the FastAPI app, not on every import.
    It's idempotent - calling multiple times has no effect after the first call.
    """
    global _models_loaded
    if _models_loaded:
        return
    
    import sqlalchemy as sa
    from backend.utils.import_parse import get_all_models
    
    # Import all models for auto create db tables
    for cls in get_all_models():
        if isinstance(cls, sa.Table):
            table_name = cls.name
            if table_name not in globals():
                globals()[table_name] = cls
        else:
            class_name = cls.__name__
            if class_name not in globals():
                globals()[class_name] = cls
    
    _models_loaded = True


# For backwards compatibility, provide a way to check if models are loaded
def are_models_loaded() -> bool:
    """Check if database models have been loaded."""
    return _models_loaded
