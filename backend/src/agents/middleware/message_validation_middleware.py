"""Message Validation Middleware for LangChain Agents.

This middleware intercepts model calls and validates message content before sending to the LLM API.
It specifically addresses the issue where AIMessage tool_calls may have null IDs, which causes
400 BadRequestError from the OpenAI/Anthropic APIs.

The issue occurs inside the deepagent framework during multi-turn tool calling - messages accumulate
and some may have malformed tool_call IDs. This middleware ensures all messages are valid before
each LLM call.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

logger = logging.getLogger(__name__)


class MessageValidationMiddleware(AgentMiddleware):
    """Middleware that validates and fixes message content before LLM calls.
    
    This middleware intercepts the model call and ensures:
    1. All AIMessage tool_calls have valid string IDs
    2. All ToolMessage objects have valid tool_call_id strings
    3. Messages with invalid content are fixed rather than causing API errors
    
    This is necessary because the deepagent framework accumulates messages during
    multi-turn tool calling, and some messages may have null/invalid tool_call IDs
    which causes 400 BadRequestError from LLM APIs.
    """

    def __init__(self) -> None:
        """Initialize the MessageValidationMiddleware."""
        super().__init__()
        self.tools = []  # No tools provided by this middleware

    def _generate_tool_call_id(self) -> str:
        """Generate a valid tool call ID."""
        return f"call_{uuid.uuid4().hex[:24]}"

    def _validate_and_fix_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """Validate and fix messages to ensure all tool_call IDs are valid strings.
        
        Args:
            messages: List of messages to validate
            
        Returns:
            List of validated/fixed messages
        """
        fixed_count = 0
        
        for i, msg in enumerate(messages):
            try:
                # Fix AIMessage tool_calls
                if isinstance(msg, AIMessage):
                    # Check tool_calls attribute
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for j, tool_call in enumerate(msg.tool_calls):
                            if isinstance(tool_call, dict):
                                tc_id = tool_call.get('id')
                                if tc_id is None or not isinstance(tc_id, str) or tc_id == '':
                                    new_id = self._generate_tool_call_id()
                                    tool_call['id'] = new_id
                                    fixed_count += 1
                                    logger.warning(
                                        f"[MessageValidationMiddleware] Fixed null tool_calls[{j}].id "
                                        f"in message {i} -> {new_id}"
                                    )
                            elif hasattr(tool_call, 'id'):
                                tc_id = tool_call.id
                                if tc_id is None or not isinstance(tc_id, str) or tc_id == '':
                                    new_id = self._generate_tool_call_id()
                                    # ToolCall objects may be immutable, create a new one
                                    try:
                                        tool_call.id = new_id
                                    except AttributeError:
                                        # If immutable, try to create a copy with fixed ID
                                        logger.warning(
                                            f"[MessageValidationMiddleware] Could not fix immutable "
                                            f"tool_call in message {i}, skipping"
                                        )
                                        continue
                                    fixed_count += 1
                                    logger.warning(
                                        f"[MessageValidationMiddleware] Fixed null tool_calls[{j}].id "
                                        f"in message {i} -> {new_id}"
                                    )
                    
                    # Also check additional_kwargs for tool_calls (legacy format)
                    if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                        if 'tool_calls' in msg.additional_kwargs:
                            for j, tool_call in enumerate(msg.additional_kwargs['tool_calls']):
                                if isinstance(tool_call, dict):
                                    tc_id = tool_call.get('id')
                                    if tc_id is None or not isinstance(tc_id, str) or tc_id == '':
                                        new_id = self._generate_tool_call_id()
                                        tool_call['id'] = new_id
                                        fixed_count += 1
                                        logger.warning(
                                            f"[MessageValidationMiddleware] Fixed null "
                                            f"additional_kwargs.tool_calls[{j}].id in message {i} -> {new_id}"
                                        )
                
                # Fix ToolMessage tool_call_id
                elif isinstance(msg, ToolMessage):
                    if not hasattr(msg, 'tool_call_id') or msg.tool_call_id is None or \
                       not isinstance(msg.tool_call_id, str) or msg.tool_call_id == '':
                        new_id = self._generate_tool_call_id()
                        msg.tool_call_id = new_id
                        fixed_count += 1
                        logger.warning(
                            f"[MessageValidationMiddleware] Fixed null tool_call_id "
                            f"in ToolMessage {i} -> {new_id}"
                        )
                        
            except Exception as e:
                logger.error(f"[MessageValidationMiddleware] Error validating message {i}: {e}")
        
        if fixed_count > 0:
            logger.info(f"[MessageValidationMiddleware] Fixed {fixed_count} invalid tool_call IDs")
        
        return messages

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous wrapper - validates messages before model call.
        
        Args:
            request: Model request containing messages
            handler: Next handler in middleware chain
            
        Returns:
            Model response from the handler
        """
        # Validate messages in the request
        if hasattr(request, 'messages') and request.messages:
            self._validate_and_fix_messages(request.messages)
        
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async wrapper - validates messages before model call.
        
        Args:
            request: Model request containing messages
            handler: Next handler in middleware chain
            
        Returns:
            Model response from the handler
        """
        # Validate messages in the request
        if hasattr(request, 'messages') and request.messages:
            self._validate_and_fix_messages(request.messages)
        
        return await handler(request)


__all__ = ["MessageValidationMiddleware"]
