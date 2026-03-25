
import json
import logging
import time
from typing import Optional, Dict, Any, Tuple, List
from uuid import uuid4


class StreamBuffer:
    """
    Buffers streaming events (SSE) and emits atomic events for II-Agent compatibility.
    
    The II-Agent Frontend expects atomic events (one "bubble" per action).
    High-frequency streaming events (deltas) cause UI stutter and duplicate bubbles 
    because the frontend treats each event ID as a new message.
    
    This buffer:
    1. Accumulates `tool_call` deltas into a single `TOOL_CALL` event.
    2. Accumulates `reasoning` deltas into a single `AGENT_THINKING` event.
    3. Accumulates `message_chunk` deltas into a single `AGENT_RESPONSE` event.
    4. Passes through other events (status, error, etc.) immediately.
    """
    
    def __init__(self):
        self.reset()
        self.logger = logging.getLogger("StreamBuffer")

    def reset(self):
        """Reset all internal buffers."""
        # Tool Call Buffer
        self.tool_id: Optional[str] = None
        self.tool_name: Optional[str] = None
        self.tool_input_parts: List[str] = []
        
        # Thinking Buffer
        self.thinking_id: Optional[str] = None
        self.thinking_parts: List[str] = []
        self.thinking_signature: Optional[str] = None
        
        # Message Buffer
        self.message_id: Optional[str] = None
        self.message_parts: List[str] = []

        # ── Tool Progress Tracking ──────────────────────────────────────
        # Counts and timing for the Signal Flow UI
        self._tool_count: int = 0
        self._tool_category_counts: Dict[str, int] = {}
        self._current_tool_start_time: Optional[float] = None
        self._build_phase_start: Optional[float] = None

    def process_event(self, event_type: str, data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Process an incoming streaming event and optionally return an atomic event.

        Args:
            event_type: The raw AG-UI event type (e.g., 'tool_call_start', 'message_chunk')
            data: The event payload

        Returns:
            Tuple(new_event_type, transformed_data) OR (None, None) if buffering.
        """

        # --- Skip II-Agent format "tool_call" events with status field ---
        # agent.py emits BOTH II-Agent format (via adapter methods) AND AG-UI format.
        # We only process AG-UI format (tool_call_start/args/end) to avoid duplicates.
        # II-Agent format tool_call events have a "status" field (start/delta/stop).
        if event_type == "tool_call" and data.get("status") in ("start", "delta", "stop"):
            return None, None  # Skip - we'll handle the AG-UI format instead

        # --- Skip duplicate II-Agent format "tool_result" events ---
        # agent.py emits adapter.tool_result() (has "status" and "tool_display_name")
        # AND _make_event("tool_result") (has "thread_id" and "tool_input")
        # We prefer the _make_event format which has more complete data.
        if event_type == "tool_result" and "status" in data and "tool_display_name" in data:
            return None, None  # Skip - we'll handle the other tool_result event

        # --- Skip II-Agent format thinking events ---
        # agent.py emits adapter.thinking_xxx() (event type "thinking")
        # AND _make_event("reasoning_xxx") (event type "reasoning_*")
        # We only process AG-UI format (reasoning_*) to avoid duplicates.
        if event_type == "thinking":
            return None, None  # Skip - we handle reasoning_* events instead

        # --- Tool Call Buffering ---
        if event_type == "tool_call_start":
            self._flush_message_if_needed() # Ensure interleaved messages are flushed
            self.tool_id = data.get("toolCallId") or data.get("id")
            self.tool_name = data.get("toolName") or data.get("toolCallName") or data.get("name")
            self.tool_input_parts = []
            return None, None # Start buffering
            
        elif event_type == "tool_call_args":
            delta = data.get("delta", "")
            if delta and self.tool_id:
                 self.tool_input_parts.append(delta)
            return None, None # Continue buffering

        elif event_type == "tool_call_end":
            # Finalize and emit atomic TOOL_CALL
            full_input_str = "".join(self.tool_input_parts)
            
            # Try to parse JSON to ensure validity, but send as dict/str as per adapter expectation
            try:
                # Some tools might send partial JSON or empty string if no args
                input_json = json.loads(full_input_str) if full_input_str else {}
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse tool input JSON: {full_input_str}")
                input_json = {"raw_input": full_input_str}

            # Deferred import to avoid circular dependency with event_adapter.py
            from backend.app.agent.event_adapter import humanize_tool_name, normalize_tool_name

            # Normalize tool name for frontend TOOL enum compatibility
            # Backend uses snake_case (e.g., "todo_write"), frontend expects specific values (e.g., "TodoWrite")
            normalized_name = normalize_tool_name(self.tool_name or "")

            # ── Tool Progress Tracking ──────────────────────────────────
            now = time.time()
            self._tool_count += 1
            if self._build_phase_start is None:
                self._build_phase_start = now
            self._current_tool_start_time = now

            # Categorize the tool for Signal Rail stats
            category = self._categorize_tool(normalized_name)
            self._tool_category_counts[category] = self._tool_category_counts.get(category, 0) + 1

            atomic_data = {
                "tool_call_id": self.tool_id,
                "tool_name": normalized_name,  # Normalized for frontend TOOL enum matching
                "tool_display_name": humanize_tool_name(self.tool_name or ""),
                "tool_input": input_json,  # Adapter can handle dict or str
                # ── Timing metadata for Signal Flow UI ──────────────────
                "started_at": now,
                "tool_stats": {
                    "total_tools_called": self._tool_count,
                    "tools_by_category": dict(self._tool_category_counts),
                    "current_tool_index": self._tool_count - 1,
                    "build_phase_start_time": self._build_phase_start,
                },
            }
            
            # Reset tool buffer
            self.tool_id = None
            self.tool_name = None
            self.tool_input_parts = []
            
            return "tool_call", atomic_data


        # --- Thinking / Reasoning Buffering ---
        elif event_type in ["reasoning_start", "reasoning_message_start"]:
            self._flush_message_if_needed()
            self.thinking_id = data.get("messageId") or str(uuid4())
            self.thinking_parts = []
            return None, None
            
        elif event_type == "reasoning_message_content":
            delta = data.get("delta", "")
            if delta:
                self.thinking_parts.append(delta)
            return None, None
            
        elif event_type in ["reasoning_end", "reasoning_message_end"]:
            full_thought = "".join(self.thinking_parts)
            atomic_data = {
                "text": full_thought,
                "thinking_id": self.thinking_id,
                "status": "stop" # Signal completion if needed
            }
            
            self.thinking_id = None
            self.thinking_parts = []
            
            return "agent_thinking", atomic_data

        # --- Message / Response Buffering ---
        # Handle AG-UI format message events: "message_chunk" and "message"
        # - chat.py emits "message_chunk" events
        # - agent.py emits "message" events (with type: "chunk")
        # NOTE: We don't buffer "content" events because agent.py emits BOTH
        # "content" (II-Agent format) AND "message" (AG-UI format) for each chunk.
        # Buffering both would cause text duplication.
        elif event_type in ("message_chunk", "message"):
            # Extract delta from different field names used by different event sources
            delta = data.get("content") or data.get("delta", "") or data.get("text", "")
            self.message_id = data.get("id") or data.get("message_id") or self.message_id
            if delta:
                self.message_parts.append(delta)
            return None, None

        # --- II-Agent SSE Format Events ---
        # "content" events are II-Agent SSE format. When coming through WebSocket path,
        # they're duplicates of "message" events, so we skip them to avoid duplication.
        # The "message" event already captured the text above.
        elif event_type == "content":
            # Skip - the "message" event will capture the same content
            return None, None
            
        elif event_type == "complete": 
            # End of stream.
            # Do NOT flush here, because we can only return one event.
            # The caller (QueryHandler) is responsible for calling .flush() 
            # after the stream loop ends.
            pass 


        # --- Passthrough for other events ---
        return event_type, data

    def _flush_message_if_needed(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Check if there is a pending message to emit."""
        if self.message_parts:
            full_text = "".join(self.message_parts)
            data = {
                "text": full_text,
                "message_id": self.message_id or str(uuid4())
            }
            self.message_id = None
            self.message_parts = []
            return "agent_response", data
        return None

    @staticmethod
    def _categorize_tool(tool_name: str) -> str:
        """
        Categorize a normalized tool name into a high-level category.
        Must stay in sync with the frontend TOOL_CATEGORY_MAP in toolProgress.ts.
        """
        lower = tool_name.lower()

        # Read tools
        if tool_name in ("Read", "Glob", "LS", "ASTGrep", "lsp",
                         "pdf_text_extract", "view_image", "read_remote_image",
                         "mcp_filesystem_read", "mcp_codex_read", "TodoRead"):
            return "read"

        # Write tools
        if tool_name in ("Write", "Edit", "MultiEdit", "apply_patch",
                         "str_replace_based_edit_tool", "mcp_filesystem_write",
                         "mcp_codex_write", "TodoWrite",
                         "SlideWrite", "SlideEdit", "slide_apply_patch"):
            return "write"

        # Bash / Shell tools
        if lower.startswith("bash") or lower.startswith("shell_") or \
           tool_name in ("python_execute", "javascript_execute", "code_execute"):
            return "bash"

        # Browse tools
        if lower.startswith("browser_") or lower.startswith("mcp_browser") or \
           tool_name in ("web_visit", "web_visit_compress", "browser_use", "crawl"):
            return "browse"

        # Generate tools
        if tool_name in ("generate_image", "generate_video",
                         "generate_long_video_from_text", "generate_long_video_from_image",
                         "audio_transcribe", "generate_audio_response", "display_image",
                         "design_create", "design_edit",
                         "excalidraw_create", "excalidraw_batch_create",
                         "document_compile", "latex_compile"):
            return "generate"

        # Search tools
        if "search" in lower or tool_name in ("get_paper_details", "get_author_details",
                                               "get_author_papers"):
            return "search"

        # Deploy tools
        if tool_name in ("static_deploy", "register_deployment", "register_port"):
            return "deploy"

        # Agent tools
        if lower.startswith("sub_agent") or lower.startswith("codex") or \
           tool_name in ("deep_research", "reviewer_agent", "mcp_claude_code",
                         "browser_subagent", "design_document_agent"):
            return "agent"

        return "other"
    
    def flush(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Flush any remaining buffered content (e.g. at end of stream)."""
        events = []
        
        # Flush message
        msg_event = self._flush_message_if_needed()
        if msg_event:
            events.append(msg_event)
            
        # Flush thinking (if incomplete)
        if self.thinking_parts:
            full_thought = "".join(self.thinking_parts)
            events.append(("agent_thinking", {
                "text": full_thought,
                "thinking_id": self.thinking_id or str(uuid4())
            }))
            self.thinking_parts = []
            self.thinking_id = None
            
        # Flush tool (if incomplete - rare/error case)
        if self.tool_id:
             # Logic for incomplete tool? Ignore or emit partial.
             self.tool_input_parts = []
             self.tool_id = None

        return events
