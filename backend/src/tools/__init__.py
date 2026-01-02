"""Tools Package.

This package contains shared tools used across the application:
- crawl: Web page crawling
- human_feedback: Human-in-the-loop (HITL) request tool
- people_search: People search via Exa.ai
- academic: Academic paper and author search via Semantic Scholar
- retriever: RAG retriever tool
- search: Web search (Tavily/InfoQuest)
- tts: Text-to-speech

Note: PTC sandbox tools (bash, file_ops, code_execution, etc.) have been moved to
backend.src.ptc.tools for better organization.
"""

from .crawl import crawl_tool
from .human_feedback import human_feedback_tool, request_human_input, HITL_TOOL_MARKER
from .people_search_tool import people_search_tool
from .retriever import get_retriever_tool
from .search import get_web_search_tool
from .tts import VolcengineTTS

from .academic import (
    paper_search_tool,
    get_paper_details_tool,
    search_authors_tool,
    get_author_details_tool,
    get_author_papers_tool,
    semantic_scholar_search_tool,
    arxiv_search_tool,
    pubmed_central_tool,
)

# Vision tools
from backend.src.agents.middleware.view_image_middleware import create_view_image_tool

__all__ = [
    # Web tools
    "crawl_tool",
    "get_web_search_tool",
    "get_retriever_tool",
    # HITL tools
    "human_feedback_tool",
    "HITL_TOOL_MARKER",
    "request_human_input",
    # People search
    "people_search_tool",
    # Academic research tools
    "paper_search_tool",
    "get_paper_details_tool",
    "search_authors_tool",
    "get_author_details_tool",
    "get_author_papers_tool",
    "semantic_scholar_search_tool",
    "arxiv_search_tool",
    "pubmed_central_tool",
    # Vision tools
    "create_view_image_tool",
    # TTS
    "VolcengineTTS",
]

