"""Podcast Generation Workflow.

This module provides an async workflow for generating podcasts from text content
using AI-powered script writing and text-to-speech synthesis.
"""
import logging
from typing import AsyncGenerator, Optional

from backend.src.config.configuration import get_recursion_limit
from backend.src.module.podcast.graph.builder import graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def run_podcast_workflow_async(
    input_content: str,
    debug: bool = False,
) -> AsyncGenerator[dict, None]:
    """Run the podcast generation workflow asynchronously.

    Args:
        input_content: The text content to convert to a podcast
        debug: If True, enables debug level logging

    Yields:
        State updates from the workflow

    Returns:
        The final state containing the generated audio
    """
    if not input_content:
        raise ValueError("Input content cannot be empty")

    if debug:
        logging.getLogger("backend.src.module.podcast").setLevel(logging.DEBUG)

    logger.info("Starting podcast generation workflow")

    initial_state = {
        "input": input_content,
        "messages": [],
    }

    config = {
        "configurable": {
            "thread_id": "podcast-workflow",
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
        logger.info("Podcast generation completed successfully")


async def run_podcast_workflow(
    input_content: str,
    debug: bool = False,
) -> dict:
    """Run the podcast generation workflow and return the final state.

    Args:
        input_content: The text content to convert to a podcast
        debug: If True, enables debug level logging

    Returns:
        The final state containing:
        - output: bytes - The generated audio data
        - script: Script - The generated podcast script
    """
    final_state = None
    async for state in run_podcast_workflow_async(input_content, debug):
        final_state = state
    return final_state


def run_podcast_workflow_sync(
    input_content: str,
    debug: bool = False,
) -> dict:
    """Run the podcast generation workflow synchronously.

    Args:
        input_content: The text content to convert to a podcast
        debug: If True, enables debug level logging

    Returns:
        The final state containing the generated audio
    """
    import asyncio
    return asyncio.run(run_podcast_workflow(input_content, debug))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example usage
    sample_content = """
    # Introduction to Machine Learning
    
    Machine learning is a subset of artificial intelligence that enables
    computers to learn from data without being explicitly programmed.
    """
    
    result = run_podcast_workflow_sync(sample_content)
    
    # Save the output audio
    if result and result.get("output"):
        with open("podcast_output.mp3", "wb") as f:
            f.write(result["output"])
        print("Podcast saved to podcast_output.mp3")
