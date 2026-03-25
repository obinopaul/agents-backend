"""Academic Tools Package.

Tools for academic research including paper search, author search, and more.

Available tools:
- paper_search_tool: Comprehensive paper search via Semantic Scholar (with citations)
- get_paper_details_tool: Get full paper details with TLDR, citations, references
- search_authors_tool: Search for academic authors
- get_author_details_tool: Get author profile with h-index and papers
- get_author_papers_tool: Get all papers by an author (paginated)
- semantic_scholar_search_tool: Simple open-access paper search
- arxiv_search_tool: Search papers on arXiv
"""

from .paper_search_tool import (
    paper_search_tool,
    get_paper_details_tool,
    search_authors_tool,
    get_author_details_tool,
    get_author_papers_tool,
    SemanticScholarClient,
)

from .semantic_scholar import (
    semantic_scholar_search_tool,
    SemanticScholarSearch,  # Legacy class
)

from .arxiv import (
    arxiv_search_tool,
    ArxivSearch,  # Legacy class
    ARXIV_AVAILABLE,
)

from .pubmed_central import (
    pubmed_central_tool,
    PubMedCentralSearch,
)

__all__ = [
    # Paper search (comprehensive)
    "paper_search_tool",
    "get_paper_details_tool",
    "search_authors_tool",
    "get_author_details_tool",
    "get_author_papers_tool",
    "SemanticScholarClient",
    # Semantic Scholar (simple open access)
    "semantic_scholar_search_tool",
    "SemanticScholarSearch",
    # ArXiv
    "arxiv_search_tool",
    "ArxivSearch",
    "ARXIV_AVAILABLE",
    # PubMed Central
    "pubmed_central_tool",
    "PubMedCentralSearch",
]

