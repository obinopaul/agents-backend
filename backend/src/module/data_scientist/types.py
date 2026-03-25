"""
State Types.

This module defines the state for the DS* multi-agent architecture.
Follows the simple pattern from types.py - extends MessagesState with minimal fields.
"""

from typing import List, Literal, Optional
from enum import Enum

from langgraph.graph import MessagesState


# =============================================================================
# Enums for Routing
# =============================================================================

class VerificationStatus(str, Enum):
    """Status returned by the Verifier agent."""
    PENDING = "pending"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


# =============================================================================
# DS* State - Extends MessagesState
# =============================================================================

class State(MessagesState):
    """
    State for the DS* agent system, extends MessagesState.
    
    Keeps it simple - messages contain all conversation history including
    user queries, AI responses, and tool calls/results.
    
    No need for separate query field - the user's question is in messages.
    Configuration (like iterations) comes from the Configuration class.
    """
    
    # Human feedback / HITL control
    needs_human_feedback: bool = False  # Set by agent when it needs clarification
    hitl_questions: Optional[List[str]] = None  # Structured questions for HITL UI
    
    # Workflow control - where to go next
    goto: str = "analyzer"  # Default starting node
    
    # Verification status (set by verifier)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    
    # Workflow iteration counter (planner→coder→executor→verifier loop)
    # Increments each time verifier routes back to planner (INSUFFICIENT)
    # Resets to 0 when a new workflow cycle starts
    workflow_iteration_count: int = 0
    
    # Resources for RAG (user will fix this)
    resources: List[str] = []

