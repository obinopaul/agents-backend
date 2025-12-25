from langgraph.graph import END, START, StateGraph

from backend.src.module.podcast.graph.audio_mixer_node import audio_mixer_node
from backend.src.module.podcast.graph.script_writer_node import script_writer_node
from backend.src.module.podcast.graph.state import PodcastState
from backend.src.module.podcast.graph.tts_node import tts_node


def build_graph():
    """Build and return the podcast workflow graph."""
    builder = StateGraph(PodcastState)
    builder.add_node("script_writer", script_writer_node)
    builder.add_node("tts", tts_node)
    builder.add_node("audio_mixer", audio_mixer_node)
    builder.add_edge(START, "script_writer")
    builder.add_edge("script_writer", "tts")
    builder.add_edge("tts", "audio_mixer")
    builder.add_edge("audio_mixer", END)
    return builder.compile()


# Pre-compiled workflow graph
graph = build_graph()
