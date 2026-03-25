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
    Request input from the human user. ONLY use this as an ABSOLUTE LAST RESORT.
    
    You should almost NEVER call this tool. Complete the task using your own
    judgment and the other tools available to you.
    
    When to use (VERY RARE — all conditions must be true):
    - You have ALREADY attempted the task and encountered an unresolvable blocker
    - The missing information CANNOT be inferred, guessed, or found via other tools
    - WITHOUT this specific information, the task literally cannot proceed at all
    - You have NOT already asked the user in this conversation
    
    When NOT to use (MOST situations):
    - You have enough information to complete the task — just do it
    - You want confirmation before taking an action — just take the action
    - You want the user to choose between options — pick the best one yourself
    - You want to communicate progress — just continue working
    - The task description is slightly ambiguous — use your best judgment
    - You already asked the user once — do NOT ask again, use what you have
    
    IMPORTANT: Calling this tool pauses the entire workflow and forces the user
    to respond. It is disruptive. Prefer action over asking.
    
    Args:
        questions: List of questions to ask the user (keep to 1-2 max).
    
    Returns:
        A marker string indicating HITL was requested. The actual response
        will come through the human_feedback_node interrupt.
    """
    import json
    
    # Return structured marker that the node can parse
    return f"{HITL_TOOL_MARKER}{json.dumps({'questions': questions})}"


# Alias for cleaner imports
human_feedback_tool = request_human_input

