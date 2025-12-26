"""Podcast graph builder - STUBBED for sandbox server testing.

The original implementation is commented out below.
This stub allows the FastAPI server to start for sandbox testing.
"""

# =============================================================================
# STUB: Dummy build_graph function for sandbox server testing
# =============================================================================

class DummyGraph:
    """Dummy graph that raises NotImplementedError when invoked."""
    
    def invoke(self, *args, **kwargs):
        raise NotImplementedError("Podcast generation is not yet integrated")
    
    async def ainvoke(self, *args, **kwargs):
        raise NotImplementedError("Podcast generation is not yet integrated")


def build_graph():
    """Build and return the podcast workflow graph.
    
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
# from backend.src.module.podcast.graph.audio_mixer_node import audio_mixer_node
# from backend.src.module.podcast.graph.script_writer_node import script_writer_node
# from backend.src.module.podcast.graph.state import PodcastState
# from backend.src.module.podcast.graph.tts_node import tts_node
#
#
# def build_graph():
#     """Build and return the podcast workflow graph."""
#     builder = StateGraph(PodcastState)
#     builder.add_node("script_writer", script_writer_node)
#     builder.add_node("tts", tts_node)
#     builder.add_node("audio_mixer", audio_mixer_node)
#     builder.add_edge(START, "script_writer")
#     builder.add_edge("script_writer", "tts")
#     builder.add_edge("tts", "audio_mixer")
#     builder.add_edge("audio_mixer", END)
#     return builder.compile()
#
#
# # Pre-compiled workflow graph
# graph = build_graph()
