# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Handler for enhance prompt command."""

import logging
from typing import Dict, Any, Optional

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)

from backend.core.conf import settings

logger = logging.getLogger(__name__)

# System prompt for enhancing user prompts
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


class EnhancePromptHandler(CommandHandler):
    """
    Handler for enhance_prompt command.
    
    Takes a user's prompt and enhances it using an LLM to make it
    more detailed and actionable. This helps users write better prompts.
    
    The enhanced prompt includes:
    - More specific requirements
    - Structured output expectations
    - Best practices requests
    - Error handling considerations
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.ENHANCE_PROMPT

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle enhance prompt request.
        
        :param content: Contains 'prompt' to enhance, optional 'model_name'
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        try:
            original_prompt = content.get('prompt', '') or content.get('text', '')
            model_name = content.get('model_name', 'gpt-4o-mini')
            files = content.get('files', [])
            
            if not original_prompt:
                await self.send_error(
                    room=sid,
                    message="No prompt provided to enhance"
                )
                return
            
            await self.send_processing_event(
                session_uuid=session_uuid,
                message="Enhancing prompt..."
            )
            
            # Try to use LLM for enhancement
            enhanced_prompt = await self._enhance_with_llm(
                original_prompt=original_prompt,
                model_name=model_name,
                files=files
            )
            
            # Fall back to template-based enhancement if LLM fails
            if not enhanced_prompt:
                enhanced_prompt = self._enhance_with_template(original_prompt)
            
            await self.emit_to_sid(
                sid=sid,
                event_type='prompt_enhanced',
                content={
                    'session_uuid': session_uuid,
                    'original_prompt': original_prompt,
                    'enhanced_prompt': enhanced_prompt,
                    'result': enhanced_prompt,  # Compatibility with frontend
                    'original_request': original_prompt,  # Compatibility with frontend
                }
            )
            
            logger.info(f"Prompt enhanced for session {session_uuid}")
            
        except Exception as e:
            logger.error(f"Error enhancing prompt: {e}", exc_info=True)
            await self.send_error(
                room=sid,
                message=f"Failed to enhance prompt: {str(e)}"
            )

    async def _enhance_with_llm(
        self,
        original_prompt: str,
        model_name: str,
        files: list
    ) -> Optional[str]:
        """
        Enhance the prompt using an LLM.
        
        :param original_prompt: Original prompt
        :param model_name: LLM model to use
        :param files: Optional attached files
        :return: Enhanced prompt or None if LLM call fails
        """
        try:
            # Import LangChain components
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            
            from backend.src.llms.llm import (
                get_llm,
                get_fallback_llm,
                get_fallback_model_identifiers,
            )
            
            # Build the user message
            user_message = f"Please enhance this prompt:\n\n{original_prompt}"
            
            if files:
                user_message += f"\n\nNote: The user has attached {len(files)} file(s) to this prompt."
            
            llm = get_llm()

            # # Create the LLM client
            # llm = ChatOpenAI(
            #     model=model_name,
            #     temperature=0.3,
            #     api_key=settings.OPENAI_API_KEY,
            # )
            
            # Get the enhanced prompt
            response = await llm.ainvoke([
                SystemMessage(content=ENHANCE_PROMPT_SYSTEM),
                HumanMessage(content=user_message)
            ])
            
            enhanced = response.content.strip()
            
            if enhanced:
                return enhanced
            
        except ImportError:
            logger.debug("LangChain not available for prompt enhancement")
        except Exception as e:
            logger.warning(f"LLM enhancement failed, using template: {e}")
        
        return None

    def _enhance_with_template(self, prompt: str) -> str:
        """
        Enhance the prompt using a template (fallback).
        
        :param prompt: Original prompt
        :return: Enhanced prompt
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
