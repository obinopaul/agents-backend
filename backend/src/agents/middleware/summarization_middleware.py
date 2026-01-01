"""Summarization middleware with Factory.AI-style incremental compression."""

import uuid
import warnings
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal, cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    MessageLikeRepresentation,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain.chat_models import BaseChatModel, init_chat_model

TokenCounter = Callable[[Iterable[MessageLikeRepresentation]], int]

DEFAULT_SUMMARY_PROMPT = """<role>
Context Extraction Assistant
</role>

<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>

<token_constraint>
CRITICAL: Your response must not exceed {max_summary_tokens} tokens. This is a hard limit.
</token_constraint>

<objective_information>
You're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.
This context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to your overall goal.
</objective_information>

<instructions>
The conversation history below will be replaced with the context you extract in this step. Because of this, you must do your very best to extract and record all of the most important context from the conversation history.
You want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.

Focus on:
- Session intent and requirements
- High-level outcomes and decisions
- Key artifacts (files, changes, results)
- Critical identifiers for reconstructing context

Stay under {max_summary_tokens} tokens.
</instructions>

The user will message you with the full message history you'll be extracting context from, to then replace. Carefully read over it all, and think deeply about what information is most important to your overall goal that should be saved:

With all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.
Respond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.

<messages>
Messages to summarize:
{messages}
</messages>"""

DEFAULT_UPDATE_PROMPT = """<role>
Context Update Assistant
</role>

<primary_objective>
You are updating an existing conversation summary with new information. Your goal is to merge the new messages into the existing summary while maintaining the most important context.
</primary_objective>

<token_constraint>
CRITICAL: Your response must not exceed {max_summary_tokens} tokens. This is a hard limit.
</token_constraint>

<instructions>
You have an EXISTING SUMMARY that covers earlier messages (up to message index {anchor_index}).
Now you need to incorporate NEW MESSAGES (from index {anchor_index} to {cutoff_index}) into this summary.

DO NOT re-summarize everything. Instead:
1. Read the existing summary to understand what's already captured
2. Extract key information from the NEW messages only
3. Merge the new information with the existing summary
4. As you add new context, remove or condense less critical older details to stay within the token limit
5. Prioritize: recent context > session intent > high-level outcomes > specific details

The summary should be comprehensive yet concise, never exceeding {max_summary_tokens} tokens.
</instructions>

<existing_summary>
{existing_summary}
</existing_summary>

<new_messages>
New messages to incorporate (indices {anchor_index} to {cutoff_index}):
{new_messages}
</new_messages>

Respond ONLY with the updated merged summary. Do not include any additional text."""

_DEFAULT_MESSAGES_TO_KEEP = 20
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15
_SEARCH_RANGE_FOR_TOOL_PAIRS = 5
_DEFAULT_MAX_SUMMARY_TOKENS = 2000  # T_summary: Maximum size for any summary

ContextFraction = tuple[Literal["fraction"], float]
ContextTokens = tuple[Literal["tokens"], int]
ContextMessages = tuple[Literal["messages"], int]

ContextSize = ContextFraction | ContextTokens | ContextMessages


class SummarizationState:
    """Tracks persistent summary state across compressions (Factory.AI style)."""
    
    def __init__(self):
        self.summary: str | None = None
        self.anchor_index: int | None = None  # Message index where summary ends
        self.anchor_message_id: str | None = None  # ID of the anchor message
        
    def has_summary(self) -> bool:
        return self.summary is not None and self.anchor_index is not None


class SummarizationMiddleware(AgentMiddleware):
    """Summarizes conversation history with incremental updates (Factory.AI approach).

    This middleware monitors message token counts and automatically summarizes older
    messages when a threshold is reached. Unlike naive approaches that re-summarize
    everything each time, this uses Factory.AI's incremental compression:
    
    1. Maintains a persistent summary with an anchor point
    2. Only summarizes newly dropped messages
    3. Merges new summaries into the existing summary
    
    This dramatically reduces summarization cost and latency in long conversations.
    """

    def __init__(
        self,
        model: str | BaseChatModel,
        *,
        trigger: ContextSize | list[ContextSize] | None = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        max_summary_tokens: int = _DEFAULT_MAX_SUMMARY_TOKENS,
        token_counter: TokenCounter = count_tokens_approximately,
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        update_prompt: str = DEFAULT_UPDATE_PROMPT,
        trim_tokens_to_summarize: int | None = _DEFAULT_TRIM_TOKEN_LIMIT,
        **deprecated_kwargs: Any,
    ) -> None:
        """Initialize summarization middleware.

        Args:
            model: The language model to use for generating summaries.
            trigger: One or more thresholds that trigger summarization (T_max).
                Examples: `("messages", 50)`, `("tokens", 3000)`, `[("fraction", 0.8)]`.
            keep: Context retention policy after summarization (T_retained).
                Examples: `("messages", 20)`, `("tokens", 3000)`, `("fraction", 0.3)`.
            max_summary_tokens: T_summary - Maximum token size enforced for any summary.
                The prompts enforce this limit to prevent unbounded summary growth.
            token_counter: Function to count tokens in messages.
            summary_prompt: Prompt for initial summary generation. Should reference 
                {max_summary_tokens} and {messages} placeholders.
            update_prompt: Prompt for incremental summary updates (Factory.AI style). 
                Should reference {max_summary_tokens}, {existing_summary}, {new_messages},
                {anchor_index}, and {cutoff_index} placeholders.
            trim_tokens_to_summarize: Max tokens when preparing summarization input.
        """
        # Handle deprecated parameters
        if "max_tokens_before_summary" in deprecated_kwargs:
            value = deprecated_kwargs["max_tokens_before_summary"]
            warnings.warn(
                "max_tokens_before_summary is deprecated. Use trigger=('tokens', value) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if trigger is None and value is not None:
                trigger = ("tokens", value)

        if "messages_to_keep" in deprecated_kwargs:
            value = deprecated_kwargs["messages_to_keep"]
            warnings.warn(
                "messages_to_keep is deprecated. Use keep=('messages', value) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if keep == ("messages", _DEFAULT_MESSAGES_TO_KEEP):
                keep = ("messages", value)

        super().__init__()

        if isinstance(model, str):
            model = init_chat_model(model)

        self.model = model
        if trigger is None:
            self.trigger: ContextSize | list[ContextSize] | None = None
            trigger_conditions: list[ContextSize] = []
        elif isinstance(trigger, list):
            validated_list = [self._validate_context_size(item, "trigger") for item in trigger]
            self.trigger = validated_list
            trigger_conditions = validated_list
        else:
            validated = self._validate_context_size(trigger, "trigger")
            self.trigger = validated
            trigger_conditions = [validated]
        self._trigger_conditions = trigger_conditions

        self.keep = self._validate_context_size(keep, "keep")
        self.max_summary_tokens = max_summary_tokens
        self.token_counter = token_counter
        self.summary_prompt = summary_prompt
        self.update_prompt = update_prompt
        self.trim_tokens_to_summarize = trim_tokens_to_summarize
        
        # Factory.AI style: persistent state tracking
        self._summary_state = SummarizationState()

        requires_profile = any(condition[0] == "fraction" for condition in self._trigger_conditions)
        if self.keep[0] == "fraction":
            requires_profile = True
        if requires_profile and self._get_profile_limits() is None:
            msg = (
                "Model profile information is required to use fractional token limits, "
                "and is unavailable for the specified model. Please use absolute token "
                "counts instead, or pass "
                '`\n\nChatModel(..., profile={"max_input_tokens": ...})`.\n\n'
                "with a desired integer value of the model's maximum input tokens."
            )
            raise ValueError(msg)

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:  # noqa: ARG002
        """Process messages with Factory.AI-style incremental compression."""
        messages = state["messages"]
        self._ensure_message_ids(messages)

        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None

        cutoff_index = self._determine_cutoff_index(messages)

        if cutoff_index <= 0:
            return None

        # Factory.AI approach: determine if this is initial or incremental
        if self._summary_state.has_summary():
            return self._incremental_compression(messages, cutoff_index)
        else:
            return self._initial_compression(messages, cutoff_index)

    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:  # noqa: ARG002
        """Async version with Factory.AI-style incremental compression."""
        messages = state["messages"]
        self._ensure_message_ids(messages)

        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None

        cutoff_index = self._determine_cutoff_index(messages)

        if cutoff_index <= 0:
            return None

        # Factory.AI approach: determine if this is initial or incremental
        if self._summary_state.has_summary():
            return await self._aincremental_compression(messages, cutoff_index)
        else:
            return await self._ainitial_compression(messages, cutoff_index)

    def _initial_compression(
        self, messages: list[AnyMessage], cutoff_index: int
    ) -> dict[str, Any]:
        """First compression: create initial summary and set anchor point."""
        messages_to_summarize, preserved_messages = self._partition_messages(
            messages, cutoff_index
        )

        summary = self._create_summary(messages_to_summarize)
        
        # Set anchor point at the boundary between summarized and preserved
        # The anchor marks the last message included in the summary
        anchor_index = cutoff_index - 1 if cutoff_index > 0 else 0
        anchor_message_id = messages[anchor_index].id if anchor_index < len(messages) else None
        
        self._summary_state.summary = summary
        self._summary_state.anchor_index = anchor_index
        self._summary_state.anchor_message_id = anchor_message_id

        new_messages = self._build_summary_message(summary, anchor_index)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    async def _ainitial_compression(
        self, messages: list[AnyMessage], cutoff_index: int
    ) -> dict[str, Any]:
        """Async first compression."""
        messages_to_summarize, preserved_messages = self._partition_messages(
            messages, cutoff_index
        )

        summary = await self._acreate_summary(messages_to_summarize)
        
        # Set anchor point at the boundary between summarized and preserved
        anchor_index = cutoff_index - 1 if cutoff_index > 0 else 0
        anchor_message_id = messages[anchor_index].id if anchor_index < len(messages) else None
        
        self._summary_state.summary = summary
        self._summary_state.anchor_index = anchor_index
        self._summary_state.anchor_message_id = anchor_message_id

        new_messages = self._build_summary_message(summary, anchor_index)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    def _incremental_compression(
        self, messages: list[AnyMessage], cutoff_index: int
    ) -> dict[str, Any]:
        """Factory.AI incremental update: only summarize newly dropped messages."""
        # Find where the old anchor was in current message list
        old_anchor_index = self._find_anchor_in_messages(messages)
        
        if old_anchor_index is None:
            # Anchor message was already dropped, fall back to full summarization
            return self._initial_compression(messages, cutoff_index)
        
        # Only summarize messages between old anchor and new cutoff
        # This is the key Factory.AI optimization!
        newly_dropped_start = old_anchor_index + 1
        newly_dropped_messages = messages[newly_dropped_start:cutoff_index]
        
        if not newly_dropped_messages:
            # Edge case: nothing new to summarize
            _, preserved_messages = self._partition_messages(messages, cutoff_index)
            new_messages = self._build_summary_message(
                self._summary_state.summary or "", cutoff_index
            )
            return {
                "messages": [
                    RemoveMessage(id=REMOVE_ALL_MESSAGES),
                    *new_messages,
                    *preserved_messages,
                ]
            }
        
        # Update summary with only the new messages
        # T_summary is enforced by the prompt itself
        updated_summary = self._update_summary(
            self._summary_state.summary or "",
            newly_dropped_messages,
            old_anchor_index,
            cutoff_index,
        )
        
        # Update anchor point
        self._summary_state.summary = updated_summary
        self._summary_state.anchor_index = cutoff_index - 1
        if cutoff_index > 0:
            self._summary_state.anchor_message_id = messages[cutoff_index - 1].id
        
        _, preserved_messages = self._partition_messages(messages, cutoff_index)
        new_messages = self._build_summary_message(updated_summary, cutoff_index)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    async def _aincremental_compression(
        self, messages: list[AnyMessage], cutoff_index: int
    ) -> dict[str, Any]:
        """Async Factory.AI incremental update."""
        old_anchor_index = self._find_anchor_in_messages(messages)
        
        if old_anchor_index is None:
            return await self._ainitial_compression(messages, cutoff_index)
        
        newly_dropped_start = old_anchor_index + 1
        newly_dropped_messages = messages[newly_dropped_start:cutoff_index]
        
        if not newly_dropped_messages:
            _, preserved_messages = self._partition_messages(messages, cutoff_index)
            new_messages = self._build_summary_message(
                self._summary_state.summary or "", cutoff_index
            )
            return {
                "messages": [
                    RemoveMessage(id=REMOVE_ALL_MESSAGES),
                    *new_messages,
                    *preserved_messages,
                ]
            }
        
        # T_summary is enforced by the prompt itself
        updated_summary = await self._aupdate_summary(
            self._summary_state.summary or "",
            newly_dropped_messages,
            old_anchor_index,
            cutoff_index,
        )
        
        self._summary_state.summary = updated_summary
        self._summary_state.anchor_index = cutoff_index - 1
        if cutoff_index > 0:
            self._summary_state.anchor_message_id = messages[cutoff_index - 1].id
        
        _, preserved_messages = self._partition_messages(messages, cutoff_index)
        new_messages = self._build_summary_message(updated_summary, cutoff_index)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    def _find_anchor_in_messages(self, messages: list[AnyMessage]) -> int | None:
        """Find the current position of the anchor message in the message list."""
        if not self._summary_state.anchor_message_id:
            return None
        
        for i, msg in enumerate(messages):
            if msg.id == self._summary_state.anchor_message_id:
                return i
        
        return None

    def _update_summary(
        self,
        existing_summary: str,
        new_messages: list[AnyMessage],
        anchor_index: int,
        cutoff_index: int,
    ) -> str:
        """Factory.AI style: merge new messages into existing summary.
        
        T_summary enforcement happens in the prompt itself, not via post-processing.
        """
        if not new_messages:
            return existing_summary

        trimmed_messages = self._trim_messages_for_summary(new_messages)
        if not trimmed_messages:
            return existing_summary

        try:
            prompt = self.update_prompt.format(
                existing_summary=existing_summary,
                new_messages=trimmed_messages,
                anchor_index=anchor_index,
                cutoff_index=cutoff_index,
                max_summary_tokens=self.max_summary_tokens,
            )
            response = self.model.invoke(prompt)
            return response.text.strip()
        except Exception as e:  # noqa: BLE001
            # Fallback: concatenate summaries if update fails
            return f"{existing_summary}\n\nRecent updates: {e!s}"

    async def _aupdate_summary(
        self,
        existing_summary: str,
        new_messages: list[AnyMessage],
        anchor_index: int,
        cutoff_index: int,
    ) -> str:
        """Async Factory.AI style summary update.
        
        T_summary enforcement happens in the prompt itself, not via post-processing.
        """
        if not new_messages:
            return existing_summary

        trimmed_messages = self._trim_messages_for_summary(new_messages)
        if not trimmed_messages:
            return existing_summary

        try:
            prompt = self.update_prompt.format(
                existing_summary=existing_summary,
                new_messages=trimmed_messages,
                anchor_index=anchor_index,
                cutoff_index=cutoff_index,
                max_summary_tokens=self.max_summary_tokens,
            )
            response = await self.model.ainvoke(prompt)
            return response.text.strip()
        except Exception as e:  # noqa: BLE001
            return f"{existing_summary}\n\nRecent updates: {e!s}"

    def _build_summary_message(self, summary: str, anchor_index: int) -> list[HumanMessage]:
        """Build summary message with anchor metadata."""
        return [
            HumanMessage(
                content=f"Summary of conversation (up to message index {anchor_index}):\n\n{summary}",
                additional_kwargs={"anchor_index": anchor_index},
            )
        ]

    def _should_summarize(self, messages: list[AnyMessage], total_tokens: int) -> bool:
        """Determine whether summarization should run for the current token usage."""
        if not self._trigger_conditions:
            return False

        for kind, value in self._trigger_conditions:
            if kind == "messages" and len(messages) >= value:
                return True
            if kind == "tokens" and total_tokens >= value:
                return True
            if kind == "fraction":
                max_input_tokens = self._get_profile_limits()
                if max_input_tokens is None:
                    continue
                threshold = int(max_input_tokens * value)
                if threshold <= 0:
                    threshold = 1
                if total_tokens >= threshold:
                    return True
        return False

    def _determine_cutoff_index(self, messages: list[AnyMessage]) -> int:
        """Choose cutoff index respecting retention configuration.
        
        This intelligently determines where to split messages based on T_retained:
        - For token-based: Uses binary search to find optimal cutoff
        - For message-based: Counts from the end
        - Always respects AI/Tool message pairs to avoid breaking context
        
        Returns the index where compression should cut (messages[:cutoff] get summarized)
        """
        kind, value = self.keep
        if kind in {"tokens", "fraction"}:
            token_based_cutoff = self._find_token_based_cutoff(messages)
            if token_based_cutoff is not None:
                return token_based_cutoff
            return self._find_safe_cutoff(messages, _DEFAULT_MESSAGES_TO_KEEP)
        return self._find_safe_cutoff(messages, cast("int", value))

    def _find_token_based_cutoff(self, messages: list[AnyMessage]) -> int | None:
        """Find cutoff index based on target token retention."""
        if not messages:
            return 0

        kind, value = self.keep
        if kind == "fraction":
            max_input_tokens = self._get_profile_limits()
            if max_input_tokens is None:
                return None
            target_token_count = int(max_input_tokens * value)
        elif kind == "tokens":
            target_token_count = int(value)
        else:
            return None

        if target_token_count <= 0:
            target_token_count = 1

        if self.token_counter(messages) <= target_token_count:
            return 0

        left, right = 0, len(messages)
        cutoff_candidate = len(messages)
        max_iterations = len(messages).bit_length() + 1
        for _ in range(max_iterations):
            if left >= right:
                break

            mid = (left + right) // 2
            if self.token_counter(messages[mid:]) <= target_token_count:
                cutoff_candidate = mid
                right = mid
            else:
                left = mid + 1

        if cutoff_candidate == len(messages):
            cutoff_candidate = left

        if cutoff_candidate >= len(messages):
            if len(messages) == 1:
                return 0
            cutoff_candidate = len(messages) - 1

        for i in range(cutoff_candidate, -1, -1):
            if self._is_safe_cutoff_point(messages, i):
                return i

        return 0

    def _get_profile_limits(self) -> int | None:
        """Retrieve max input token limit from the model profile."""
        try:
            profile = self.model.profile
        except AttributeError:
            return None

        if not isinstance(profile, Mapping):
            return None

        max_input_tokens = profile.get("max_input_tokens")

        if not isinstance(max_input_tokens, int):
            return None

        return max_input_tokens

    def _validate_context_size(self, context: ContextSize, parameter_name: str) -> ContextSize:
        """Validate context configuration tuples."""
        kind, value = context
        if kind == "fraction":
            if not 0 < value <= 1:
                msg = f"Fractional {parameter_name} values must be between 0 and 1, got {value}."
                raise ValueError(msg)
        elif kind in {"tokens", "messages"}:
            if value <= 0:
                msg = f"{parameter_name} thresholds must be greater than 0, got {value}."
                raise ValueError(msg)
        else:
            msg = f"Unsupported context size type {kind} for {parameter_name}."
            raise ValueError(msg)
        return context

    def _ensure_message_ids(self, messages: list[AnyMessage]) -> None:
        """Ensure all messages have unique IDs for the add_messages reducer."""
        for msg in messages:
            if msg.id is None:
                msg.id = str(uuid.uuid4())

    def _partition_messages(
        self,
        conversation_messages: list[AnyMessage],
        cutoff_index: int,
    ) -> tuple[list[AnyMessage], list[AnyMessage]]:
        """Partition messages into those to summarize and those to preserve."""
        messages_to_summarize = conversation_messages[:cutoff_index]
        preserved_messages = conversation_messages[cutoff_index:]

        return messages_to_summarize, preserved_messages

    def _find_safe_cutoff(self, messages: list[AnyMessage], messages_to_keep: int) -> int:
        """Find safe cutoff point that preserves AI/Tool message pairs."""
        if len(messages) <= messages_to_keep:
            return 0

        target_cutoff = len(messages) - messages_to_keep

        for i in range(target_cutoff, -1, -1):
            if self._is_safe_cutoff_point(messages, i):
                return i

        return 0

    def _is_safe_cutoff_point(self, messages: list[AnyMessage], cutoff_index: int) -> bool:
        """Check if cutting at index would separate AI/Tool message pairs."""
        if cutoff_index >= len(messages):
            return True

        search_start = max(0, cutoff_index - _SEARCH_RANGE_FOR_TOOL_PAIRS)
        search_end = min(len(messages), cutoff_index + _SEARCH_RANGE_FOR_TOOL_PAIRS)

        for i in range(search_start, search_end):
            if not self._has_tool_calls(messages[i]):
                continue

            tool_call_ids = self._extract_tool_call_ids(cast("AIMessage", messages[i]))
            if self._cutoff_separates_tool_pair(messages, i, cutoff_index, tool_call_ids):
                return False

        return True

    def _has_tool_calls(self, message: AnyMessage) -> bool:
        """Check if message is an AI message with tool calls."""
        return (
            isinstance(message, AIMessage) 
            and hasattr(message, "tool_calls") 
            and message.tool_calls  # type: ignore[return-value]
        )

    def _extract_tool_call_ids(self, ai_message: AIMessage) -> set[str]:
        """Extract tool call IDs from an AI message."""
        tool_call_ids = set()
        for tc in ai_message.tool_calls:
            call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            if call_id is not None:
                tool_call_ids.add(call_id)
        return tool_call_ids

    def _cutoff_separates_tool_pair(
        self,
        messages: list[AnyMessage],
        ai_message_index: int,
        cutoff_index: int,
        tool_call_ids: set[str],
    ) -> bool:
        """Check if cutoff separates an AI message from its corresponding tool messages."""
        for j in range(ai_message_index + 1, len(messages)):
            message = messages[j]
            if isinstance(message, ToolMessage) and message.tool_call_id in tool_call_ids:
                ai_before_cutoff = ai_message_index < cutoff_index
                tool_before_cutoff = j < cutoff_index
                if ai_before_cutoff != tool_before_cutoff:
                    return True
        return False

    def _create_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """Generate initial summary for the given messages.
        
        T_summary enforcement happens in the prompt itself, not via post-processing.
        """
        if not messages_to_summarize:
            return "No previous conversation history."

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        try:
            response = self.model.invoke(
                self.summary_prompt.format(
                    messages=trimmed_messages,
                    max_summary_tokens=self.max_summary_tokens,
                )
            )
            return response.text.strip()
        except Exception as e:  # noqa: BLE001
            return f"Error generating summary: {e!s}"

    async def _acreate_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """Generate initial summary for the given messages (async).
        
        T_summary enforcement happens in the prompt itself, not via post-processing.
        """
        if not messages_to_summarize:
            return "No previous conversation history."

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        try:
            response = await self.model.ainvoke(
                self.summary_prompt.format(
                    messages=trimmed_messages,
                    max_summary_tokens=self.max_summary_tokens,
                )
            )
            return response.text.strip()
        except Exception as e:  # noqa: BLE001
            return f"Error generating summary: {e!s}"

    def _trim_messages_for_summary(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        """Trim messages to fit within summary generation limits."""
        try:
            if self.trim_tokens_to_summarize is None:
                return messages
            return trim_messages(
                messages,
                max_tokens=self.trim_tokens_to_summarize,
                token_counter=self.token_counter,
                start_on="human",
                strategy="last",
                allow_partial=True,
                include_system=True,
            )
        except Exception:  # noqa: BLE001
            return messages[-_DEFAULT_FALLBACK_MESSAGE_COUNT:]