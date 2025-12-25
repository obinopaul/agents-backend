"""Prose Writing Workflow.

This module provides an async workflow for AI-powered prose writing operations
including continue, improve, shorten, lengthen, fix, and zap options.
"""
import logging
from typing import AsyncGenerator, Literal, Optional

from backend.src.config.configuration import get_recursion_limit
from backend.src.module.prose.graph.builder import graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

ProseOption = Literal["continue", "improve", "shorter", "longer", "fix", "zap"]


async def run_prose_workflow_async(
    content: str,
    option: ProseOption,
    command: str = "",
    debug: bool = False,
) -> AsyncGenerator[dict, None]:
    """Run the prose writing workflow asynchronously.

    Args:
        content: The text content to process
        option: The prose operation to perform
            - "continue": Continue writing the text
            - "improve": Improve the text quality
            - "shorter": Make the text shorter
            - "longer": Make the text longer
            - "fix": Fix grammar and spelling
            - "zap": Remove unnecessary content
        command: Optional custom command for the operation
        debug: If True, enables debug level logging

    Yields:
        State updates from the workflow

    Returns:
        The final state containing the processed text
    """
    if not content:
        raise ValueError("Content cannot be empty")

    valid_options = {"continue", "improve", "shorter", "longer", "fix", "zap"}
    if option not in valid_options:
        raise ValueError(f"Invalid option: {option}. Must be one of {valid_options}")

    if debug:
        logging.getLogger("backend.src.module.prose").setLevel(logging.DEBUG)

    logger.info(f"Starting prose workflow with option: {option}")

    initial_state = {
        "content": content,
        "option": option,
        "command": command,
        "messages": [],
    }

    config = {
        "configurable": {
            "thread_id": "prose-workflow",
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
        logger.info("Prose workflow completed successfully")


async def run_prose_workflow(
    content: str,
    option: ProseOption,
    command: str = "",
    debug: bool = False,
) -> dict:
    """Run the prose writing workflow and return the final state.

    Args:
        content: The text content to process
        option: The prose operation to perform
        command: Optional custom command for the operation
        debug: If True, enables debug level logging

    Returns:
        The final state containing the processed text
    """
    final_state = None
    async for state in run_prose_workflow_async(content, option, command, debug):
        final_state = state
    return final_state


def run_prose_workflow_sync(
    content: str,
    option: ProseOption,
    command: str = "",
    debug: bool = False,
) -> dict:
    """Run the prose writing workflow synchronously.

    Args:
        content: The text content to process
        option: The prose operation to perform
        command: Optional custom command for the operation
        debug: If True, enables debug level logging

    Returns:
        The final state containing the processed text
    """
    import asyncio
    return asyncio.run(run_prose_workflow(content, option, command, debug))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example usage
    sample_content = "The weather in Beijing is sunny today."
    
    result = run_prose_workflow_sync(sample_content, "continue")
    print(f"Result: {result.get('output')}")
