from langgraph.checkpoint.memory import MemorySaver
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


def build_graph_with_memory():
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    # TODO: be compatible with SQLite / PostgreSQL
    memory = MemorySaver()

    # build state graph
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)


def build_graph():
    """Build and return the agent workflow graph without memory."""
    # build state graph
    builder = _build_base_graph()
    return builder.compile()


graph = build_graph()
