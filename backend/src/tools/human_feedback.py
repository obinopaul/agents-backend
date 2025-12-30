"""Human in the Loop (HITL) Tool.

This tool allows the agent to request human input when needed.
The tool is intentionally simple - it just signals that human input is needed
and passes the question(s) to ask. The structured HITL logic (approve/edit/reject
decisions) is handled by the human_feedback_node.

Design Philosophy:
- Tool: Simple trigger that passes what to ask the user
- Node: Contains structured decision logic (approve/edit/reject)
- This separation keeps the agent's task simple while allowing rich HITL UX
"""

from typing import Annotated, List, Optional

from langchain_core.tools import tool


# Marker used to detect HITL requests in the message stream
HITL_TOOL_MARKER = "[HITL_REQUEST]"


@tool
def request_human_input(
    questions: Annotated[
        List[str],
        "List of questions or prompts to present to the user. Each question will be displayed for human review."
    ],
) -> str:
    """
    Request input from the human user.
    
    Use this tool when you need clarification, confirmation, or additional
    information from the user to complete your task.
    
    When to use:
    - You need clarification on ambiguous requirements
    - You want confirmation before taking an important action
    - You need the user to choose between options
    - You're missing information needed to complete the task
    
    When NOT to use:
    - You have enough information to complete the task
    - The decision is routine and doesn't need approval
    - You're just making progress on a clear task and want to communicate to the user
    
    The user will be able to:
    - Approve: Accept your work as-is
    - Edit: Provide modifications or corrections
    - Reject: Decline with feedback for you to try again
    
    Args:
        questions: List of questions to ask the user. Can be one or more.
                  Examples:
                  - ["What file format do you prefer for the report?"]
                  - ["Do you want me to proceed with this approach?", 
                     "Should I include additional sections?"]
    
    Returns:
        A marker string indicating HITL was requested. The actual response
        will come through the human_feedback_node interrupt.
    """
    import json
    
    # Return structured marker that the node can parse
    return f"{HITL_TOOL_MARKER}{json.dumps({'questions': questions})}"


# Alias for cleaner imports
human_feedback_tool = request_human_input

