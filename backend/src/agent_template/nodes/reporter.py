# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Reporter Node - Final output generation.

The reporter handles:
- Synthesizing all results
- Generating final output/report
- Formatting the response
"""

import logging
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig, default_config
from backend.src.agent_template.prompts.reporter import REPORTER_SYSTEM_PROMPT
from backend.src.llms.llm import get_llm_by_type

logger = logging.getLogger(__name__)


async def reporter_node(
    state: TemplateState, 
    config: RunnableConfig
) -> Command[Literal["__end__"]]:
    """
    Reporter node - generates final output.
    
    Responsibilities:
    1. Synthesize all step results and observations
    2. Generate a coherent final response
    3. Format appropriately for the task type
    
    Args:
        state: Current workflow state
        config: Runtime configuration
        
    Returns:
        Command to update state with final output and end workflow
    """
    logger.info("Reporter node: generating final output")
    
    # Get task and results
    task = state.get("task", "")
    step_results = state.get("step_results", [])
    observations = state.get("observations", [])
    errors = state.get("errors", [])
    locale = state.get("locale", "en-US")
    
    # If already have final output, just end
    if state.get("final_output"):
        return Command(
            update={"is_complete": True},
            goto="__end__",
        )
    
    # Get LLM for report generation
    try:
        llm = get_llm_by_type("basic")
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        # Fallback to simple summary
        fallback_output = _generate_fallback_output(task, step_results, errors)
        return Command(
            update={
                "final_output": fallback_output,
                "is_complete": True,
                "messages": state.get("messages", []) + [AIMessage(content=fallback_output)],
            },
            goto="__end__",
        )
    
    # Build report prompt
    results_text = "\n\n".join([
        f"### Step {r.get('step')}: {r.get('description')}\n{r.get('result', '')}"
        for r in step_results
    ]) if step_results else "No execution results available."
    
    observations_text = "\n".join([f"- {obs}" for obs in observations]) if observations else "None"
    errors_text = "\n".join([f"- {err}" for err in errors]) if errors else "None"
    
    report_prompt = f"""Generate a comprehensive final response for this task.

## Task
{task}

## Execution Results
{results_text}

## Observations
{observations_text}

## Errors Encountered
{errors_text}

## Instructions
Create a well-structured, helpful response that:
1. Directly addresses the original task
2. Synthesizes the key findings from execution
3. Is clear and actionable
4. Uses appropriate formatting (markdown if helpful)

Locale: {locale}

Generate the final response:"""
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": REPORTER_SYSTEM_PROMPT},
            {"role": "user", "content": report_prompt},
        ])
        
        final_output = response.content
        logger.info(f"Generated final output: {len(final_output)} chars")
        
        return Command(
            update={
                "final_output": final_output,
                "is_complete": True,
                "messages": state.get("messages", []) + [AIMessage(content=final_output)],
            },
            goto="__end__",
        )
        
    except Exception as e:
        logger.error(f"Reporter error: {e}")
        fallback_output = _generate_fallback_output(task, step_results, errors)
        return Command(
            update={
                "final_output": fallback_output,
                "is_complete": True,
                "errors": errors + [f"Reporter error: {str(e)}"],
            },
            goto="__end__",
        )


def _generate_fallback_output(task: str, step_results: list, errors: list) -> str:
    """Generate a fallback output when LLM fails."""
    output_parts = [f"# Task: {task}\n"]
    
    if step_results:
        output_parts.append("## Results\n")
        for r in step_results:
            output_parts.append(f"- **Step {r.get('step')}**: {r.get('result', 'No result')[:500]}\n")
    
    if errors:
        output_parts.append("\n## Errors Encountered\n")
        for err in errors:
            output_parts.append(f"- {err}\n")
    
    if not step_results:
        output_parts.append("\nUnable to complete the task. Please try again or provide more details.")
    
    return "\n".join(output_parts)
