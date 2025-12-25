"""Prompt Enhancer Workflow.

This module provides an async workflow for enhancing user prompts
using AI-powered analysis to make them more effective and specific.
"""
import logging
from typing import AsyncGenerator, Optional

from backend.src.config.configuration import get_recursion_limit
from backend.src.module.prompt_enhancer.graph.builder import graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def run_prompt_enhancer_workflow_async(
    prompt: str,
    context: Optional[str] = None,
    locale: str = "en-US",
    debug: bool = False,
) -> AsyncGenerator[dict, None]:
    """Run the prompt enhancer workflow asynchronously.

    Args:
        prompt: The original prompt to enhance
        context: Optional additional context for enhancement
        locale: Locale for the output (default: "en-US")
        debug: If True, enables debug level logging

    Yields:
        State updates from the workflow

    Returns:
        The final state containing the enhanced prompt
    """
    if not prompt:
        raise ValueError("Prompt cannot be empty")

    if debug:
        logging.getLogger("backend.src.module.prompt_enhancer").setLevel(logging.DEBUG)

    logger.info("Starting prompt enhancement workflow")

    initial_state = {
        "prompt": prompt,
        "context": context,
        "locale": locale,
    }

    config = {
        "configurable": {
            "thread_id": "prompt-enhancer-workflow",
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
        logger.info("Prompt enhancement completed successfully")


async def run_prompt_enhancer_workflow(
    prompt: str,
    context: Optional[str] = None,
    locale: str = "en-US",
    debug: bool = False,
) -> dict:
    """Run the prompt enhancer workflow and return the final state.

    Args:
        prompt: The original prompt to enhance
        context: Optional additional context for enhancement
        locale: Locale for the output (default: "en-US")
        debug: If True, enables debug level logging

    Returns:
        The final state containing the enhanced prompt
    """
    final_state = None
    async for state in run_prompt_enhancer_workflow_async(prompt, context, locale, debug):
        final_state = state
    return final_state


def run_prompt_enhancer_workflow_sync(
    prompt: str,
    context: Optional[str] = None,
    locale: str = "en-US",
    debug: bool = False,
) -> dict:
    """Run the prompt enhancer workflow synchronously.

    Args:
        prompt: The original prompt to enhance
        context: Optional additional context for enhancement
        locale: Locale for the output (default: "en-US")
        debug: If True, enables debug level logging

    Returns:
        The final state containing the enhanced prompt
    """
    import asyncio
    return asyncio.run(run_prompt_enhancer_workflow(prompt, context, locale, debug))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example usage
    sample_prompt = "Write about AI"
    
    result = run_prompt_enhancer_workflow_sync(sample_prompt)
    print(f"Enhanced prompt: {result.get('output')}")
