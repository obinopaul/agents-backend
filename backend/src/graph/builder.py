# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
LangGraph State Graph Builder.

This module builds the core agent workflow graph. The graph is compiled
without a checkpointer - the PostgreSQL checkpointer is injected at runtime
by the checkpointer_manager.

Usage:
    from backend.src.graph.builder import graph
    from backend.src.graph.checkpointer import checkpointer_manager
    
    async with checkpointer_manager.get_graph_with_checkpointer(graph, thread_id) as g:
        async for event in g.astream_events(input, config):
            yield event
"""

from langgraph.graph import END, START, StateGraph

from .nodes import (
    background_investigation_node,
    base_node,
    human_feedback_node,
)
from .types import State


def _build_base_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_node("background_investigator", background_investigation_node)
    builder.add_node("base", base_node)
    builder.add_node("human_feedback", human_feedback_node)
    
    builder.add_edge(START, "background_investigator")
    builder.add_edge("background_investigator", "base")
    # base node uses Command(goto="human_feedback")
    # human_feedback node uses Command(goto="base" or "__end__")
    
    return builder


def build_graph():
    """
    Build and return the agent workflow graph.
    
    The graph is compiled WITHOUT a checkpointer. The PostgreSQL checkpointer
    is injected at runtime by checkpointer_manager.get_graph_with_checkpointer().
    
    This design ensures:
    - Single shared connection pool across all requests
    - Proper lifecycle management (init at startup, close at shutdown)
    - No in-memory state loss on restart
    
    Returns:
        CompiledStateGraph: The compiled graph ready for checkpointer injection
    """
    builder = _build_base_graph()
    return builder.compile()


# Pre-compiled graph instance
# The PostgreSQL checkpointer is injected at runtime by checkpointer_manager
graph = build_graph()
