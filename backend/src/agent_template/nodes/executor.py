# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Executor Node - Step execution with tools and reasoning.

The executor handles:
- Tool invocation (MCP, sandbox)
- Code execution
- Reasoning steps
- Collecting results
"""

import logging
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig, default_config
from backend.src.agent_template.prompts.executor import EXECUTOR_SYSTEM_PROMPT
from backend.src.llms.llm import get_llm

logger = logging.getLogger(__name__)


async def executor_node(
    state: TemplateState, 
    config: RunnableConfig
) -> Command[Literal["executor", "reviewer", "planner"]]:
    """
    Executor node - executes steps from the plan.
    
    Responsibilities:
    1. Get the current step from the plan
    2. Execute it (tool call, reasoning, or code)
    3. Store results
    4. Move to next step or finish
    
    Args:
        state: Current workflow state
        config: Runtime configuration
        
    Returns:
        Command to update state and navigate to next node
    """
    logger.info("Executor node: executing current step")
    
    # Get configuration
    configurable = config.get("configurable", {})
    agent_config = configurable.get("agent_config", default_config)
    
    # Get plan and current step
    plan = state.get("plan", {})
    current_step_idx = state.get("current_step", 0)
    step_results = state.get("step_results", [])
    task = state.get("task", "")
    
    if not plan or not plan.get("steps"):
        logger.warning("No plan available, going to reporter")
        return Command(
            update={"is_complete": True},
            goto="reviewer",
        )
    
    steps = plan.get("steps", [])
    
    # Check if all steps are done
    if current_step_idx >= len(steps):
        logger.info("All steps complete, going to reviewer")
        return Command(
            update={"is_complete": True},
            goto="reviewer",
        )
    
    # Get current step
    current_step = steps[current_step_idx]
    step_description = current_step.get("description", "Execute step")
    step_method = current_step.get("method", "reasoning")
    tool_name = current_step.get("tool_name")
    
    logger.info(f"Executing step {current_step_idx + 1}/{len(steps)}: {step_description}")
    
    # Get LLM
    try:
        llm = get_llm()
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        return Command(
            update={
                "errors": state.get("errors", []) + [f"Executor LLM error: {str(e)}"],
            },
            goto="reviewer",
        )
    
    # Execute based on method
    try:
        if step_method == "tool" and tool_name:
            # Tool execution - for now, simulate with reasoning
            # TODO: Integrate with tool_server and sandbox
            result = await _execute_tool_step(llm, task, step_description, tool_name, step_results)
        elif step_method == "code":
            # Code execution - for now, simulate with reasoning
            # TODO: Integrate with sandbox
            result = await _execute_code_step(llm, task, step_description, step_results)
        else:
            # Reasoning step
            result = await _execute_reasoning_step(llm, task, step_description, step_results)
        
        # Store result
        step_result = {
            "step": current_step_idx + 1,
            "description": step_description,
            "method": step_method,
            "result": result,
        }
        
        new_results = step_results + [step_result]
        observations = state.get("observations", []) + [result]
        
        # Move to next step or finish
        next_step = current_step_idx + 1
        
        if next_step >= len(steps):
            # All steps done
            return Command(
                update={
                    "step_results": new_results,
                    "observations": observations,
                    "current_step": next_step,
                    "is_complete": True,
                    "messages": state.get("messages", []) + [
                        AIMessage(content=f"Step {current_step_idx + 1} complete: {result[:200]}...")
                    ],
                },
                goto="reviewer",
            )
        else:
            # Continue to next step
            return Command(
                update={
                    "step_results": new_results,
                    "observations": observations,
                    "current_step": next_step,
                },
                goto="executor",
            )
            
    except Exception as e:
        logger.error(f"Executor error on step {current_step_idx + 1}: {e}")
        
        # Try to continue with next step
        return Command(
            update={
                "errors": state.get("errors", []) + [f"Step {current_step_idx + 1} error: {str(e)}"],
                "current_step": current_step_idx + 1,
            },
            goto="executor" if current_step_idx + 1 < len(steps) else "reviewer",
        )


async def _execute_reasoning_step(llm, task: str, step_description: str, previous_results: List[Dict]) -> str:
    """Execute a reasoning step."""
    context = "\n".join([f"- {r.get('result', '')[:500]}" for r in previous_results]) if previous_results else "None yet"
    
    prompt = f"""Complete this reasoning step for the task.

Task: {task}

Current Step: {step_description}

Previous Results:
{context}

Provide a thorough, well-reasoned response for this step:"""
    
    response = await llm.ainvoke([
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    
    return response.content


async def _execute_tool_step(llm, task: str, step_description: str, tool_name: str, previous_results: List[Dict]) -> str:
    """Execute a tool step (placeholder for tool integration)."""
    # TODO: Integrate with tool_server
    # For now, simulate tool execution with reasoning
    
    context = "\n".join([f"- {r.get('result', '')[:500]}" for r in previous_results]) if previous_results else "None yet"
    
    prompt = f"""Simulate the execution of tool '{tool_name}' for this step.

Task: {task}

Current Step: {step_description}

Tool to use: {tool_name}

Previous Results:
{context}

Describe what the tool would return and provide the result:"""
    
    response = await llm.ainvoke([
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    
    return f"[Tool: {tool_name}] {response.content}"


async def _execute_code_step(llm, task: str, step_description: str, previous_results: List[Dict]) -> str:
    """Execute a code step (placeholder for sandbox integration)."""
    # TODO: Integrate with sandbox
    # For now, simulate code execution with reasoning
    
    context = "\n".join([f"- {r.get('result', '')[:500]}" for r in previous_results]) if previous_results else "None yet"
    
    prompt = f"""Write and simulate executing code for this step.

Task: {task}

Current Step: {step_description}

Previous Results:
{context}

Write the code and describe the expected output:"""
    
    response = await llm.ainvoke([
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    
    return f"[Code Execution] {response.content}"
