"""Custom tools for the CLI agent."""

from typing import Any, Literal

import requests
from markdownify import markdownify
from tavily import TavilyClient

from deepagents_cli.config import settings

# Initialize Tavily client if API key is available
tavily_client = TavilyClient(api_key=settings.tavily_api_key) if settings.has_tavily else None


# =============================================================================
# MCP Tools Integration
# =============================================================================
#
# The Agent-Infra Sandbox exposes ALL its tools via MCP at {base_url}/mcp/
# This is the RECOMMENDED way to get sandbox tools:
#
#     tools = await get_sandbox_tools()
#     agent = create_deep_agent(tools=tools, ...)
#
# =============================================================================

async def get_sandbox_tools(base_url: str | None = None):
    """Get all sandbox tools via MCP (async).
    
    This is the RECOMMENDED way to get sandbox tools for LangGraph agents.
    Returns LangChain-compatible tools that can be passed directly to agents.
    
    Args:
        base_url: Sandbox base URL (default from AGENT_INFRA_URL env or localhost:8090)
        
    Returns:
        List of LangChain-compatible BaseTool instances
        
    Example:
        tools = await get_sandbox_tools()
        agent = create_deep_agent(
            tools=tools,
            system_prompt="You are a coding agent.",
            model=init_chat_model("openai:gpt-4"),
        )
    """
    import os
    from langchain_mcp_adapters.client import MultiServerMCPClient
    
    url = base_url or os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    
    mcp_client = MultiServerMCPClient({
        "sandbox": {
            "url": f"{url}/mcp/",
            "transport": "http"  # Use "http" transport (per langchain-mcp-adapters docs)
        },
    })
    return await mcp_client.get_tools()


def get_sandbox_tools_sync(base_url: str | None = None):
    """Get all sandbox tools via MCP (sync wrapper).
    
    Synchronous wrapper for get_sandbox_tools(). Handles cases where
    there's already an event loop running (common in CLI contexts).
    
    Args:
        base_url: Sandbox base URL
        
    Returns:
        List of LangChain-compatible BaseTool instances
    """
    import asyncio
    
    # Check if there's already an event loop running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is not None:
        # We're inside an async context, need to use nest_asyncio or run in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, get_sandbox_tools(base_url))
            return future.result()
    else:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(get_sandbox_tools(base_url))


def get_sandbox_tools_list(base_url: str | None = None) -> list[dict]:
    """List available sandbox tools via MCP (returns metadata only).
    
    Use this to see what tools are available without creating tool instances.
    
    Returns:
        List of tool definitions with name, description, and input_schema
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend(base_url=base_url)
    return backend.list_mcp_tools()


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: str | dict | None = None,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Make HTTP requests to APIs and web services.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: HTTP headers to include
        data: Request body data (string or dict)
        params: URL query parameters
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data including status, headers, and content
    """
    try:
        kwargs = {"url": url, "method": method.upper(), "timeout": timeout}

        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        if data:
            if isinstance(data, dict):
                kwargs["json"] = data
            else:
                kwargs["data"] = data

        response = requests.request(**kwargs)

        try:
            content = response.json()
        except:
            content = response.text

        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": content,
            "url": response.url,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": 0,
            "headers": {},
            "content": f"Request timed out after {timeout} seconds",
            "url": url,
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "status_code": 0,
            "headers": {},
            "content": f"Request error: {e!s}",
            "url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "headers": {},
            "content": f"Error making request: {e!s}",
            "url": url,
        }


def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Search the web using Tavily for current information and documentation.

    This tool searches the web and returns relevant results. After receiving results,
    you MUST synthesize the information into a natural, helpful response for the user.

    Args:
        query: The search query (be specific and detailed)
        max_results: Number of results to return (default: 5)
        topic: Search topic type - "general" for most queries, "news" for current events
        include_raw_content: Include full page content (warning: uses more tokens)

    Returns:
        Dictionary containing:
        - results: List of search results, each with:
            - title: Page title
            - url: Page URL
            - content: Relevant excerpt from the page
            - score: Relevance score (0-1)
        - query: The original search query

    IMPORTANT: After using this tool:
    1. Read through the 'content' field of each result
    2. Extract relevant information that answers the user's question
    3. Synthesize this into a clear, natural language response
    4. Cite sources by mentioning the page titles or URLs
    5. NEVER show the raw JSON to the user - always provide a formatted response
    """
    if tavily_client is None:
        return {
            "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable.",
            "query": query,
        }

    try:
        return tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
    except Exception as e:
        return {"error": f"Web search error: {e!s}", "query": query}


def fetch_url(url: str, timeout: int = 30) -> dict[str, Any]:
    """Fetch content from a URL and convert HTML to markdown format.

    This tool fetches web page content and converts it to clean markdown text,
    making it easy to read and process HTML content. After receiving the markdown,
    you MUST synthesize the information into a natural, helpful response for the user.

    Args:
        url: The URL to fetch (must be a valid HTTP/HTTPS URL)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dictionary containing:
        - success: Whether the request succeeded
        - url: The final URL after redirects
        - markdown_content: The page content converted to markdown
        - status_code: HTTP status code
        - content_length: Length of the markdown content in characters

    IMPORTANT: After using this tool:
    1. Read through the markdown content
    2. Extract relevant information that answers the user's question
    3. Synthesize this into a clear, natural language response
    4. NEVER show the raw markdown to the user unless specifically requested
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeepAgents/1.0)"},
        )
        response.raise_for_status()

        # Convert HTML content to markdown
        markdown_content = markdownify(response.text)

        return {
            "url": str(response.url),
            "markdown_content": markdown_content,
            "status_code": response.status_code,
            "content_length": len(markdown_content),
        }
    except Exception as e:
        return {"error": f"Fetch URL error: {e!s}", "url": url}


def crawl_tool(url: str) -> dict[str, Any]:
    """Crawl a URL and extract readable content using advanced readability extraction.
    
    This is more robust than fetch_url for article-style content:
    - Uses readability extraction (better for articles/blog posts)
    - Supports multiple backends (Jina, InfoQuest)
    - Handles PDF detection gracefully
    - Better error handling with fallbacks
    
    Args:
        url: The URL to crawl
        
    Returns:
        Dictionary containing:
        - url: The crawled URL
        - crawled_content: Extracted content in markdown format (truncated to 5000 chars)
        - is_pdf: True if URL is a PDF (which cannot be crawled)
        - error: Error message if crawling failed
        
    Note:
        Use this for articles, documentation, and blog posts.
        Use fetch_url for simpler content or when you need the full raw HTML.
    """
    import json
    import logging
    from urllib.parse import urlparse
    
    logger = logging.getLogger(__name__)
    
    # Check for PDF URLs
    parsed_url = urlparse(url)
    if parsed_url.path.lower().endswith('.pdf'):
        return {
            "url": url,
            "error": "PDF files cannot be crawled directly. Use a PDF extraction tool instead.",
            "crawled_content": None,
            "is_pdf": True,
        }
    
    try:
        # Try to import the crawler module
        from backend.src.crawler import Crawler
        
        crawler = Crawler()
        article = crawler.crawl(url)
        markdown_content = article.to_markdown()
        
        # Truncate to reasonable size for LLM context
        max_length = 5000
        if len(markdown_content) > max_length:
            markdown_content = markdown_content[:max_length] + "\n\n... [Content truncated]"
        
        return {
            "url": url,
            "crawled_content": markdown_content,
            "title": getattr(article, 'title', None),
        }
    except ImportError:
        # Crawler module not available, fall back to fetch_url
        logger.warning("Crawler module not available, falling back to fetch_url")
        result = fetch_url(url)
        if "markdown_content" in result:
            return {
                "url": url,
                "crawled_content": result["markdown_content"][:5000],
                "fallback": True,
            }
        return {"url": url, "error": "Crawler unavailable and fetch_url also failed"}
    except Exception as e:
        error_msg = f"Failed to crawl {url}: {repr(e)}"
        logger.error(error_msg)
        return {"url": url, "error": error_msg}


# =============================================================================
# Sandbox-Specific Tools
# These tools leverage the Agent-Infra sandbox capabilities
# =============================================================================

# Note: The sandbox backend is injected at runtime by the agent when these tools are used


def execute_python_code(
    code: str,
    session_id: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute Python code using the sandbox's Jupyter kernel.
    
    This provides better Python execution than shell commands:
    - Session persistence (variables survive across calls when using same session_id)
    - Rich outputs (images, dataframes, etc.)
    - Better error handling
    
    Args:
        code: Python code to execute
        session_id: Optional session ID to maintain state across calls.
                   Use the same ID to preserve variables between executions.
        timeout: Execution timeout in seconds (max 300)
        
    Returns:
        Dictionary with:
        - success: bool
        - status: 'ok', 'error', or 'timeout'
        - session_id: ID for this session (use to maintain state)
        - outputs: List of execution outputs
        - error: Error message if failed
        
    Example:
        result = execute_python_code("x = 42")
        # Later, using same session:
        result = execute_python_code("print(x)", session_id=result['session_id'])
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    return backend.execute_python(
        code=code,
        session_id=session_id,
        timeout=timeout,
    )


def execute_javascript_code(
    code: str,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute JavaScript code using the sandbox's Node.js runtime.
    
    Each request creates a fresh execution environment.
    
    Args:
        code: JavaScript code to execute
        timeout: Execution timeout in seconds (max 300)
        
    Returns:
        Dictionary with:
        - success: bool
        - status: 'ok', 'error', or 'timeout'
        - stdout: Standard output
        - stderr: Standard error
        - exit_code: Process exit code
        
    Example:
        result = execute_javascript_code("console.log('Hello from Node.js!')")
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    return backend.execute_javascript(code=code, timeout=timeout)


def take_sandbox_screenshot() -> dict[str, Any]:
    """Take a screenshot of the current sandbox display.
    
    This captures the sandbox screen, including any browsers or
    applications running inside it. Useful for:
    - Viewing web apps running in the sandbox
    - Debugging visual issues
    - Showing the user what's on the sandbox screen
    
    Returns:
        Dictionary with:
        - success: bool
        - image_bytes: PNG image bytes (if successful)
        - image_size: Size in bytes
        - error: Error message if failed
        
    Note: The image_bytes can be saved to a file or displayed to the user.
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    screenshot = backend.take_screenshot()
    if screenshot:
        return {
            "success": True,
            "image_bytes": screenshot,
            "image_size": len(screenshot),
        }
    return {"success": False, "error": "Failed to capture screenshot"}


def get_sandbox_vnc_url() -> str:
    """Get the VNC URL for accessing the sandbox browser visually.
    
    This URL opens a browser-in-browser view showing the sandbox desktop.
    Useful for:
    - Viewing web apps running in the sandbox
    - Interactive debugging
    - Showing the user how to see the sandbox
    
    Returns:
        Full VNC URL with autoconnect, e.g. 
        'http://localhost:8090/vnc/index.html?autoconnect=true'
        
    Note: The user can open this URL in their browser to see and 
    interact with the sandbox desktop.
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    return backend.get_vnc_url()


def get_sandbox_browser_info() -> dict[str, Any]:
    """Get information about the sandbox browser.
    
    Returns:
        Dictionary with browser info:
        - cdp_url: Chrome DevTools Protocol URL for Playwright/Puppeteer
        - vnc_url: VNC URL for visual browser access  
        - viewport: {width, height} of the browser viewport
        - user_agent: Browser user agent string
        
    Use this to:
    - Get the CDP URL for browser automation
    - Check the browser viewport size
    - Verify the browser is running
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    return backend.get_browser_info()


def convert_url_to_markdown(uri: str) -> str:
    """Convert a URL or file to markdown.
    
    Uses the sandbox's markitdown utility to convert web pages
    or documents to markdown format. Supports:
    - Web pages (http/https URLs)
    - PDF files
    - Word documents
    - And more
    
    Args:
        uri: URL or file path to convert
        
    Returns:
        Markdown content string
    """
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend
    backend = AgentInfraBackend()
    return backend.convert_to_markdown(uri=uri)
