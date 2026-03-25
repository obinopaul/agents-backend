"""Company Search Tool - LangChain-compatible.

A robust tool for searching companies using natural language queries via Exa.ai.
Returns company information including websites, funding, industry, and enrichment data.

Usage:
    from backend.src.tools.company_search_tool import company_search_tool
    
    # Use directly
    result = await company_search_tool.ainvoke({
        "query": "AI startups in San Francisco with Series A funding",
        "enrichment_description": "Company website, funding information, and key details"
    })
    
    # Or add to agent tools
    agent = create_agent(tools=[company_search_tool])
"""

import asyncio
import json
import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.core.conf import settings

logger = logging.getLogger(__name__)

# Try to import exa_py, make tool unavailable if not installed
try:
    from exa_py import Exa
    from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False
    Exa = None
    logger.warning("exa_py not installed - Company Search Tool will not be available")


class CompanySearchInput(BaseModel):
    """Input schema for company search."""
    
    query: str = Field(
        description=(
            "Natural language search query describing the companies you want to find. "
            "Examples: 'AI startups in San Francisco with Series A funding', "
            "'E-commerce companies in Austin with 50-200 employees', "
            "'Fortune 500 companies in healthcare sector', "
            "'B2B SaaS companies with over 100 employees in New York'"
        )
    )
    enrichment_description: str = Field(
        default="Company website, founding date, industry, and key business information",
        description=(
            "What specific information to find about each company. "
            "Default: 'Company website, founding date, industry, and key business information'"
        )
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Maximum number of results to return (1-25). Default: 10"
    )


def _get_exa_client() -> Optional["Exa"]:
    """Get an Exa client instance if API key is configured."""
    if not EXA_AVAILABLE:
        return None
    
    api_key = settings.EXA_API_KEY
    if not api_key:
        logger.warning("EXA_API_KEY not configured - Company Search Tool will not work")
        return None
    
    return Exa(api_key)


def _format_company_results(items_data: list, max_results: int = 10) -> list[dict]:
    """Format raw Exa results into a structured company response."""
    formatted_results = []
    
    for idx, item in enumerate(items_data[:max_results], 1):
        # Handle different item formats
        if hasattr(item, 'model_dump'):
            item_dict = item.model_dump()
        elif isinstance(item, dict):
            item_dict = item
        else:
            item_dict = vars(item) if hasattr(item, '__dict__') else {}
        
        properties = item_dict.get('properties', {})
        company_info = properties.get('company', {})
        
        # Format evaluations
        evaluations_text = ""
        evaluations = item_dict.get('evaluations', [])
        if evaluations:
            eval_items = []
            for eval_item in evaluations:
                if isinstance(eval_item, dict):
                    criterion = eval_item.get('criterion', '')
                    satisfied = eval_item.get('satisfied', '')
                    if criterion:
                        eval_items.append(f"{criterion}: {satisfied}")
            evaluations_text = " | ".join(eval_items)
        
        # Format enrichments
        enrichment_text = ""
        if 'enrichments' in item_dict and item_dict['enrichments']:
            enrichments = item_dict['enrichments']
            if isinstance(enrichments, list) and len(enrichments) > 0:
                enrichment = enrichments[0]
                if isinstance(enrichment, dict):
                    enrich_result = enrichment.get('result')
                    if enrich_result is not None:
                        if isinstance(enrich_result, list) and enrich_result:
                            enrichment_text = str(enrich_result[0]) if enrich_result[0] else ""
                        elif isinstance(enrich_result, str):
                            enrichment_text = enrich_result
                        else:
                            enrichment_text = str(enrich_result) if enrich_result else ""
        
        # Handle None logo_url
        logo_url = company_info.get('logo_url', '')
        if logo_url is None:
            logo_url = ''
        
        # Extract company details with fallbacks
        result_entry = {
            "rank": idx,
            "id": item_dict.get('id', ''),
            "webset_id": item_dict.get('webset_id', ''),
            "source": str(item_dict.get('source', '')),
            "source_id": item_dict.get('source_id', ''),
            
            # Primary company info
            "company_name": company_info.get('name', properties.get('title', '')),
            "company_url": properties.get('url', company_info.get('website', '')),
            "company_description": properties.get('description', company_info.get('description', '')),
            
            # Company metadata
            "company_industry": company_info.get('industry', ''),
            "company_location": company_info.get('location', company_info.get('headquarters', '')),
            "company_size": company_info.get('size', company_info.get('employee_count', '')),
            "company_founded": company_info.get('founded', company_info.get('founding_date', '')),
            "company_funding": company_info.get('funding', company_info.get('total_funding', '')),
            "company_logo_url": str(logo_url) if logo_url else '',
            
            # Additional data
            "type": properties.get('type', ''),
            "evaluations": evaluations_text,
            "enrichment_data": enrichment_text,
            "created_at": str(item_dict.get('created_at', '')),
            "updated_at": str(item_dict.get('updated_at', ''))
        }
        
        formatted_results.append(result_entry)
    
    return formatted_results


def _create_summary(results: list[dict], query: str) -> str:
    """Create a human-readable summary of company search results."""
    if not results:
        return f"No companies found matching: '{query}'"
    
    summary_lines = [
        f"Found {len(results)} companies matching: '{query}'",
        "",
        "Top Results:",
        "-" * 40
    ]
    
    for result in results[:5]:  # Top 5 in summary
        name = result.get('company_name', 'Unknown')
        industry = result.get('company_industry', 'N/A')
        location = result.get('company_location', 'N/A')
        url = result.get('company_url', '')
        
        summary_lines.append(f"\n{result['rank']}. {name}")
        if industry:
            summary_lines.append(f"   Industry: {industry}")
        if location:
            summary_lines.append(f"   Location: {location}")
        if url:
            summary_lines.append(f"   Website: {url}")
    
    if len(results) > 5:
        summary_lines.append(f"\n... and {len(results) - 5} more results")
    
    return "\n".join(summary_lines)


@tool(args_schema=CompanySearchInput)
async def company_search_tool(
    query: str,
    enrichment_description: str = "Company website, founding date, industry, and key business information",
    max_results: int = 10,
) -> str:
    """Search for companies using natural language queries and enrich with business information.
    
    This tool uses Exa.ai to find companies matching your criteria. Returns up to 25 results
    with business information including:
    - Company name, description, and website
    - Industry and location
    - Funding and size (when available)
    - Custom enrichment data
    
    Args:
        query: Natural language search query describing the companies you want to find.
               Examples: 'AI startups in San Francisco with Series A funding',
               'E-commerce companies in Austin with 50-200 employees'
        enrichment_description: What specific information to find about each company.
                               Default: 'Company website, founding date, industry, and key business information'
        max_results: Maximum number of results to return (1-25). Default: 10
    
    Returns:
        JSON string with search results including company information and enrichment data.
    """
    # Validate Exa availability
    if not EXA_AVAILABLE:
        return json.dumps({
            "error": "Company Search is not available. The exa_py package is not installed.",
            "suggestion": "Install with: pip install exa_py"
        })
    
    # Get client
    exa_client = _get_exa_client()
    if not exa_client:
        return json.dumps({
            "error": "Company Search is not available. EXA_API_KEY is not configured.",
            "suggestion": "Add EXA_API_KEY to your .env file"
        })
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    # Validate max_results
    max_results = max(1, min(25, max_results))
    
    try:
        logger.info(f"Creating Exa webset for company search: '{query}' with {max_results} results")
        
        # Create enrichment config
        enrichment_config = CreateEnrichmentParameters(
            description=enrichment_description,
            format="text"
        )
        
        # Create webset parameters
        webset_params = CreateWebsetParameters(
            search={
                "query": query,
                "count": max_results,
                # Optional: filter for company-related content
                # "type": "company"  # Uncomment if Exa supports this filter
            },
            enrichments=[enrichment_config]
        )
        
        # Create webset
        try:
            webset = await asyncio.to_thread(
                exa_client.websets.create,
                params=webset_params
            )
            logger.info(f"Webset created with ID: {webset.id}")
        except Exception as create_error:
            error_str = str(create_error)
            logger.error(f"Failed to create webset: {error_str}")
            
            if "401" in error_str:
                return json.dumps({
                    "error": "Authentication failed with Exa API. Please check your API key."
                })
            elif "400" in error_str:
                return json.dumps({
                    "error": "Invalid request to Exa API. Please check your query format."
                })
            elif "429" in error_str:
                return json.dumps({
                    "error": "Rate limit exceeded. Please wait a moment and try again."
                })
            else:
                return json.dumps({
                    "error": f"Failed to create webset. Please try again. Details: {error_str[:200]}"
                })
        
        # Wait for processing
        logger.info(f"Waiting for webset {webset.id} to complete processing...")
        try:
            webset = await asyncio.to_thread(
                exa_client.websets.wait_until_idle,
                webset.id
            )
            logger.info(f"Webset {webset.id} processing complete")
        except Exception as wait_error:
            logger.error(f"Error waiting for webset: {wait_error}")
            return json.dumps({
                "error": "Failed while waiting for search results. Please try again."
            })
        
        # Retrieve items
        logger.info(f"Retrieving items from webset {webset.id}...")
        try:
            items = await asyncio.to_thread(
                exa_client.websets.items.list,
                webset_id=webset.id
            )
            logger.info("Retrieved items from webset")
        except Exception as items_error:
            logger.error(f"Error retrieving items: {items_error}")
            return json.dumps({
                "error": "Failed to retrieve search results. Please try again."
            })
        
        # Format results
        results = items.data if items else []
        formatted_results = _format_company_results(results, max_results)
        
        logger.info(f"Got {len(formatted_results)} company results from webset")
        
        # Build output
        output = {
            "query": query,
            "total_results": len(formatted_results),
            "max_requested": max_results,
            "results": formatted_results,
            "enrichment_type": enrichment_description,
            "summary": _create_summary(formatted_results, query)
        }
        
        logger.info(f"Successfully completed company search with {len(formatted_results)} results")
        
        return json.dumps(output, indent=2, default=str)
        
    except asyncio.TimeoutError:
        return json.dumps({
            "error": "Search timed out. Please try again with a simpler query."
        })
    except Exception as e:
        logger.error(f"Company search failed: {repr(e)}", exc_info=True)
        return json.dumps({
            "error": "An error occurred during the search. Please try again."
        })


# Export the tool
__all__ = ["company_search_tool", "CompanySearchInput"]
