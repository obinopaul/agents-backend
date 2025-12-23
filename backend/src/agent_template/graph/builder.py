# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Graph Builder for the multi-agent template.

Constructs the LangGraph StateGraph with all nodes and edges.
"""

import logging
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.nodes import (
    coordinator_node,
    planner_node,
    executor_node,
    reviewer_node,
    reporter_node,
)
from backend.src.agent_template.graph.edges import route_after_executor

logger = logging.getLogger(__name__)


def _build_base_graph() -> StateGraph:
    """
    Build the base state graph with all nodes and edges.
    
    Graph Structure:
    
    START → coordinator
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
    planner              (direct → END)
    ↓
    executor ←──────┐
    ↓               │
    reviewer ───────┤ (if REPLAN)
    ↓
    reporter
    ↓
    END
    
    Returns:
        StateGraph: The constructed graph (not compiled)
    """
    builder = StateGraph(TemplateState)
    
    # Add all nodes
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("executor", executor_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("reporter", reporter_node)
    
    # Entry point
    builder.add_edge(START, "coordinator")
    
    # Coordinator routes
    # Note: coordinator_node returns Command with goto, so edges are handled by Command
    
    # Planner routes to executor (or human_approval if enabled)
    # Note: planner_node returns Command with goto
    
    # Executor can loop back or go to reviewer
    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        ["executor", "reviewer"],
    )
    
    # Reviewer routes to planner (replan) or reporter
    # Note: reviewer_node returns Command with goto
    
    # Reporter always ends
    builder.add_edge("reporter", END)
    
    return builder


def build_graph():
    """
    Build and compile the agent workflow graph without persistence.
    
    Returns:
        CompiledGraph: The compiled graph ready for execution
    """
    builder = _build_base_graph()
    return builder.compile()


def build_graph_with_memory(checkpointer: Optional[BaseCheckpointSaver] = None):
    """
    Build and compile the agent workflow graph with memory/persistence.
    
    Args:
        checkpointer: Optional custom checkpointer. If None, uses MemorySaver.
        
    Returns:
        CompiledGraph: The compiled graph with checkpointing enabled
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    builder = _build_base_graph()
    return builder.compile(checkpointer=checkpointer)


# Pre-built graph instance for convenience
graph = build_graph()
