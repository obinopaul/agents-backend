"""PPT Generation Workflow.

This module provides an async workflow for generating PowerPoint presentations
from text content using AI-powered composition and Marp CLI generation.
"""
import logging
from typing import AsyncGenerator, Optional

from langfuse.langchain import CallbackHandler

from backend.src.config.configuration import get_recursion_limit
from backend.src.module.ppt.graph.builder import graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def run_ppt_workflow_async(
    input_content: str,
    locale: str = "en-US",
    debug: bool = False,
) -> AsyncGenerator[dict, None]:
    """Run the PPT generation workflow asynchronously.

    Args:
        input_content: The text content to convert to a presentation
        locale: Locale for the presentation (default: "en-US")
        debug: If True, enables debug level logging

    Yields:
        State updates from the workflow

    Returns:
        The final state containing the generated PPT file path
    """
    if not input_content:
        raise ValueError("Input content cannot be empty")

    if debug:
        logging.getLogger("backend.src.module.ppt").setLevel(logging.DEBUG)

    logger.info(f"Starting PPT generation workflow for locale: {locale}")

    initial_state = {
        "input": input_content,
        "locale": locale,
        "messages": [],
    }

    config = {
        "configurable": {
            "thread_id": "ppt-workflow",
        },
        "recursion_limit": get_recursion_limit(default=50),
    }

    final_state = None
    async for state in graph.astream(
        input=initial_state, config=config, stream_mode="values"
    ):
        final_state = state
        yield state

    if final_state:
        logger.info(f"PPT generation completed: {final_state.get('generated_file_path')}")
    
    return final_state


async def run_ppt_workflow(
    input_content: str,
    locale: str = "en-US",
    debug: bool = False,
) -> dict:
    """Run the PPT generation workflow and return the final state.

    Args:
        input_content: The text content to convert to a presentation
        locale: Locale for the presentation (default: "en-US")
        debug: If True, enables debug level logging

    Returns:
        The final state containing the generated PPT file path
    """
    final_state = None
    async for state in run_ppt_workflow_async(input_content, locale, debug):
        final_state = state
    return final_state


def run_ppt_workflow_sync(
    input_content: str,
    locale: str = "en-US",
    debug: bool = False,
) -> dict:
    """Run the PPT generation workflow synchronously.

    Args:
        input_content: The text content to convert to a presentation
        locale: Locale for the presentation (default: "en-US")
        debug: If True, enables debug level logging

    Returns:
        The final state containing the generated PPT file path
    """
    import asyncio
    return asyncio.run(run_ppt_workflow(input_content, locale, debug))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example usage
    sample_content = """
    # Introduction to AI
    
    Artificial Intelligence (AI) is transforming industries worldwide.
    
    ## Key Topics
    - Machine Learning
    - Deep Learning
    - Natural Language Processing
    """
    
    result = run_ppt_workflow_sync(sample_content)
    print(f"Generated PPT: {result.get('generated_file_path')}")
