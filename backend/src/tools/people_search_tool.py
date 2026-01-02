"""People Search Tool - LangChain-compatible.

A robust tool for searching people using natural language queries via Exa.ai.
Returns professional background information, LinkedIn profiles, and enrichment data.

Usage:
    from backend.src.tools.people_search_tool import people_search_tool
    
    # Use directly
    result = await people_search_tool.ainvoke({
        "query": "CTOs at AI startups in San Francisco",
        "enrichment_description": "LinkedIn profile URL"
    })
    
    # Or add to agent tools
    agent = create_agent(tools=[people_search_tool])
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
    logger.warning("exa_py not installed - People Search Tool will not be available")


class PeopleSearchInput(BaseModel):
    """Input schema for people search."""
    
    query: str = Field(
        description=(
            "Natural language search query describing the people you want to find. "
            "Examples: 'CTOs at AI startups in San Francisco', "
            "'Senior Python developers with machine learning experience at Google', "
            "'Marketing managers at Fortune 500 companies in New York'"
        )
    )
    enrichment_description: str = Field(
        default="LinkedIn profile URL",
        description="What specific information to find about each person. Default: 'LinkedIn profile URL'"
    )


def _get_exa_client() -> Optional["Exa"]:
    """Get an Exa client instance if API key is configured."""
    if not EXA_AVAILABLE:
        return None
    
    api_key = settings.EXA_API_KEY
    if not api_key:
        logger.warning("EXA_API_KEY not configured - People Search Tool will not work")
        return None
    
    return Exa(api_key)


def _format_results(items_data: list) -> list[dict]:
    """Format raw Exa results into a structured response."""
    formatted_results = []
    
    for idx, item in enumerate(items_data[:10], 1):
        # Handle different item formats
        if hasattr(item, 'model_dump'):
            item_dict = item.model_dump()
        elif isinstance(item, dict):
            item_dict = item
        else:
            item_dict = vars(item) if hasattr(item, '__dict__') else {}
        
        properties = item_dict.get('properties', {})
        person_info = properties.get('person', {})
        
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
        
        # Handle None picture_url
        picture_url = person_info.get('picture_url', '')
        if picture_url is None:
            picture_url = ''
        
        result_entry = {
            "rank": idx,
            "id": item_dict.get('id', ''),
            "webset_id": item_dict.get('webset_id', ''),
            "source": str(item_dict.get('source', '')),
            "source_id": item_dict.get('source_id', ''),
            "url": properties.get('url', ''),
            "type": properties.get('type', ''),
            "description": properties.get('description', ''),
            "person_name": person_info.get('name', ''),
            "person_location": person_info.get('location', ''),
            "person_position": person_info.get('position', ''),
            "person_picture_url": str(picture_url) if picture_url else '',
            "evaluations": evaluations_text,
            "enrichment_data": enrichment_text,
            "created_at": str(item_dict.get('created_at', '')),
            "updated_at": str(item_dict.get('updated_at', ''))
        }
        
        formatted_results.append(result_entry)
    
    return formatted_results


@tool(args_schema=PeopleSearchInput)
async def people_search_tool(
    query: str,
    enrichment_description: str = "LinkedIn profile URL",
) -> str:
    """Search for people using natural language queries and enrich with LinkedIn profiles.
    
    This tool uses Exa.ai to find people matching your criteria. Returns up to 10 results
    with professional background information including:
    - Name, position, location
    - LinkedIn profile URL (or custom enrichment)
    - Source website and description
    
    Args:
        query: Natural language search query describing the people you want to find.
               Examples: 'CTOs at AI startups in San Francisco',
               'Senior Python developers with machine learning experience at Google'
        enrichment_description: What specific information to find about each person.
                               Default: 'LinkedIn profile URL'
    
    Returns:
        JSON string with search results including person information and enrichment data.
    """
    # Validate Exa availability
    if not EXA_AVAILABLE:
        return json.dumps({
            "error": "People Search is not available. The exa_py package is not installed.",
            "suggestion": "Install with: pip install exa_py"
        })
    
    # Get client
    exa_client = _get_exa_client()
    if not exa_client:
        return json.dumps({
            "error": "People Search is not available. EXA_API_KEY is not configured.",
            "suggestion": "Add EXA_API_KEY to your .env file"
        })
    
    if not query:
        return json.dumps({"error": "Search query is required."})
    
    try:
        logger.info(f"Creating Exa webset for: '{query}' with 10 results")
        
        # Create enrichment config
        enrichment_config = CreateEnrichmentParameters(
            description=enrichment_description,
            format="text"
        )
        
        # Create webset parameters
        webset_params = CreateWebsetParameters(
            search={
                "query": query,
                "count": 10
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
            else:
                return json.dumps({
                    "error": "Failed to create webset. Please try again."
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
        formatted_results = _format_results(results)
        
        logger.info(f"Got {len(formatted_results)} results from webset")
        
        # Build output
        output = {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results,
            "enrichment_type": enrichment_description
        }
        
        logger.info(f"Successfully completed people search with {len(formatted_results)} results")
        
        return json.dumps(output, indent=2, default=str)
        
    except asyncio.TimeoutError:
        return json.dumps({
            "error": "Search timed out. Please try again with a simpler query."
        })
    except Exception as e:
        logger.error(f"People search failed: {repr(e)}", exc_info=True)
        return json.dumps({
            "error": "An error occurred during the search. Please try again."
        })


# Export the tool
__all__ = ["people_search_tool", "PeopleSearchInput"]
