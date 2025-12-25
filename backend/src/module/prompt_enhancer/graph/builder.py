from langgraph.graph import StateGraph

from backend.src.module.prompt_enhancer.graph.enhancer_node import prompt_enhancer_node
from backend.src.module.prompt_enhancer.graph.state import PromptEnhancerState


def build_graph():
    """Build and return the prompt enhancer workflow graph."""
    builder = StateGraph(PromptEnhancerState)
    builder.add_node("enhancer", prompt_enhancer_node)
    builder.set_entry_point("enhancer")
    builder.set_finish_point("enhancer")
    return builder.compile()


# Pre-compiled workflow graph
graph = build_graph()
