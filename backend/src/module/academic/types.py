
from dataclasses import field
from typing import Optional, List

from langgraph.graph import MessagesState


class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""
    
    # Human feedback / HITL control
    needs_human_feedback: bool = False  # Set by agent when it needs clarification
    hitl_questions: Optional[List[str]] = None  # Structured questions for HITL UI
    resources: Optional[List[str]] = None  # Resources for the agent to use
    
    # Workflow control
    goto: str = "base"  # Default next node
