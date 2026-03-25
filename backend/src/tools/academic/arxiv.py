"""ArXiv Search Tool - LangChain-compatible.

A tool for searching academic papers on arXiv (https://arxiv.org).
Requires the 'arxiv' package: pip install arxiv

Usage:
    from backend.src.tools.academic.arxiv import arxiv_search_tool
    
    result = await arxiv_search_tool.ainvoke({
        "query": "quantum computing",
        "sort": "Relevance",
        "max_results": 10
    })
"""

import json
import logging
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Check if arxiv is available
try:
    import arxiv
    ARXIV_AVAILABLE = True
except ImportError:
    ARXIV_AVAILABLE = False
    arxiv = None
    logger.warning("arxiv package not installed - ArXiv Search Tool will not be available")


class ArxivSearchInput(BaseModel):
    """Input schema for ArXiv search."""
    query: str = Field(description="Search query for finding papers on arXiv")
    sort: Literal["Relevance", "SubmittedDate"] = Field(
        default="Relevance",
        description="Sort by 'Relevance' or 'SubmittedDate'"
    )
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results (1-100)")


@tool(args_schema=ArxivSearchInput)
def arxiv_search_tool(
    query: str,
    sort: str = "Relevance",
    max_results: int = 10,
) -> str:
    """Search for academic papers on arXiv.
    
    ArXiv is a free repository of scientific papers, particularly strong in
    physics, mathematics, computer science, and related fields.
    
    Args:
        query: Search query (e.g., 'quantum computing', 'machine learning')
        sort: Sort by 'Relevance' or 'SubmittedDate'
        max_results: Maximum number of results (1-100)
    
    Returns:
        JSON with paper results including title, PDF URL, abstract, authors.
    """
    if not ARXIV_AVAILABLE:
        return json.dumps({
            "error": "ArXiv search is not available. The 'arxiv' package is not installed.",
            "suggestion": "Install with: pip install arxiv"
        })
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    if sort not in ["Relevance", "SubmittedDate"]:
        return json.dumps({"error": "Sort must be 'Relevance' or 'SubmittedDate'"})
    
    try:
        logger.info(f"Searching arXiv for: '{query}' (max: {max_results})")
        
        # Set sort criterion
        sort_criterion = (
            arxiv.SortCriterion.SubmittedDate 
            if sort == "SubmittedDate" 
            else arxiv.SortCriterion.Relevance
        )
        
        # Perform search
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_criterion,
        )
        
        results = list(arxiv.Client().results(search))
        
        formatted_results = []
        for idx, result in enumerate(results, 1):
            # Get author names
            authors = [author.name for author in result.authors]
            
            # Get categories
            categories = result.categories if hasattr(result, 'categories') else []
            
            formatted_results.append({
                "rank": idx,
                "title": result.title,
                "pdf_url": result.pdf_url,
                "abstract": result.summary,
                "authors": authors,
                "published": str(result.published) if result.published else None,
                "updated": str(result.updated) if result.updated else None,
                "arxiv_id": result.entry_id.split("/")[-1] if result.entry_id else None,
                "primary_category": result.primary_category if hasattr(result, 'primary_category') else None,
                "categories": categories,
                "comment": result.comment if hasattr(result, 'comment') else None,
                "journal_ref": result.journal_ref if hasattr(result, 'journal_ref') else None,
                "doi": result.doi if hasattr(result, 'doi') else None,
            })
        
        output = {
            "query": query,
            "sort": sort,
            "total_results": len(formatted_results),
            "results": formatted_results
        }
        
        logger.info(f"Found {len(formatted_results)} papers on arXiv")
        return json.dumps(output, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"ArXiv search failed: {e}", exc_info=True)
        return json.dumps({"error": f"ArXiv search failed: {str(e)}"})


# Keep legacy class for backward compatibility
class ArxivSearch:
    """Legacy class - use arxiv_search_tool instead."""
    
    def __init__(self, query: str, sort: str = "Relevance", query_domains=None):
        self.query = query
        assert sort in ["Relevance", "SubmittedDate"], "Invalid sort criterion"
        self.sort = sort

    def search(self, max_results: int = 5):
        """Performs the search."""
        result = arxiv_search_tool.invoke({
            "query": self.query,
            "sort": self.sort,
            "max_results": max_results
        })
        data = json.loads(result)
        
        # Return in legacy format
        if "error" in data:
            return []
        
        return [
            {
                "title": r.get("title", ""),
                "href": r.get("pdf_url", ""),
                "body": r.get("abstract", ""),
            }
            for r in data.get("results", [])
        ]


__all__ = ["arxiv_search_tool", "ArxivSearch", "ARXIV_AVAILABLE"]