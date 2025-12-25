# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Coordinator Node - Entry point and routing logic.

The coordinator handles:
- Initial task analysis
- Routing to appropriate nodes
- Direct responses for simple queries
- Clarification requests
"""

import logging
from typing import Any, Dict, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.agent_template.state import TemplateState
from backend.src.agent_template.config import AgentConfig, default_config
from backend.src.agent_template.prompts.coordinator import COORDINATOR_SYSTEM_PROMPT
from backend.src.llms.llm import get_llm

logger = logging.getLogger(__name__)


async def coordinator_node(
    state: TemplateState, 
    config: RunnableConfig
) -> Command[Literal["planner", "reporter", "__end__"]]:
    """
    Coordinator node - analyzes task and routes to appropriate next node.
    
    Responsibilities:
    1. Analyze the incoming task
    2. Determine if it needs planning (complex) or direct response (simple)
    3. Route to planner for complex tasks
    4. Route to reporter for direct responses
    
    Args:
        state: Current workflow state
        config: Runtime configuration
        
    Returns:
        Command to update state and navigate to next node
    """
    logger.info("Coordinator node: analyzing task")
    
    # Get configuration
    configurable = config.get("configurable", {})
    agent_config = configurable.get("agent_config", default_config)
    
    # Get task from state
    task = state.get("task", "")
    messages = state.get("messages", [])
    
    # If no task but has messages, extract from last user message
    if not task and messages:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
                task = msg.content if hasattr(msg, "content") else str(msg)
                break
    
    if not task:
        logger.warning("Coordinator: No task provided")
        return Command(
            update={
                "final_output": "No task provided. Please specify what you'd like me to help with.",
                "is_complete": True,
            },
            goto="__end__",
        )
    
    # Get LLM for analysis
    try:
        llm = get_llm()
    except Exception as e:
        logger.error(f"Failed to get LLM: {e}")
        # Fallback: assume complex task
        return Command(
            update={
                "task": task,
                "goto": "planner",
            },
            goto="planner",
        )
    
    # Analyze task complexity
    analysis_prompt = f"""Analyze this task and determine the best approach:

Task: {task}

Respond with exactly one of:
- PLAN: if the task requires multiple steps, research, or complex reasoning
- DIRECT: if it's a simple question that can be answered immediately
- CLARIFY: if the task is ambiguous and needs clarification

Your response (one word only):"""
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": COORDINATOR_SYSTEM_PROMPT},
            {"role": "user", "content": analysis_prompt},
        ])
        
        decision = response.content.strip().upper()
        logger.info(f"Coordinator decision: {decision}")
        
        if "DIRECT" in decision:
            # Simple task - generate direct response
            direct_prompt = f"""Provide a helpful, concise response to this request:

Task: {task}

Response:"""
            
            direct_response = await llm.ainvoke([
                {"role": "system", "content": "You are a helpful assistant. Provide clear, concise answers."},
                {"role": "user", "content": direct_prompt},
            ])
            
            return Command(
                update={
                    "task": task,
                    "final_output": direct_response.content,
                    "is_complete": True,
                    "messages": messages + [AIMessage(content=direct_response.content)],
                },
                goto="__end__",
            )
        
        elif "CLARIFY" in decision:
            # Need clarification - for now, proceed to planner anyway
            # TODO: Implement clarification flow
            pass
        
        # Default: Complex task - go to planner
        return Command(
            update={
                "task": task,
                "goto": "planner",
            },
            goto="planner",
        )
        
    except Exception as e:
        logger.error(f"Coordinator error: {e}")
        # On error, default to planner
        return Command(
            update={
                "task": task,
                "errors": state.get("errors", []) + [f"Coordinator error: {str(e)}"],
                "goto": "planner",
            },
            goto="planner",
        )
