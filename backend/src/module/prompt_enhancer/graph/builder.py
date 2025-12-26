"""Prompt enhancer graph builder - STUBBED for sandbox server testing.

The original implementation is commented out below.
This stub allows the FastAPI server to start for sandbox testing.
"""

# =============================================================================
# STUB: Dummy build_graph function for sandbox server testing
# =============================================================================

class DummyGraph:
    """Dummy graph that raises NotImplementedError when invoked."""
    
    def invoke(self, *args, **kwargs):
        raise NotImplementedError("Prompt enhancement is not yet integrated")
    
    async def ainvoke(self, *args, **kwargs):
        raise NotImplementedError("Prompt enhancement is not yet integrated")


def build_graph():
    """Build and return the prompt enhancer workflow graph.
    
    STUBBED: Returns a dummy graph for sandbox server testing.
    """
    return DummyGraph()


# Pre-compiled workflow graph
graph = build_graph()


# =============================================================================
# ORIGINAL IMPLEMENTATION (commented out for sandbox testing)
# =============================================================================
# from langgraph.graph import StateGraph
#
# from backend.src.module.prompt_enhancer.graph.enhancer_node import prompt_enhancer_node
# from backend.src.module.prompt_enhancer.graph.state import PromptEnhancerState
#
#
# def build_graph():
#     """Build and return the prompt enhancer workflow graph."""
#     builder = StateGraph(PromptEnhancerState)
#     builder.add_node("enhancer", prompt_enhancer_node)
#     builder.set_entry_point("enhancer")
#     builder.set_finish_point("enhancer")
#     return builder.compile()
#
#
# # Pre-compiled workflow graph
# graph = build_graph()
