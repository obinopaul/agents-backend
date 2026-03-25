"""
Verifier Node Structured Output Types and Verification Tool.

Defines the Pydantic models for structured verification results and
the submit_verification tool that agents call to report verification status.

The tool-based approach avoids OpenAI's strict mode schema validation issues
that occur when using response_format with other tools.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.tools import tool
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models with ConfigDict for Schema Compatibility
# =============================================================================
# These models use ConfigDict(extra='forbid') to generate additionalProperties: false
# in their JSON schemas, ensuring compatibility with OpenAI/Anthropic strict mode.

class ImprovementArea(BaseModel):
    """A single area that needs improvement."""
    model_config = ConfigDict(extra='forbid')
    
    area: str = Field(
        description="The area or component that needs improvement"
    )
    issue: str = Field(
        description="What is the issue or problem"
    )
    suggestion: str = Field(
        description="How to fix or improve this area"
    )


class ImprovementAreaInput(BaseModel):
    """Input schema for a single improvement area (for tool args_schema)."""
    model_config = ConfigDict(extra='forbid')
    
    area: str = Field(
        ...,
        description="The area or component that needs improvement"
    )
    issue: str = Field(
        ...,
        description="What is the issue or problem"
    )
    suggestion: str = Field(
        ...,
        description="How to fix or improve this area"
    )


class VerificationResult(BaseModel):
    """
    Structured output from the Verifier Agent.
    
    The agent uses tools to analyze the implementation, then returns
    this structured result containing either a walkthrough (if sufficient)
    or improvement areas (if insufficient).
    """
    model_config = ConfigDict(extra='forbid')
    
    status: Literal["SUFFICIENT", "INSUFFICIENT"] = Field(
        description="Is the implementation sufficient and robust? SUFFICIENT means ready for delivery. INSUFFICIENT means more work needed."
    )
    
    # Reasoning applies to both cases
    reasoning: str = Field(
        description="Explanation of why this decision was made. What was analyzed and what led to this conclusion."
    )
    
    # If SUFFICIENT - walkthrough summary
    walkthrough: Optional[str] = Field(
        default=None,
        description="Detailed walkthrough of what was built. Only provided if status is SUFFICIENT. Summarize the implementation, key features, and how it meets requirements."
    )
    
    files_created: List[str] = Field(
        default_factory=list,
        description="List of files created or modified. Only populated if status is SUFFICIENT."
    )
    
    # If INSUFFICIENT - improvement areas (merged with next_steps)
    improvements: List[ImprovementArea] = Field(
        default_factory=list,
        description="Areas that need improvement with suggestions for how to fix them. Only populated if status is INSUFFICIENT."
    )


class SubmitVerificationInput(BaseModel):
    """Input schema for submit_verification tool with proper JSON schema generation."""
    model_config = ConfigDict(extra='forbid')
    
    status: Literal["SUFFICIENT", "INSUFFICIENT"] = Field(
        ...,
        description="Is the implementation sufficient and robust? SUFFICIENT means ready for delivery. INSUFFICIENT means more work needed."
    )
    
    reasoning: str = Field(
        ...,
        description="Explanation of why this decision was made. What was analyzed and what led to this conclusion."
    )
    
    walkthrough: Optional[str] = Field(
        default=None,
        description="Detailed walkthrough of what was built. Only provided if status is SUFFICIENT."
    )
    
    files_created: Optional[List[str]] = Field(
        default=None,
        description="List of files created or modified. Only populated if status is SUFFICIENT."
    )
    
    improvements: Optional[List[ImprovementAreaInput]] = Field(
        default=None,
        description="Areas that need improvement. Only populated if status is INSUFFICIENT. Each improvement has area, issue, and suggestion."
    )


# =============================================================================
# Verification Submission Tool
# =============================================================================

SUBMIT_VERIFICATION_DESCRIPTION = """Submit the verification result after analyzing the implementation.

Call this tool ONLY when you have completed your verification analysis.

For SUFFICIENT status:
- Provide a detailed walkthrough of what was built
- List all files created/modified
- Explain why the implementation meets requirements

For INSUFFICIENT status:
- Provide specific improvement areas with issues and suggestions
- Explain what needs to be fixed and how

You MUST call this tool exactly once to complete verification."""


@tool(description=SUBMIT_VERIFICATION_DESCRIPTION, args_schema=SubmitVerificationInput)
def submit_verification(
    status: Literal["SUFFICIENT", "INSUFFICIENT"],
    reasoning: str,
    walkthrough: Optional[str] = None,
    files_created: Optional[List[str]] = None,
    improvements: Optional[List[dict]] = None,
) -> str:
    """
    Submit the verification result.
    
    This tool is called by the verifier agent to report whether the
    implementation is sufficient or needs improvement.
    
    Args:
        status: SUFFICIENT or INSUFFICIENT
        reasoning: Explanation of the decision
        walkthrough: Summary of what was built (if SUFFICIENT)
        files_created: List of files created/modified (if SUFFICIENT)
        improvements: Areas needing improvement (if INSUFFICIENT)
    
    Returns:
        Confirmation message
    """
    if status == "SUFFICIENT":
        files_count = len(files_created) if files_created else 0
        return f"✅ Verification COMPLETE: Implementation is SUFFICIENT. {files_count} file(s) documented."
    else:
        improvements_count = len(improvements) if improvements else 0
        return f"⚠️ Verification COMPLETE: Implementation is INSUFFICIENT. {improvements_count} improvement area(s) identified."


def create_submit_verification_tool():
    """Factory function to create the submit_verification tool.
    
    Returns:
        The submit_verification tool with proper schema configuration.
    """
    return submit_verification


def extract_verification_result(messages: list) -> Optional[VerificationResult]:
    """
    Extract VerificationResult from agent messages by finding the submit_verification tool call.
    
    Searches through messages (in reverse order for efficiency) to find a tool call
    to submit_verification and extracts the arguments as a VerificationResult.
    
    Args:
        messages: List of messages from agent execution
        
    Returns:
        VerificationResult if found, None otherwise
    """
    # Search in reverse (most recent first) for efficiency
    for msg in reversed(messages):
        # Check for tool_calls attribute (AIMessage with tool calls)
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call.get('name') == 'submit_verification':
                    args = tool_call.get('args', {})
                    try:
                        # Convert improvements from list of dicts to ImprovementArea objects
                        improvements_data = args.get('improvements') or []
                        improvements = [
                            ImprovementArea(**imp) if isinstance(imp, dict) else imp
                            for imp in improvements_data
                        ]
                        
                        return VerificationResult(
                            status=args.get('status', 'INSUFFICIENT'),
                            reasoning=args.get('reasoning', 'No reasoning provided.'),
                            walkthrough=args.get('walkthrough'),
                            files_created=args.get('files_created') or [],
                            improvements=improvements,
                        )
                    except Exception as e:
                        logger.error(f"Failed to parse verification result: {e}")
                        continue
        
        # Also check for content that might contain tool call info (edge case)
        if hasattr(msg, 'additional_kwargs'):
            tool_calls = msg.additional_kwargs.get('tool_calls', [])
            for tc in tool_calls:
                if tc.get('function', {}).get('name') == 'submit_verification':
                    try:
                        args_str = tc.get('function', {}).get('arguments', '{}')
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        
                        improvements_data = args.get('improvements') or []
                        improvements = [
                            ImprovementArea(**imp) if isinstance(imp, dict) else imp
                            for imp in improvements_data
                        ]
                        
                        return VerificationResult(
                            status=args.get('status', 'INSUFFICIENT'),
                            reasoning=args.get('reasoning', 'No reasoning provided.'),
                            walkthrough=args.get('walkthrough'),
                            files_created=args.get('files_created') or [],
                            improvements=improvements,
                        )
                    except Exception as e:
                        logger.error(f"Failed to parse verification from additional_kwargs: {e}")
                        continue
    
    return None


__all__ = [
    "ImprovementArea",
    "ImprovementAreaInput",
    "VerificationResult", 
    "SubmitVerificationInput",
    "submit_verification",
    "create_submit_verification_tool",
    "extract_verification_result",
]
