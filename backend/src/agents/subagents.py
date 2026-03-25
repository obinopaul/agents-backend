"""Subagent exports and utilities.

This module provides common exports for subagent functionality.
Module-specific subagents should be defined in each module's own subagents.py file
using the get_subagents() function pattern.

Example usage in a module:
    
    # In backend/src/module/my_module/subagents.py
    from deepagents.middleware.subagents import SubAgent
    
    def get_subagents(model=None, middleware=None):
        return [
            SubAgent(
                name="my_subagent",
                description="Does something specific",
                system_prompt="You are a specialized agent.",
                model=model,
                middleware=middleware or [],
            ),
        ]
"""

# Re-export common types for convenience
try:
    from deepagents.middleware.subagents import SubAgent, CompiledSubAgent
    SUBAGENT_AVAILABLE = True
except ImportError:
    SubAgent = None
    CompiledSubAgent = None
    SUBAGENT_AVAILABLE = False

__all__ = [
    "SubAgent",
    "CompiledSubAgent",
    "SUBAGENT_AVAILABLE",
]
