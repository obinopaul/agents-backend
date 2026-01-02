"""Paper Search Tool - LangChain-compatible.

A comprehensive academic research tool using Semantic Scholar API.
Provides paper search, author search, detailed paper info, and more.

Features:
- Search for academic papers by keywords, topics, authors
- Get detailed paper information with citations and references
- Search for authors and their publications
- Filter by year, field of study, open access
- Rate-limited requests with retry logic

Usage:
    from backend.src.tools.academic.paper_search_tool import (
        paper_search_tool,
        get_paper_details_tool,
        search_authors_tool,
        get_author_details_tool,
        get_author_papers_tool,
    )
    
    # Use directly
    result = await paper_search_tool.ainvoke({
        "query": "transformer architectures attention mechanisms",
        "limit": 10
    })
    
    # Or add to agent
    agent = create_agent(tools=[paper_search_tool, get_paper_details_tool])
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.core.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# API Client with Rate Limiting
# =============================================================================

class SemanticScholarClient:
    """Rate-limited client for Semantic Scholar API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self):
        self.last_request_time = 0
        self.request_lock = asyncio.Lock()
    
    @property
    def api_key(self) -> str:
        return settings.SEMANTIC_SCHOLAR_API_KEY
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Make a rate-limited request to the API."""
        if not self.is_available:
            raise ValueError("SEMANTIC_SCHOLAR_API_KEY not configured")
        
        async with self.request_lock:
            # Rate limiting: at least 1 second between requests
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < 1.0:
                await asyncio.sleep(1.0 - time_since_last)
            
            headers = {"x-api-key": self.api_key}
            url = f"{self.BASE_URL}/{endpoint}"
            
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params, headers=headers) as response:
                            self.last_request_time = time.time()
                            
                            if response.status == 429:
                                retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                                logger.warning(f"Rate limited, waiting {retry_after}s before retry")
                                await asyncio.sleep(retry_after)
                                continue
                            
                            if response.status == 200:
                                return await response.json()
                            else:
                                error_text = await response.text()
                                logger.error(f"API request failed: {response.status} - {error_text}")
                                
                                if response.status >= 500 and attempt < max_retries - 1:
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                
                                raise Exception(f"API error: {response.status} - {error_text}")
                
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except aiohttp.ClientError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
            
            raise Exception(f"Failed after {max_retries} attempts")


# Singleton client
_client = SemanticScholarClient()


# =============================================================================
# Input Schemas
# =============================================================================

class PaperSearchInput(BaseModel):
    """Input schema for paper search."""
    query: str = Field(description="Search query for finding academic papers")
    year: Optional[str] = Field(default=None, description="Filter by year range (e.g., '2020-2023')")
    fields_of_study: Optional[str] = Field(default=None, description="Comma-separated fields (e.g., 'Computer Science,Physics')")
    open_access_only: bool = Field(default=False, description="Only return open access papers")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results (1-100)")


class PaperDetailsInput(BaseModel):
    """Input schema for paper details."""
    paper_id: str = Field(description="Semantic Scholar paper ID")
    include_citations: bool = Field(default=False, description="Include papers that cite this paper")
    include_references: bool = Field(default=False, description="Include referenced papers")


class AuthorSearchInput(BaseModel):
    """Input schema for author search."""
    query: str = Field(description="Author name to search for")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results (1-100)")


class AuthorDetailsInput(BaseModel):
    """Input schema for author details."""
    author_id: str = Field(description="Semantic Scholar author ID")
    include_papers: bool = Field(default=False, description="Include author's papers")
    papers_limit: int = Field(default=10, ge=1, le=100, description="Number of papers to return")


class AuthorPapersInput(BaseModel):
    """Input schema for author papers."""
    author_id: str = Field(description="Semantic Scholar author ID")
    limit: int = Field(default=100, ge=1, le=1000, description="Number of papers (1-1000)")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


# =============================================================================
# Helper Functions
# =============================================================================

def _format_paper(paper: Dict, idx: int = 1) -> Dict:
    """Format a paper result."""
    open_access_pdf = paper.get('openAccessPdf')
    pdf_url = open_access_pdf.get('url') if open_access_pdf else None
    
    venue_info = paper.get('publicationVenue') or {}
    
    authors_list = []
    for author in paper.get('authors', []):
        authors_list.append({
            "name": author.get('name', ''),
            "author_id": author.get('authorId', '')
        })
    
    return {
        "rank": idx,
        "paper_id": paper.get('paperId', ''),
        "title": paper.get('title', ''),
        "abstract": paper.get('abstract', ''),
        "year": paper.get('year'),
        "url": paper.get('url', ''),
        "authors": authors_list,
        "venue": paper.get('venue', ''),
        "venue_type": venue_info.get('type', ''),
        "citation_count": paper.get('citationCount', 0),
        "reference_count": paper.get('referenceCount', 0),
        "influential_citation_count": paper.get('influentialCitationCount', 0),
        "is_open_access": paper.get('isOpenAccess', False),
        "pdf_url": pdf_url,
        "fields_of_study": paper.get('fieldsOfStudy', []),
        "publication_types": paper.get('publicationTypes', []),
        "publication_date": paper.get('publicationDate', ''),
        "journal": paper.get('journal', {}).get('name', '') if paper.get('journal') else ''
    }


def _format_author(author: Dict, idx: int = 1) -> Dict:
    """Format an author result."""
    return {
        "rank": idx,
        "author_id": author.get('authorId', ''),
        "name": author.get('name', ''),
        "url": author.get('url', ''),
        "affiliations": author.get('affiliations', []),
        "homepage": author.get('homepage', ''),
        "paper_count": author.get('paperCount', 0),
        "citation_count": author.get('citationCount', 0),
        "h_index": author.get('hIndex', 0),
        "external_ids": author.get('externalIds', {})
    }


def _check_api_available() -> Optional[str]:
    """Check if API is available, return error message if not."""
    if not _client.is_available:
        return json.dumps({
            "error": "Paper Search is not available. SEMANTIC_SCHOLAR_API_KEY is not configured.",
            "suggestion": "Add SEMANTIC_SCHOLAR_API_KEY to your .env file"
        })
    return None


# =============================================================================
# LangChain Tools
# =============================================================================

@tool(args_schema=PaperSearchInput)
async def paper_search_tool(
    query: str,
    year: Optional[str] = None,
    fields_of_study: Optional[str] = None,
    open_access_only: bool = False,
    limit: int = 10,
) -> str:
    """Search for academic papers using Semantic Scholar (FREE).
    
    Returns papers with titles, abstracts, authors, citations, and publication details.
    Use this to find relevant research on any topic.
    
    Args:
        query: Search query (e.g., 'transformer architectures', 'climate change')
        year: Filter by year range (e.g., '2020-2023' or '2023')
        fields_of_study: Comma-separated fields (e.g., 'Computer Science,Physics')
        open_access_only: Only return papers with free PDF access
        limit: Number of results (1-100, default: 10)
    
    Returns:
        JSON with paper results including title, abstract, authors, citations.
    """
    error = _check_api_available()
    if error:
        return error
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    try:
        logger.info(f"Searching Semantic Scholar for: '{query}' (limit: {limit})")
        
        params = {
            "query": query,
            "limit": limit,
            "fields": "paperId,title,abstract,year,authors,url,venue,publicationVenue,citationCount,referenceCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,s2FieldsOfStudy,publicationTypes,publicationDate,journal"
        }
        
        if year:
            params["year"] = year
        if fields_of_study:
            params["fieldsOfStudy"] = fields_of_study
        if open_access_only:
            params["openAccessPdf"] = ""
        
        data = await _client.request("paper/search", params)
        
        results = data.get('data', [])
        total = data.get('total', 0)
        
        formatted_results = [_format_paper(paper, idx) for idx, paper in enumerate(results, 1)]
        
        output = {
            "query": query,
            "total_available": total,
            "results_returned": len(formatted_results),
            "results": formatted_results
        }
        
        logger.info(f"Found {len(formatted_results)} papers")
        return json.dumps(output, indent=2, default=str)
        
    except asyncio.TimeoutError:
        return json.dumps({"error": "Search timed out. Try a simpler query."})
    except Exception as e:
        logger.error(f"Paper search failed: {e}", exc_info=True)
        return json.dumps({"error": f"Search failed: {str(e)}"})


@tool(args_schema=PaperDetailsInput)
async def get_paper_details_tool(
    paper_id: str,
    include_citations: bool = False,
    include_references: bool = False,
) -> str:
    """Get detailed information about a specific paper (FREE).
    
    Use this after paper_search to get full details including TLDR, citations, and references.
    
    Args:
        paper_id: Semantic Scholar paper ID from search results
        include_citations: Include papers that cite this paper (up to 50)
        include_references: Include papers referenced by this paper (up to 50)
    
    Returns:
        JSON with full paper details including abstract, TLDR, authors, citations.
    """
    error = _check_api_available()
    if error:
        return error
    
    if not paper_id:
        return json.dumps({"error": "Paper ID is required."})
    
    try:
        logger.info(f"Fetching details for paper: {paper_id}")
        
        fields = "paperId,corpusId,title,abstract,year,authors,url,venue,publicationVenue,citationCount,referenceCount,influentialCitationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,s2FieldsOfStudy,publicationTypes,publicationDate,journal,citationStyles,externalIds,tldr,embedding"
        
        if include_citations:
            fields += ",citations.paperId,citations.title,citations.year,citations.authors,citations.citationCount"
        if include_references:
            fields += ",references.paperId,references.title,references.year,references.authors,references.citationCount"
        
        data = await _client.request(f"paper/{paper_id}", {"fields": fields})
        
        # Format authors
        authors_list = []
        for author in data.get('authors', []):
            authors_list.append({
                "author_id": author.get('authorId', ''),
                "name": author.get('name', ''),
                "url": author.get('url', ''),
                "affiliations": author.get('affiliations', []),
            })
        
        # Format PDF info
        open_access_pdf = data.get('openAccessPdf')
        pdf_info = None
        if open_access_pdf:
            pdf_info = {
                "url": open_access_pdf.get('url'),
                "status": open_access_pdf.get('status'),
                "license": open_access_pdf.get('license')
            }
        
        venue_info = data.get('publicationVenue') or {}
        
        # Format citations
        citations_list = []
        if include_citations and data.get('citations'):
            for citation in data.get('citations', [])[:50]:
                citation_authors = [a.get('name', '') for a in citation.get('authors', [])]
                citations_list.append({
                    "paper_id": citation.get('paperId', ''),
                    "title": citation.get('title', ''),
                    "year": citation.get('year'),
                    "authors": citation_authors,
                    "citation_count": citation.get('citationCount', 0)
                })
        
        # Format references
        references_list = []
        if include_references and data.get('references'):
            for ref in data.get('references', [])[:50]:
                ref_authors = [a.get('name', '') for a in ref.get('authors', [])]
                references_list.append({
                    "paper_id": ref.get('paperId', ''),
                    "title": ref.get('title', ''),
                    "year": ref.get('year'),
                    "authors": ref_authors,
                    "citation_count": ref.get('citationCount', 0)
                })
        
        # Get TLDR
        tldr_text = None
        if data.get('tldr'):
            tldr_text = data['tldr'].get('text', '')
        
        result = {
            "paper_id": data.get('paperId', ''),
            "corpus_id": data.get('corpusId'),
            "title": data.get('title', ''),
            "abstract": data.get('abstract', ''),
            "tldr": tldr_text,
            "year": data.get('year'),
            "url": data.get('url', ''),
            "authors": authors_list,
            "venue": data.get('venue', ''),
            "venue_name": venue_info.get('name', ''),
            "venue_type": venue_info.get('type', ''),
            "citation_count": data.get('citationCount', 0),
            "reference_count": data.get('referenceCount', 0),
            "influential_citation_count": data.get('influentialCitationCount', 0),
            "is_open_access": data.get('isOpenAccess', False),
            "pdf_info": pdf_info,
            "fields_of_study": data.get('fieldsOfStudy', []),
            "publication_types": data.get('publicationTypes', []),
            "publication_date": data.get('publicationDate', ''),
            "journal": data.get('journal', {}).get('name', '') if data.get('journal') else '',
            "external_ids": data.get('externalIds', {}),
            "citation_styles": data.get('citationStyles', {}),
            "citations": citations_list if include_citations else None,
            "references": references_list if include_references else None
        }
        
        logger.info(f"Retrieved details for paper: {paper_id}")
        return json.dumps({"paper": result}, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Get paper details failed: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to get paper details: {str(e)}"})


@tool(args_schema=AuthorSearchInput)
async def search_authors_tool(
    query: str,
    limit: int = 10,
) -> str:
    """Search for academic authors and researchers (FREE).
    
    Returns author profiles with publication counts, citations, and h-index.
    
    Args:
        query: Author name to search for (e.g., 'Geoffrey Hinton', 'Yann LeCun')
        limit: Number of results (1-100, default: 10)
    
    Returns:
        JSON with author results including name, affiliations, paper count, h-index.
    """
    error = _check_api_available()
    if error:
        return error
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    try:
        logger.info(f"Searching for authors: '{query}'")
        
        params = {
            "query": query,
            "limit": limit,
            "fields": "authorId,name,url,affiliations,homepage,paperCount,citationCount,hIndex,externalIds"
        }
        
        data = await _client.request("author/search", params)
        
        results = data.get('data', [])
        total = data.get('total', 0)
        
        formatted_results = [_format_author(author, idx) for idx, author in enumerate(results, 1)]
        
        output = {
            "query": query,
            "total_available": total,
            "results_returned": len(formatted_results),
            "results": formatted_results
        }
        
        logger.info(f"Found {len(formatted_results)} authors")
        return json.dumps(output, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Author search failed: {e}", exc_info=True)
        return json.dumps({"error": f"Author search failed: {str(e)}"})


@tool(args_schema=AuthorDetailsInput)
async def get_author_details_tool(
    author_id: str,
    include_papers: bool = False,
    papers_limit: int = 10,
) -> str:
    """Get detailed information about a specific author (FREE).
    
    Returns author profile with metrics and optionally their papers.
    
    Args:
        author_id: Semantic Scholar author ID from search results
        include_papers: Include author's papers
        papers_limit: Number of papers to return if include_papers is true
    
    Returns:
        JSON with author details including affiliations, h-index, and papers.
    """
    error = _check_api_available()
    if error:
        return error
    
    if not author_id:
        return json.dumps({"error": "Author ID is required."})
    
    try:
        logger.info(f"Fetching details for author: {author_id}")
        
        fields = "authorId,name,url,affiliations,homepage,paperCount,citationCount,hIndex,externalIds"
        if include_papers:
            fields += ",papers.paperId,papers.title,papers.year,papers.citationCount,papers.url,papers.venue,papers.abstract"
        
        params = {"fields": fields}
        if include_papers:
            params["limit"] = papers_limit
        
        data = await _client.request(f"author/{author_id}", params)
        
        # Format papers
        papers_list = []
        if include_papers and data.get('papers'):
            for paper in data.get('papers', [])[:papers_limit]:
                papers_list.append({
                    "paper_id": paper.get('paperId', ''),
                    "title": paper.get('title', ''),
                    "year": paper.get('year'),
                    "citation_count": paper.get('citationCount', 0),
                    "url": paper.get('url', ''),
                    "venue": paper.get('venue', ''),
                    "abstract": paper.get('abstract', '')
                })
        
        result = {
            "author_id": data.get('authorId', ''),
            "name": data.get('name', ''),
            "url": data.get('url', ''),
            "affiliations": data.get('affiliations', []),
            "homepage": data.get('homepage', ''),
            "paper_count": data.get('paperCount', 0),
            "citation_count": data.get('citationCount', 0),
            "h_index": data.get('hIndex', 0),
            "external_ids": data.get('externalIds', {}),
            "papers": papers_list if include_papers else None
        }
        
        logger.info(f"Retrieved details for author: {author_id}")
        return json.dumps({"author": result}, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Get author details failed: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to get author details: {str(e)}"})


@tool(args_schema=AuthorPapersInput)
async def get_author_papers_tool(
    author_id: str,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Get all papers by a specific author (FREE).
    
    Returns a paginated list of an author's publications.
    
    Args:
        author_id: Semantic Scholar author ID
        limit: Number of papers (1-1000, default: 100)
        offset: Pagination offset for large result sets
    
    Returns:
        JSON with author's papers including citations and publication details.
    """
    error = _check_api_available()
    if error:
        return error
    
    if not author_id:
        return json.dumps({"error": "Author ID is required."})
    
    try:
        logger.info(f"Fetching papers for author: {author_id}")
        
        params = {
            "fields": "paperId,title,abstract,year,citationCount,referenceCount,influentialCitationCount,url,venue,publicationVenue,isOpenAccess,openAccessPdf,fieldsOfStudy,publicationTypes,publicationDate,journal",
            "limit": limit,
            "offset": offset
        }
        
        data = await _client.request(f"author/{author_id}/papers", params)
        
        papers = data.get('data', [])
        next_offset = data.get('next')
        
        formatted_papers = [_format_paper(paper, offset + idx) for idx, paper in enumerate(papers, 1)]
        
        output = {
            "author_id": author_id,
            "papers_returned": len(formatted_papers),
            "offset": offset,
            "next_offset": next_offset,
            "has_more": next_offset is not None,
            "papers": formatted_papers
        }
        
        logger.info(f"Retrieved {len(formatted_papers)} papers for author: {author_id}")
        return json.dumps(output, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Get author papers failed: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to get author papers: {str(e)}"})


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "paper_search_tool",
    "get_paper_details_tool",
    "search_authors_tool",
    "get_author_details_tool",
    "get_author_papers_tool",
    "SemanticScholarClient",
]