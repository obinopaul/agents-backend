# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Prompt enhancement REST API endpoint.

Uses the same LLM-powered enhancement as the WebSocket enhance_prompt handler.
This provides a REST alternative for cases where WebSocket is not available.
"""

import re
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth

logger = logging.getLogger(__name__)

router = APIRouter(tags=['Prompt Enhancement'])


# =============================================================================
# System Prompt (same as WebSocket handler)
# =============================================================================

ENHANCE_PROMPT_SYSTEM = """You are an expert at improving user prompts to get better AI responses.

Your task is to take the user's original prompt and enhance it to be:
1. More specific and actionable
2. Clear about the desired output format
3. Well-structured with logical organization
4. Complete with any implied requirements

MUST FOLLOW THE RULES:
- Identify and articulate the core objective
- Add only the essential missing context
- Use precise, unambiguous language
- Maintain original scope - don't add features or complexity
- Do not add any features beyond the user request
- Do not mention tech-stack if it is not mentioned in the user request
- Do not mention any security-related information beyond the user request
- Do not add the deliverables section if they do not appear on the user request

Output the enhanced prompt directly, no explanations or metadata.

# Your Role
- Analyze the original prompt for clarity, specificity, and completeness
- Enhance the prompt by adding relevant details, context, and structure
- Make the prompt more actionable and results-oriented
- Preserve the user's original intent while improving effectiveness

# Enhancement Guidelines
1. **Add specificity**: Include relevant details, scope, and constraints
2. **Improve structure**: Organize the request logically with clear sections if needed
3. **Clarify expectations**: Specify desired output format, length, or style
4. **Add context**: Include background information that would help generate better results
5. **Make it actionable**: Ensure the prompt guides toward concrete, useful outputs

# Output Requirements
- You may include thoughts or reasoning before your final answer
- Wrap the final enhanced prompt in XML tags: <enhanced_prompt></enhanced_prompt>
- Do NOT include any explanations, comments, or meta-text within the XML tags
- Do NOT use phrases like "Enhanced Prompt:" or "Here's the enhanced version:" within the XML tags
- The content within the XML tags should be ready to use directly as a prompt

# Examples

**Original**: "Write about AI"
**Enhanced**:
<enhanced_prompt>
Write a comprehensive 1000-word analysis of artificial intelligence's current applications in healthcare, education, and business. Include specific examples of AI tools being used in each sector, discuss both benefits and challenges, and provide insights into future trends. Structure the response with clear sections for each industry and conclude with key takeaways.
</enhanced_prompt>

**Original**: "Explain climate change"
**Enhanced**:
<enhanced_prompt>
Provide a detailed explanation of climate change suitable for a general audience. Cover the scientific mechanisms behind global warming, major causes including greenhouse gas emissions, observable effects we're seeing today, and projected future impacts. Include specific data and examples, and explain the difference between weather and climate. Organize the response with clear headings and conclude with actionable steps individuals can take.
</enhanced_prompt>
"""


# =============================================================================
# Request/Response Models
# =============================================================================

class EnhancePromptRequest(BaseModel):
    """Request to enhance a prompt."""
    prompt: str
    context: Optional[str] = None


class EnhancePromptResponse(BaseModel):
    """Enhanced prompt response."""
    original_prompt: str
    enhanced_prompt: str
    reasoning: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_enhanced_prompt(response_text: str) -> str:
    """
    Extract the enhanced prompt from XML tags in the response.

    Falls back to the full response if no tags are found.
    """
    # Try to extract from XML tags
    match = re.search(
        r'<enhanced_prompt>(.*?)</enhanced_prompt>',
        response_text,
        re.DOTALL
    )
    if match:
        return match.group(1).strip()

    # Fallback: return full response
    return response_text.strip()


def _enhance_with_template(prompt: str) -> str:
    """
    Enhance the prompt using a template (fallback when LLM is unavailable).
    """
    # If the prompt is very short, expand it
    if len(prompt) < 50:
        return f"""Please help me with the following task:

{prompt}

Specifically, I need:
1. A clear understanding of the requirements
2. Step-by-step implementation approach
3. Working code examples with proper error handling
4. Best practices and considerations
5. Potential edge cases to handle

Please be thorough and provide complete, production-ready solutions."""

    # For medium-length prompts, add structure
    if len(prompt) < 200:
        return f"""Task: {prompt}

Please provide:
1. A comprehensive solution addressing all aspects of this request
2. Working code examples (if applicable)
3. Step-by-step explanation of your approach
4. Best practices and potential improvements
5. Error handling and edge cases

Ensure the solution is complete and ready to use."""

    # For longer prompts, just add some guidance
    return f"""{prompt}

Additional requirements:
- Provide complete, working solutions
- Include proper error handling
- Follow best practices for the technology involved
- Explain any important design decisions
- Consider edge cases and potential issues"""


# =============================================================================
# Endpoint
# =============================================================================

@router.post(
    '/enhance-prompt',
    summary='Enhance a user prompt using LLM',
    response_model=ResponseModel[EnhancePromptResponse],
    dependencies=[DependsJwtAuth]
)
async def enhance_prompt(
    request: Request,
    data: EnhancePromptRequest,
):
    """
    Enhance a user prompt for better AI responses.

    Uses an LLM with a specialized system prompt to:
    - Make prompts more specific and actionable
    - Add structure and clarity
    - Include relevant context and requirements
    - Preserve the original intent

    Falls back to template-based enhancement if LLM is unavailable.
    """
    original = data.prompt.strip()

    if not original:
        return response_base.fail(msg="Prompt cannot be empty")

    enhanced_prompt = None
    reasoning = None

    # Try LLM enhancement first
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from backend.src.llms.llm import get_llm

        # Build the user message
        user_message = f"Please enhance this prompt:\n\n{original}"

        if data.context:
            user_message += f"\n\nContext: {data.context}"

        llm = get_llm()

        response = await llm.ainvoke([
            SystemMessage(content=ENHANCE_PROMPT_SYSTEM),
            HumanMessage(content=user_message)
        ])

        raw_response = response.content.strip()
        enhanced_prompt = _extract_enhanced_prompt(raw_response)
        reasoning = "Enhanced using LLM with specialized prompt engineering"

        logger.info(f"Prompt enhanced via LLM for user {request.user.id}")

    except ImportError as e:
        logger.debug(f"LangChain not available for prompt enhancement: {e}")
    except Exception as e:
        logger.warning(f"LLM enhancement failed, using template fallback: {e}")

    # Fallback to template if LLM failed
    if not enhanced_prompt:
        enhanced_prompt = _enhance_with_template(original)
        reasoning = "Enhanced using template (LLM unavailable)"
        logger.info(f"Prompt enhanced via template for user {request.user.id}")

    return response_base.success(
        data=EnhancePromptResponse(
            original_prompt=original,
            enhanced_prompt=enhanced_prompt,
            reasoning=reasoning
        )
    )
