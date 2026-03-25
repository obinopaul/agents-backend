"""
Compatibility Module for Security Imports

Re-exports from backend.common.security for backwards compatibility
with code that expects the security module in backend.core.
"""

from backend.common.security.jwt import *
from backend.common.security.jwt import DependsJwtAuth

__all__ = ['DependsJwtAuth']
