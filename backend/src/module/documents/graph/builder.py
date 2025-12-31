# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Research Module LangGraph Builder.

This module builds the research workflow graph with multi-agent coordination.
The graph is compiled without a checkpointer - PostgreSQL checkpointer is
injected at runtime by checkpointer_manager.
"""

from langgraph.graph import END, START, StateGraph

from backend.src.prompts.planner_model import StepType

from .nodes import (
    analyst_node,
    background_investigation_node,
    coder_node,
    coordinator_node,
    human_feedback_node,
    planner_node,
    reporter_node,
    research_team_node,
    researcher_node,
)
from .types import State


def continue_to_running_research_team(state: State):
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return "planner"

    if all(step.execution_res for step in current_plan.steps):
        return "planner"

    # Find first incomplete step
    incomplete_step = None
    for step in current_plan.steps:
        if not step.execution_res:
            incomplete_step = step
            break

    if not incomplete_step:
        return "planner"

    if incomplete_step.step_type == StepType.RESEARCH:
        return "researcher"
    if incomplete_step.step_type == StepType.ANALYSIS:
        return "analyst"
    if incomplete_step.step_type == StepType.PROCESSING:
        return "coder"
    return "planner"


def _build_base_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("background_investigator", background_investigation_node)
    builder.add_node("planner", planner_node)
    builder.add_node("reporter", reporter_node)
    builder.add_node("research_team", research_team_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("coder", coder_node)
    builder.add_node("human_feedback", human_feedback_node)
    builder.add_edge("background_investigator", "planner")
    builder.add_conditional_edges(
        "research_team",
        continue_to_running_research_team,
        ["planner", "researcher", "analyst", "coder"],
    )
    builder.add_edge("reporter", END)
    return builder


def build_graph():
    """
    Build and return the research workflow graph.
    
    The graph is compiled WITHOUT a checkpointer. PostgreSQL checkpointer
    is injected at runtime by checkpointer_manager.
    """
    builder = _build_base_graph()
    return builder.compile()


# Pre-compiled graph instance
graph = build_graph()
