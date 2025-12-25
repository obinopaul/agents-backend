# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Planner Node - Task decomposition and planning.

The planner handles:
- Breaking down complex tasks into steps
- Determining which tools/agents to use
- Creating execution plans
- Revising plans based on feedback
"""

import json
import logging
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig, default_config
from backend.src.agent_template.prompts.planner import PLANNER_SYSTEM_PROMPT
from backend.src.llms.llm import get_llm

logger = logging.getLogger(__name__)


async def planner_node(
    state: TemplateState, 
    config: RunnableConfig
) -> Command[Literal["executor", "reporter", "human_approval"]]:
    """
    Planner node - creates execution plan for complex tasks.
    
    Responsibilities:
    1. Analyze the task and available context
    2. Create a step-by-step execution plan
    3. Assign appropriate tools/methods to each step
    4. Route to executor or request human approval
    
    Args:
        state: Current workflow state
        config: Runtime configuration
        
    Returns:
        Command to update state with plan and navigate to next node
    """
    logger.info("Planner node: creating execution plan")
    
    # Get configuration
    configurable = config.get("configurable", {})
    agent_config = configurable.get("agent_config", default_config)
    
    # Get task and context
    task = state.get("task", "")
    context = state.get("context", "")
    observations = state.get("observations", [])
    plan_iterations = state.get("plan_iterations", 0)
    max_iterations = agent_config.workflow.max_plan_iterations
    
    # Check iteration limit
    if plan_iterations >= max_iterations:
        logger.warning(f"Max plan iterations ({max_iterations}) reached")
        return Command(
            update={
                "final_output": f"Unable to complete task after {max_iterations} planning attempts.",
                "is_complete": True,
            },
            goto="reporter",
        )
    
    # Get LLM for planning
    try:
        llm = get_llm()
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        return Command(
            update={
                "errors": state.get("errors", []) + [f"Planner LLM error: {str(e)}"],
                "is_complete": True,
            },
            goto="reporter",
        )
    
    # Build planning prompt
    observations_text = "\n".join(observations) if observations else "None yet"
    
    planning_prompt = f"""Create an execution plan for this task.

Task: {task}

Context: {context if context else "None provided"}

Previous Observations: {observations_text}

Create a plan with 1-5 concrete steps. For each step, specify:
- description: What to do
- method: "tool" (use external tool), "reasoning" (think/analyze), or "code" (write/run code)
- tool_name: If method is "tool", which tool to use (optional)

Respond with valid JSON:
{{
    "reasoning": "Brief explanation of your approach",
    "steps": [
        {{"step": 1, "description": "...", "method": "tool", "tool_name": "web_search"}},
        {{"step": 2, "description": "...", "method": "reasoning"}},
        ...
    ]
}}"""
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": planning_prompt},
        ])
        
        # Parse plan from response
        plan = _parse_plan(response.content)
        
        if not plan or not plan.get("steps"):
            logger.warning("Failed to parse plan, using default")
            plan = {
                "reasoning": "Proceeding with direct analysis",
                "steps": [
                    {"step": 1, "description": "Analyze and respond to the task", "method": "reasoning"}
                ]
            }
        
        logger.info(f"Created plan with {len(plan.get('steps', []))} steps")
        
        # Check if human approval is needed
        auto_approve = state.get("auto_approve", agent_config.workflow.auto_approve_plans)
        
        if not auto_approve:
            return Command(
                update={
                    "plan": plan,
                    "plan_iterations": plan_iterations + 1,
                    "needs_human_approval": True,
                    "current_step": 0,
                },
                goto="human_approval",
            )
        
        # Auto-approved, go to executor
        return Command(
            update={
                "plan": plan,
                "plan_iterations": plan_iterations + 1,
                "current_step": 0,
                "messages": state.get("messages", []) + [
                    AIMessage(content=f"Plan created: {plan.get('reasoning', '')}")
                ],
            },
            goto="executor",
        )
        
    except Exception as e:
        logger.error(f"Planner error: {e}")
        return Command(
            update={
                "errors": state.get("errors", []) + [f"Planner error: {str(e)}"],
                "plan_iterations": plan_iterations + 1,
            },
            goto="reporter",
        )


def _parse_plan(content: str) -> Dict[str, Any]:
    """Parse plan JSON from LLM response."""
    try:
        # Try to extract JSON from response
        content = content.strip()
        
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse plan JSON: {e}")
        return {}
