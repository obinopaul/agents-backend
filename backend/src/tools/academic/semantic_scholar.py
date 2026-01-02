"""Semantic Scholar Search Tool - LangChain-compatible.

A lightweight tool for searching open access papers on Semantic Scholar.
This is a simpler alternative to paper_search_tool.py that only returns
papers with free PDF access.

Note: For more comprehensive academic search with author lookup, citations,
and references, use paper_search_tool.py instead.

Usage:
    from backend.src.tools.academic.semantic_scholar import semantic_scholar_search_tool
    
    result = await semantic_scholar_search_tool.ainvoke({
        "query": "transformer attention mechanisms",
        "sort": "relevance",
        "max_results": 10
    })
"""

import json
import logging
from typing import Literal, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.core.conf import settings

logger = logging.getLogger(__name__)


class SemanticScholarSearchInput(BaseModel):
    """Input schema for Semantic Scholar search."""
    query: str = Field(description="Search query for finding academic papers")
    sort: Literal["relevance", "citationCount", "publicationDate"] = Field(
        default="relevance",
        description="Sort criterion: 'relevance', 'citationCount', or 'publicationDate'"
    )
    max_results: int = Field(default=20, ge=1, le=100, description="Maximum results (1-100)")


@tool(args_schema=SemanticScholarSearchInput)
def semantic_scholar_search_tool(
    query: str,
    sort: str = "relevance",
    max_results: int = 20,
) -> str:
    """Search for open access academic papers on Semantic Scholar.
    
    Returns only papers that have free PDF access. For more comprehensive
    search including all papers, use paper_search_tool instead.
    
    Args:
        query: Search query for finding papers
        sort: Sort by 'relevance', 'citationCount', or 'publicationDate'
        max_results: Maximum number of results (1-100)
    
    Returns:
        JSON with paper results (open access only) including title, PDF URL, abstract.
    """
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    valid_sorts = ["relevance", "citationCount", "publicationDate"]
    if sort.lower() not in [s.lower() for s in valid_sorts]:
        return json.dumps({"error": f"Invalid sort. Must be one of: {valid_sorts}"})
    
    try:
        logger.info(f"Searching Semantic Scholar (open access): '{query}'")
        
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,url,venue,year,authors,isOpenAccess,openAccessPdf",
            "sort": sort.lower(),
        }
        
        # Add API key if available
        headers = {}
        if settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY
        
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        results = response.json().get("data", [])
        
        # Filter for open access papers only
        search_results = []
        for idx, result in enumerate(results, 1):
            if result.get("isOpenAccess") and result.get("openAccessPdf"):
                # Get author names
                authors = [a.get("name", "") for a in result.get("authors", [])]
                
                search_results.append({
                    "rank": idx,
                    "title": result.get("title", "No Title"),
                    "pdf_url": result["openAccessPdf"].get("url", ""),
                    "abstract": result.get("abstract", "Abstract not available"),
                    "year": result.get("year"),
                    "venue": result.get("venue", ""),
                    "url": result.get("url", ""),
                    "authors": authors,
                })
        
        output = {
            "query": query,
            "sort": sort,
            "total_results": len(search_results),
            "note": "Only open access papers with free PDF are returned",
            "results": search_results
        }
        
        logger.info(f"Found {len(search_results)} open access papers")
        return json.dumps(output, indent=2, default=str)
        
    except requests.Timeout:
        return json.dumps({"error": "Request timed out. Try again."})
    except requests.RequestException as e:
        logger.error(f"Semantic Scholar API error: {e}")
        return json.dumps({"error": f"API error: {str(e)}"})
    except Exception as e:
        logger.error(f"Semantic Scholar search failed: {e}", exc_info=True)
        return json.dumps({"error": f"Search failed: {str(e)}"})


# Keep legacy class for backward compatibility
class SemanticScholarSearch:
    """Legacy class - use semantic_scholar_search_tool instead."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    VALID_SORT_CRITERIA = ["relevance", "citationCount", "publicationDate"]

    def __init__(self, query: str, sort: str = "relevance", query_domains=None):
        self.query = query
        assert sort in self.VALID_SORT_CRITERIA, "Invalid sort criterion"
        self.sort = sort.lower()

    def search(self, max_results: int = 20):
        """Perform the search on Semantic Scholar."""
        result = semantic_scholar_search_tool.invoke({
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
                "title": r.get("title", "No Title"),
                "href": r.get("pdf_url", "No URL"),
                "body": r.get("abstract", "Abstract not available"),
            }
            for r in data.get("results", [])
        ]


__all__ = ["semantic_scholar_search_tool", "SemanticScholarSearch"]