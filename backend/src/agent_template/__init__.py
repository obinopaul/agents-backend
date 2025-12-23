# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Multi-Agent Template Package.

A configurable, reusable multi-agent framework built on LangGraph.
Can be used standalone or embedded as a node in other agent workflows.

Usage:
    from backend.src.agent_template import build_graph, TemplateState, AgentConfig
    
    # Standalone usage
    graph = build_graph()
    result = graph.invoke({"task": "Analyze this data..."})
    
    # With persistence
    graph = build_graph_with_memory()
    
    # Embedded as a node
    from backend.src.agent_template import template_agent_node
"""

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig
from backend.src.agent_template.graph.builder import (
    build_graph,
    build_graph_with_memory,
)

__all__ = [
    "TemplateState",
    "AgentConfig",
    "build_graph",
    "build_graph_with_memory",
]
