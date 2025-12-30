# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
State definition for the multi-agent template.

The TemplateState extends LangGraph's MessagesState with fields for:
- Task management (input, plan, results)
- Workflow control (current_node, iteration tracking)
- Configuration flags (enable features, limits)
"""

from dataclasses import field
from typing import Any, Dict, List, Optional

from langgraph.graph import MessagesState


class TemplateState(MessagesState):
    """
    Configurable state for the multi-agent template.
    
    Extends MessagesState to include conversation history automatically.
    All fields have sensible defaults for easy initialization.
    """
    
    # -------------------------------------------------------------------------
    # Input Fields
    # -------------------------------------------------------------------------
    task: str = ""  # The main task/query to process
    context: str = ""  # Additional context for the task
    
    # -------------------------------------------------------------------------
    # Plan & Execution State
    # -------------------------------------------------------------------------
    plan: Optional[Dict[str, Any]] = None  # Current execution plan
    plan_iterations: int = 0  # Number of planning iterations
    current_step: int = 0  # Current step in the plan
    step_results: List[Dict[str, Any]] = field(default_factory=list)  # Results from each step
    
    # -------------------------------------------------------------------------
    # Agent Memory
    # -------------------------------------------------------------------------
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # History of tool calls
    errors: List[str] = field(default_factory=list)  # Errors encountered
    
    # -------------------------------------------------------------------------
    # Output Fields
    # -------------------------------------------------------------------------
    final_output: str = ""  # Final result/report
    artifacts: List[str] = field(default_factory=list)  # Generated files/artifacts
    
    # -------------------------------------------------------------------------
    # Workflow Control
    # -------------------------------------------------------------------------
    goto: str = "coordinator"  # Next node to execute
    is_complete: bool = False  # Whether workflow is complete
    needs_human_approval: bool = False  # Waiting for human approval
    
    # -------------------------------------------------------------------------
    # Configuration Flags (can be set at runtime)
    # -------------------------------------------------------------------------
    max_iterations: int = 10  # Maximum planning iterations
    max_steps: int = 5  # Maximum steps per plan
    enable_tools: bool = True  # Enable tool usage
    enable_sandbox: bool = False  # Enable sandbox execution
    enable_review: bool = True  # Enable reviewer node
    auto_approve: bool = True  # Auto-approve plans (skip human node)
    
    # -------------------------------------------------------------------------
    # MCP & Tool Configuration
    # -------------------------------------------------------------------------
    mcp_servers: Dict[str, Any] = field(default_factory=dict)  # MCP server configs
    enabled_tools: List[str] = field(default_factory=list)  # Allowed tool names
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    session_id: str = ""  # Session identifier
    user_id: str = ""  # User identifier
    started_at: str = ""  # Workflow start time
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
