"""Podcast Generation Module.

STUBBED for sandbox server testing.
This module provides AI-powered podcast generation from text content
using script writing and text-to-speech synthesis.
"""

# =============================================================================
# STUB: Minimal exports for sandbox server testing
# =============================================================================


class DummyGraph:
    """Dummy graph that raises NotImplementedError when invoked."""
    
    def invoke(self, *args, **kwargs):
        raise NotImplementedError("Podcast generation is not yet integrated")
    
    async def ainvoke(self, *args, **kwargs):
        raise NotImplementedError("Podcast generation is not yet integrated")


def build_graph():
    """STUBBED: Returns a dummy graph for sandbox server testing."""
    return DummyGraph()


graph = build_graph()


class PodcastState:
    """STUBBED: Placeholder for PodcastState."""
    pass


class Script:
    """STUBBED: Placeholder for Script."""
    pass


class ScriptLine:
    """STUBBED: Placeholder for ScriptLine."""
    pass


def run_podcast_workflow(*args, **kwargs):
    raise NotImplementedError("Podcast workflow is not yet integrated")


def run_podcast_workflow_async(*args, **kwargs):
    raise NotImplementedError("Podcast workflow is not yet integrated")


def run_podcast_workflow_sync(*args, **kwargs):
    raise NotImplementedError("Podcast workflow is not yet integrated")


__all__ = [
    "build_graph",
    "graph",
    "PodcastState",
    "Script",
    "ScriptLine",
    "run_podcast_workflow",
    "run_podcast_workflow_async",
    "run_podcast_workflow_sync",
]
