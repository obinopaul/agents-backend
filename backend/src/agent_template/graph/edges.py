# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Edge routing logic for the multi-agent template.

Provides conditional edge functions for graph routing.
"""

import logging
from typing import Literal

from backend.src.agent_template.state import TemplateState

logger = logging.getLogger(__name__)


def route_after_executor(state: TemplateState) -> Literal["executor", "reviewer"]:
    """
    Route after executor node.
    
    Decides whether to:
    - Continue executing (more steps remaining)
    - Go to reviewer (all steps complete or error)
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name
    """
    plan = state.get("plan", {})
    current_step = state.get("current_step", 0)
    is_complete = state.get("is_complete", False)
    
    if is_complete:
        return "reviewer"
    
    steps = plan.get("steps", []) if plan else []
    
    if current_step < len(steps):
        return "executor"
    
    return "reviewer"


def route_after_coordinator(state: TemplateState) -> Literal["planner", "reporter", "__end__"]:
    """
    Route after coordinator node.
    
    Note: This is typically handled by Command in coordinator_node,
    but provided here for alternative graph configurations.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name
    """
    goto = state.get("goto", "planner")
    is_complete = state.get("is_complete", False)
    
    if is_complete:
        return "__end__"
    
    if goto == "reporter":
        return "reporter"
    
    return "planner"


def route_after_reviewer(state: TemplateState) -> Literal["planner", "reporter"]:
    """
    Route after reviewer node.
    
    Note: This is typically handled by Command in reviewer_node,
    but provided here for alternative graph configurations.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name
    """
    goto = state.get("goto", "reporter")
    
    if goto == "planner":
        return "planner"
    
    return "reporter"
