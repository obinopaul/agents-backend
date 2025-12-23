# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Reviewer Node - Output validation and quality assurance.

The reviewer handles:
- Validating execution results
- Checking for completeness
- Identifying issues
- Deciding to replan or proceed
"""

import logging
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig, default_config
from backend.src.agent_template.prompts.reviewer import REVIEWER_SYSTEM_PROMPT
from backend.src.llms.llm import get_llm_by_type

logger = logging.getLogger(__name__)


async def reviewer_node(
    state: TemplateState, 
    config: RunnableConfig
) -> Command[Literal["planner", "reporter"]]:
    """
    Reviewer node - validates execution results.
    
    Responsibilities:
    1. Review all step results
    2. Check if task was adequately addressed
    3. Identify any gaps or issues
    4. Decide to replan (if issues) or proceed to reporter
    
    Args:
        state: Current workflow state
        config: Runtime configuration
        
    Returns:
        Command to update state and navigate to next node
    """
    logger.info("Reviewer node: validating results")
    
    # Get configuration
    configurable = config.get("configurable", {})
    agent_config = configurable.get("agent_config", default_config)
    
    # Check if review is enabled
    enable_review = state.get("enable_review", agent_config.workflow.enable_review)
    if not enable_review:
        logger.info("Review disabled, proceeding to reporter")
        return Command(goto="reporter")
    
    # Get task and results
    task = state.get("task", "")
    step_results = state.get("step_results", [])
    observations = state.get("observations", [])
    plan_iterations = state.get("plan_iterations", 0)
    max_iterations = agent_config.workflow.max_plan_iterations
    
    # If no results, go to reporter
    if not step_results:
        logger.warning("No results to review, proceeding to reporter")
        return Command(
            update={"observations": observations + ["Review: No results to verify"]},
            goto="reporter",
        )
    
    # Get LLM for review
    try:
        llm = get_llm_by_type("basic")
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        return Command(goto="reporter")
    
    # Build review prompt
    results_text = "\n".join([
        f"Step {r.get('step')}: {r.get('description')}\nResult: {r.get('result', '')[:1000]}"
        for r in step_results
    ])
    
    review_prompt = f"""Review the execution results for this task.

Task: {task}

Execution Results:
{results_text}

Evaluate the results and respond with exactly one of:
- COMPLETE: if the task was adequately addressed and results are satisfactory
- REPLAN: if there are significant gaps that require replanning
- PARTIAL: if results are incomplete but usable

Also provide a brief explanation.

Format:
DECISION: [COMPLETE/REPLAN/PARTIAL]
EXPLANATION: [Your explanation]"""
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": review_prompt},
        ])
        
        content = response.content.strip()
        
        # Parse decision
        decision = "COMPLETE"
        if "REPLAN" in content.upper():
            decision = "REPLAN"
        elif "PARTIAL" in content.upper():
            decision = "PARTIAL"
        
        logger.info(f"Reviewer decision: {decision}")
        
        # Handle decision
        if decision == "REPLAN" and plan_iterations < max_iterations:
            # Need to replan
            logger.info("Replanning required")
            return Command(
                update={
                    "observations": observations + [f"Review: Replanning required - {content[:500]}"],
                    "messages": state.get("messages", []) + [
                        AIMessage(content=f"Review: Need to replan - {content[:200]}...")
                    ],
                },
                goto="planner",
            )
        
        # Complete or Partial - proceed to reporter
        return Command(
            update={
                "observations": observations + [f"Review: {decision} - {content[:500]}"],
            },
            goto="reporter",
        )
        
    except Exception as e:
        logger.error(f"Reviewer error: {e}")
        return Command(
            update={
                "errors": state.get("errors", []) + [f"Reviewer error: {str(e)}"],
            },
            goto="reporter",
        )
