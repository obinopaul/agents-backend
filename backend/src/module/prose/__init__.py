"""Prose Writing Module.

This module provides AI-powered prose writing operations including
continue, improve, shorten, lengthen, fix, and zap.
"""
from backend.src.module.prose.graph.builder import build_graph, graph
from backend.src.module.prose.graph.state import ProseState
from backend.src.module.prose.workflow import (
    run_prose_workflow,
    run_prose_workflow_async,
    run_prose_workflow_sync,
)

__all__ = [
    "build_graph",
    "graph",
    "ProseState",
    "run_prose_workflow",
    "run_prose_workflow_async",
    "run_prose_workflow_sync",
]
