
from dataclasses import field

from langgraph.graph import MessagesState


from backend.src.rag import Resource



class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Runtime Variables
    locale: str = "en-US"
    research_topic: str = ""
    observations: list[str] = []
    resources: list[Resource] = []
    
    # Background investigation
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    
    # Human feedback
    feedback: str = ""

    # Workflow control
    goto: str = "base"  # Default next node
