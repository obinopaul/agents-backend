"""
DS* (Data Science Agent) Graph Builder.

This module constructs the LangGraph state graph for the DS* multi-agent architecture.
Uses Command-based routing from nodes for dynamic graph traversal.

Graph Flow:
    START → analyzer → coder → executor → verifier
                ↑                              ↓
                └──────────────────────────────┘
                        (if INSUFFICIENT)

Routing is handled by Command returns from nodes:
    - analyzer → human_feedback or coder
    - coder → executor
    - executor → verifier
    - verifier → analyzer (INSUFFICIENT) or __end__ (SUFFICIENT)
"""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.types import Checkpointer

# Import nodes from modular packages
from backend.src.module.dev.analyzer import analyzer_node, human_feedback_node

# Import state types
from backend.src.module.dev.types import State, VerificationStatus


logger = logging.getLogger(__name__)


# =============================================================================
# Graph Builder
# =============================================================================

def _build_base_graph():
    """
    Build the DS* state graph.
    
    Args:
        with_hitl: Whether to include Human-in-the-Loop nodes
        checkpointer: Optional checkpointer for state persistence
    
    Returns:
        Compiled StateGraph ready for invocation
        
    Graph Structure:
        START → analyzer →[HITL]→ coder → executor → verifier
                    ↑                                    ↓
                    └────────────────────────────────────┘
                              (if INSUFFICIENT)
    """
    logger.info(f"Building graph")
    
    # Create graph builder
    builder = StateGraph(State)
    # =========================================================================
    # Add Nodes
    # =========================================================================
    
    # Analysis and Planning (includes planner subagent)
    builder.add_node("analyzer", analyzer_node)
    
    # HITL node (for human feedback)
    builder.add_node("human_feedback", human_feedback_node)
    
    # =========================================================================
    # Define Edges
    # =========================================================================
    
    # START → analyzer
    builder.add_edge(START, "analyzer")
    
    # NOTE: Most routing is handled by Command returns from nodes.
    # Each node returns Command(update={...}, goto="next_node")
    # which controls the routing dynamically.
    #
    # Routing Summary:
    # - analyzer → human_feedback (if HITL) or coder
    # - human_feedback → analyzer (edit) or coder (approve) or __end__ (reject)
    # - coder → executor (always)
    # - executor → verifier (always)
    # - verifier → __end__ (SUFFICIENT) or analyzer (INSUFFICIENT)
    
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
