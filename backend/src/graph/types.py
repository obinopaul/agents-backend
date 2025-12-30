
from dataclasses import field
from typing import Optional, List

from langgraph.graph import MessagesState


from backend.src.rag import Resource



class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Runtime Variables
    resources: list[Resource] = []
    
    # Background investigation
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    
    # Human feedback / HITL control
    needs_human_feedback: bool = False  # Set by agent when it needs clarification
    hitl_questions: Optional[List[str]] = None  # Structured questions for HITL UI
    
    # Workflow control
    goto: str = "base"  # Default next node
