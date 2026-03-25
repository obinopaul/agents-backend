import logging
import os
from dataclasses import dataclass, field, fields
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from backend.src.rag.retriever import Resource

logger = logging.getLogger(__name__)


def get_recursion_limit(default: int = 1000) -> int:
    """Get the recursion limit from settings with fallback.

    Returns:
        int: The recursion limit to use
    """
    from backend.core.conf import settings
    
    limit = settings.AGENT_RECURSION_LIMIT
    if limit > 0:
        return limit
    return default


@dataclass(kw_only=True)
class Configuration:
    """The configurable fields."""

    resources: list[Resource] = field(
        default_factory=list
    )  # Resources to be used for the research
    max_plan_iterations: int = 1  # Maximum number of plan iterations
    max_step_num: int = 3  # Maximum number of steps in a plan
    max_search_results: int = 3  # Maximum number of search results
    mcp_settings: dict = None  # MCP settings, including dynamic loaded tools
    mcp_url: str = None  # Dynamic MCP URL from sandbox (injected at runtime)
    codex_url: str = None  # Codex SSE server URL for task delegation (port 1324)
    vscode_url: str = None  # VS Code server URL for frontend viewer (port 9000)
    thread_id: str = None  # Thread/session ID for conversation continuity
    sandbox_id: str = None  # Sandbox ID for environment isolation
    enable_web_search: bool = (
        True  # Whether to enable web search, set to False to use only local RAG
    )
    enable_added_tools: bool = (
        False  # Whether to enable external research tools (paper_search, arxiv, etc.)
        # Defaults to False — these academic tools pollute the tool namespace
        # and cause the agent to call irrelevant tools like GetPaperDetails
        # when the user wants coding/sandbox tasks. Enable explicitly when needed.
    )

    interrupt_before_tools: list[str] = field(
        default_factory=list
    )  # List of tool names to interrupt before execution
    
    # Workspace / file upload paths (sandbox)
    workspace_path: str = "/workspace"  # Root workspace path inside sandbox
    workspace_upload_subpath: str = "uploads"  # Subdirectory for user-uploaded files

    @property
    def workspace_upload_path(self) -> str:
        """Full path where user uploads are stored in the sandbox (e.g. /workspace/uploads)."""
        return os.path.join(self.workspace_path, self.workspace_upload_subpath)

    # Human-in-the-loop (HITL) configuration
    always_require_feedback: bool = (
        False  # If True, always route to human_feedback after base node (legacy mode)
    )
    enable_feedback_tool: bool = (
        False  # If True, add request_human_feedback tool to agent for explicit HITL
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }
        # Use 'is not None' instead of truthiness check to preserve
        # explicit False values (e.g. enable_added_tools=False,
        # enable_web_search=False).  The old `if v` filter silently
        # dropped False/0/"" which made it impossible to disable
        # boolean feature flags.
        return cls(**{k: v for k, v in values.items() if v is not None})
