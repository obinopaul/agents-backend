"""PPT Generation Module.

STUBBED for sandbox server testing.
This module provides AI-powered PowerPoint presentation generation
from text content using Marp CLI.
"""

# =============================================================================
# STUB: Minimal exports for sandbox server testing
# =============================================================================


class DummyGraph:
    """Dummy graph that raises NotImplementedError when invoked."""
    
    def invoke(self, *args, **kwargs):
        raise NotImplementedError("PPT generation is not yet integrated")
    
    async def ainvoke(self, *args, **kwargs):
        raise NotImplementedError("PPT generation is not yet integrated")


def build_graph():
    """STUBBED: Returns a dummy graph for sandbox server testing."""
    return DummyGraph()


graph = build_graph()


class PPTState:
    """STUBBED: Placeholder for PPTState."""
    pass


def run_ppt_workflow(*args, **kwargs):
    raise NotImplementedError("PPT workflow is not yet integrated")


def run_ppt_workflow_async(*args, **kwargs):
    raise NotImplementedError("PPT workflow is not yet integrated")


def run_ppt_workflow_sync(*args, **kwargs):
    raise NotImplementedError("PPT workflow is not yet integrated")


__all__ = [
    "build_graph",
    "graph",
    "PPTState",
    "run_ppt_workflow",
    "run_ppt_workflow_async",
    "run_ppt_workflow_sync",
]


# =============================================================================
# ORIGINAL IMPLEMENTATION (commented out for sandbox testing)
# =============================================================================
# from backend.src.module.ppt.graph.builder import build_graph, graph
# from backend.src.module.ppt.graph.state import PPTState
# from backend.src.module.ppt.workflow import (
#     run_ppt_workflow,
#     run_ppt_workflow_async,
#     run_ppt_workflow_sync,
# )
