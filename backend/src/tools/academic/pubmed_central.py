"""PubMed Central Search Tool - LangChain-compatible.

A tool for searching and retrieving full-text articles from PubMed Central (PMC).
Requires NCBI_API_KEY in settings for higher rate limits.

Usage:
    from backend.src.tools.academic.pubmed_central import pubmed_central_tool
    
    result = await pubmed_central_tool.ainvoke({
        "query": "genome sequencing",
        "max_results": 3
    })
"""

import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.core.conf import settings

logger = logging.getLogger(__name__)


class PubMedCentralInput(BaseModel):
    """Input schema for PubMed Central search."""
    query: str = Field(description="Search query for PMC articles")
    max_results: int = Field(default=5, ge=1, le=20, description="Number of results (1-20)")
    email: Optional[str] = Field(default=None, description="Email for NCBI identification (recommended)")


@tool(args_schema=PubMedCentralInput)
def pubmed_central_tool(
    query: str,
    max_results: int = 5,
    email: Optional[str] = None
) -> str:
    """Search and retrieve full-text articles from PubMed Central (PMC).
    
    Returns full text content including abstract and body where available.
    best for deep reading of biomedical literature.
    
    Args:
        query: Search query (e.g., 'CRISPR Cas9', 'covid-19 vaccine')
        max_results: Maximum number of articles to retrieve (1-20, default: 5)
        email: Optional email contact for NCBI (good practice)
    
    Returns:
        JSON with article details including title, abstract, body text, and URL.
    """
    base_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    base_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    api_key = settings.NCBI_API_KEY
    if not api_key:
        logger.warning("NCBI_API_KEY not set. Requests will be rate-limited.")
    
    try:
        logger.info(f"Searching PubMed Central for: '{query}'")
        
        # Step 1: Search for IDs
        search_params = {
            "db": "pmc",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "tool": "agents-backend",
        }
        
        if api_key:
            search_params["api_key"] = api_key
        if email:
            search_params["email"] = email
            
        search_resp = requests.get(base_search_url, params=search_params, timeout=30)
        search_resp.raise_for_status()
        search_data = search_resp.json()
        
        id_list = search_data.get('esearchresult', {}).get('idlist', [])
        
        if not id_list:
            return json.dumps({
                "query": query,
                "total_results": 0,
                "results": []
            })
            
        logger.info(f"Found {len(id_list)} articles, fetching details...")
        
        # Step 2: Fetch details for each ID
        results = []
        for article_id in id_list:
            try:
                fetch_params = {
                    "db": "pmc",
                    "id": article_id,
                    "rettype": "full",
                    "retmode": "xml",
                }
                if api_key:
                    fetch_params["api_key"] = api_key
                    
                fetch_resp = requests.get(base_fetch_url, params=fetch_params, timeout=30)
                fetch_resp.raise_for_status()
                
                # Parse XML
                root = ET.fromstring(fetch_resp.text)
                
                # Extract title
                title_elem = root.find('.//article-title')
                title = title_elem.text if title_elem is not None else "No Title"
                
                # Extract abstract
                abstract_elem = root.find('.//abstract')
                abstract = " ".join(abstract_elem.itertext()) if abstract_elem is not None else ""
                
                # Extract body
                body_elem = root.find('.//body')
                body_text = " ".join(body_elem.itertext()) if body_elem is not None else ""
                
                # Build URL
                url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{article_id}/"
                if article_id.startswith("PMC"):
                     url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article_id}/"
                
                results.append({
                    "pmc_id": article_id,
                    "title": title,
                    "url": url,
                    "abstract": abstract[:1000] + "..." if len(abstract) > 1000 else abstract,
                    "body_excerpt": body_text[:2000] + "..." if len(body_text) > 2000 else body_text,
                    "has_full_text": bool(body_text)
                })
                
            except Exception as inner_e:
                logger.warning(f"Failed to fetch/parse article {article_id}: {inner_e}")
                continue
                
        output = {
            "query": query,
            "total_results": len(results),
            "results": results
        }
        
        return json.dumps(output, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"PubMed Central search failed: {e}", exc_info=True)
        return json.dumps({"error": f"Search failed: {str(e)}"})


# Legacy class wrapper
class PubMedCentralSearch:
    """Legacy class - use pubmed_central_tool instead."""
    
    def __init__(self, query: str, query_domains=None):
        self.query = query
        self.api_key = settings.NCBI_API_KEY

    def search(self, max_results: int = 5):
        """Perform search."""
        result = pubmed_central_tool.invoke({
            "query": self.query,
            "max_results": max_results
        })
        data = json.loads(result)
        
        if "error" in data:
            return None
            
        legacy_results = []
        for r in data.get("results", []):
            content = f"Title: {r['title']}\n\nAbstract: {r.get('abstract','')}\n\nBody: {r.get('body_excerpt','')}"
            legacy_results.append({
                "url": r["url"],
                "raw_content": content,
                "title": r["title"]
            })
        return legacy_results


__all__ = ["pubmed_central_tool", "PubMedCentralSearch"]