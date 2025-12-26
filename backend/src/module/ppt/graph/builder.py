"""PPT graph builder - STUBBED for sandbox server testing.

The original implementation is commented out below.
This stub allows the FastAPI server to start for sandbox testing.
"""

# =============================================================================
# STUB: Dummy build_graph function for sandbox server testing
# =============================================================================

class DummyGraph:
    """Dummy graph that raises NotImplementedError when invoked."""
    
    def invoke(self, *args, **kwargs):
        raise NotImplementedError("PPT generation is not yet integrated")
    
    async def ainvoke(self, *args, **kwargs):
        raise NotImplementedError("PPT generation is not yet integrated")


def build_graph():
    """Build and return the PPT workflow graph.
    
    STUBBED: Returns a dummy graph for sandbox server testing.
    """
    return DummyGraph()


# Pre-compiled workflow graph
graph = build_graph()


# =============================================================================
# ORIGINAL IMPLEMENTATION (commented out for sandbox testing)
# =============================================================================
# from langgraph.graph import END, START, StateGraph
#
# from backend.src.module.ppt.graph.ppt_composer_node import ppt_composer_node
# from backend.src.module.ppt.graph.ppt_generator_node import ppt_generator_node
# from backend.src.module.ppt.graph.state import PPTState
#
#
# def build_graph():
#     """Build and return the PPT workflow graph."""
#     builder = StateGraph(PPTState)
#     builder.add_node("ppt_composer", ppt_composer_node)
#     builder.add_node("ppt_generator", ppt_generator_node)
#     builder.add_edge(START, "ppt_composer")
#     builder.add_edge("ppt_composer", "ppt_generator")
#     builder.add_edge("ppt_generator", END)
#     return builder.compile()
#
#
# # Pre-compiled workflow graph
# graph = build_graph()
