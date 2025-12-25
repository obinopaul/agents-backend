import logging

from langgraph.graph import END, START, StateGraph

from backend.src.module.prose.graph.prose_continue_node import prose_continue_node
from backend.src.module.prose.graph.prose_fix_node import prose_fix_node
from backend.src.module.prose.graph.prose_improve_node import prose_improve_node
from backend.src.module.prose.graph.prose_longer_node import prose_longer_node
from backend.src.module.prose.graph.prose_shorter_node import prose_shorter_node
from backend.src.module.prose.graph.prose_zap_node import prose_zap_node
from backend.src.module.prose.graph.state import ProseState

logger = logging.getLogger(__name__)


def optional_node(state: ProseState):
    """Route to the appropriate prose node based on the option."""
    return state["option"]


def build_graph():
    """Build and return the prose workflow graph."""
    builder = StateGraph(ProseState)
    builder.add_node("prose_continue", prose_continue_node)
    builder.add_node("prose_improve", prose_improve_node)
    builder.add_node("prose_shorter", prose_shorter_node)
    builder.add_node("prose_longer", prose_longer_node)
    builder.add_node("prose_fix", prose_fix_node)
    builder.add_node("prose_zap", prose_zap_node)
    builder.add_conditional_edges(
        START,
        optional_node,
        {
            "continue": "prose_continue",
            "improve": "prose_improve",
            "shorter": "prose_shorter",
            "longer": "prose_longer",
            "fix": "prose_fix",
            "zap": "prose_zap",
        },
    )
    builder.add_edge("prose_continue", END)
    builder.add_edge("prose_improve", END)
    builder.add_edge("prose_shorter", END)
    builder.add_edge("prose_longer", END)
    builder.add_edge("prose_fix", END)
    builder.add_edge("prose_zap", END)
    return builder.compile()


# Pre-compiled workflow graph
graph = build_graph()
