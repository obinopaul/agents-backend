# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
II-Agent Frontend Event Adapter

Transforms AG-UI Protocol events to II-Agent frontend format.
Supports both SSE (chat mode) and WebSocket (agent mode).

Event Protocol Mapping:
----------------------
SSE Events (Chat Mode) - Backend -> Frontend:
- N/A -> `session`: Emit on session creation
- `message_chunk` -> `content` (status: delta): Rename + restructure
- N/A -> `content` (status: start): Emit before first chunk
- `reasoning_*` (5 events) -> `thinking` (status: delta): Simplify to single event
- `tool_call_start` -> `tool_call` (status: start): Rename + restructure
- `tool_call_args` -> `tool_call` (status: delta): Rename + restructure
- `tool_call_end` -> `tool_call` (status: stop): Rename + restructure
- `tool_result` -> `tool_result` (status: info): Add status field
- N/A -> `usage`: Track token usage
- N/A -> `complete` (status: done): Emit on stream end
- `error` -> `error`: Compatible (minor restructure)

WebSocket Events (Agent Mode) - Backend -> Frontend:
- `message_chunk` -> `agent_response`: Rename
- `reasoning_*` -> `agent_thinking`: Simplify
- `tool_call_*` -> `tool_call`: Merge lifecycle events
- `status` (type: processing) -> `status_update`: Rename
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.src.utils.json_utils import safe_json_serialize


# =============================================================================
# SSE Event Adapter (Chat Mode)
# =============================================================================

@dataclass
class IIAgentSSEAdapter:
    """
    Adapter for SSE chat streaming events.

    Transforms AG-UI Protocol events to II-Agent frontend SSE format.
    Tracks state across the stream for proper event lifecycle.
    """

    session_id: str
    model_id: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid4()))
    content_started: bool = False
    thinking_active: bool = False
    thinking_id: Optional[str] = None
    _start_time: float = field(default_factory=time.time)
    _input_tokens: int = 0
    _output_tokens: int = 0
    _cache_creation_tokens: int = 0
    _cache_read_tokens: int = 0

    def session_event(self, is_new: bool = True, name: Optional[str] = None) -> str:
        """
        Emit session event at stream start.

        This should be the first event emitted when a stream begins.

        Args:
            is_new: Whether this is a newly created session
            name: Optional session name (derived from first user message)
        """
        data = {
            "status": "created" if is_new else "existing",
            "session_id": self.session_id,
            "model_id": self.model_id,
            "message_id": self.message_id,
        }
        if name:
            data["name"] = name
        return self._make_sse("session", data)

    def content_start(self) -> str:
        """
        Emit content start event.

        Should be emitted before the first content chunk.
        """
        self.content_started = True
        return self._make_sse("content", {
            "status": "start",
            "message_id": self.message_id,
        })

    def content_delta(self, delta: str) -> str:
        """
        Emit content delta event.

        Args:
            delta: The text chunk to stream
        """
        return self._make_sse("content", {
            "status": "delta",
            "delta": delta,
            "message_id": self.message_id,
        })

    def content_stop(self) -> str:
        """Emit content stop event when text streaming completes."""
        return self._make_sse("content", {
            "status": "stop",
            "message_id": self.message_id,
        })

    def thinking_start(self) -> str:
        """
        Emit thinking/reasoning start event.

        Consolidates AG-UI's reasoning_start and reasoning_message_start.
        """
        self.thinking_active = True
        self.thinking_id = f"thinking-{uuid4().hex[:8]}"
        return self._make_sse("thinking", {
            "status": "start",
            "thinking_id": self.thinking_id,
        })

    def thinking_delta(self, delta: str, signature: Optional[str] = None) -> str:
        """
        Emit thinking/reasoning delta event.

        Consolidates AG-UI's reasoning_message_content.

        Args:
            delta: The reasoning text chunk
            signature: Optional signature for extended thinking (Anthropic)
        """
        data: Dict[str, Any] = {
            "status": "delta",
            "delta": delta,
            "thinking_id": self.thinking_id,
        }
        if signature:
            data["signature"] = signature
        return self._make_sse("thinking", data)

    def thinking_stop(self) -> str:
        """
        Emit thinking/reasoning stop event.

        Consolidates AG-UI's reasoning_message_end and reasoning_end.
        """
        thinking_id = self.thinking_id
        self.thinking_active = False
        self.thinking_id = None
        return self._make_sse("thinking", {
            "status": "stop",
            "thinking_id": thinking_id,
        })

    def tool_call_start(self, tool_id: str, tool_name: str) -> str:
        """
        Emit tool call start event.

        Args:
            tool_id: Unique identifier for this tool call
            tool_name: Name of the tool being called
        """
        return self._make_sse("tool_call", {
            "status": "start",
            "id": tool_id,
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "tool_display_name": humanize_tool_name(tool_name),
            "type": "function",
        })

    def tool_call_delta(self, tool_id: str, delta: str) -> str:
        """
        Emit tool call arguments delta.

        Args:
            tool_id: Identifier of the tool call
            delta: Arguments chunk (JSON string fragment)
        """
        return self._make_sse("tool_call", {
            "status": "delta",
            "id": tool_id,
            "delta": delta,
        })

    def tool_call_stop(
        self,
        tool_id: str,
        tool_name: str,
        input_json: str
    ) -> str:
        """
        Emit tool call stop event.

        Args:
            tool_id: Identifier of the tool call
            tool_name: Name of the tool
            input_json: Complete JSON string of tool arguments
        """
        return self._make_sse("tool_call", {
            "status": "stop",
            "id": tool_id,
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "tool_display_name": humanize_tool_name(tool_name),
            "tool_input": input_json,
        })

    def tool_result(
        self,
        tool_id: str,
        tool_name: str,
        output: Any,  # Can be str or List[Dict] (for images)
        is_error: bool = False
    ) -> str:
        """
        Emit tool result event.

        Args:
            tool_id: Identifier of the tool call
            tool_name: Name of the tool
            output: Tool execution result
            is_error: Whether the result is an error
        """
        return self._make_sse("tool_result", {
            "status": "info",
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "tool_display_name": humanize_tool_name(tool_name),
            "result": output,
            "is_error": is_error,
        })

    def usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_creation: int = 0,
        cache_read: int = 0
    ) -> str:
        """
        Emit usage statistics event.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_creation: Tokens used for cache creation
            cache_read: Tokens read from cache
        """
        # Update internal counters
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cache_creation_tokens = cache_creation
        self._cache_read_tokens = cache_read

        return self._make_sse("usage", {
            "status": "info",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "total_tokens": input_tokens + output_tokens,
        })

    def complete(
        self,
        finish_reason: str = "end_turn",
        elapsed_ms: Optional[int] = None
    ) -> str:
        """
        Emit completion event.

        Args:
            finish_reason: Reason for completion (end_turn, tool_use, etc.)
            elapsed_ms: Time elapsed in milliseconds (auto-calculated if not provided)
        """
        if elapsed_ms is None:
            elapsed_ms = int((time.time() - self._start_time) * 1000)

        return self._make_sse("complete", {
            "status": "done",
            "message_id": self.message_id,
            "finish_reason": finish_reason,
            "elapsed_ms": elapsed_ms,
            "usage": {
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "total_tokens": self._input_tokens + self._output_tokens,
            } if self._input_tokens or self._output_tokens else None,
        })

    def error(self, message: str, code: str = "streaming_error") -> str:
        """
        Emit error event.

        Args:
            message: Error message
            code: Error code identifier
        """
        return self._make_sse("error", {
            "status": "error",
            "error": message,
            "code": code,
            "message_id": self.message_id,
        })

    def status_update(self, status_type: str, message: str, **kwargs) -> str:
        """
        Emit status update event.

        Args:
            status_type: Type of status (processing, sandbox_ready, etc.)
            message: Human-readable status message
            **kwargs: Additional status data
        """
        data = {
            "status": "info",
            "type": status_type,
            "message": message,
            **kwargs
        }
        return self._make_sse("status", data)

    def tool_progress(
        self,
        tool_id: str,
        tool_name: str,
        progress_percentage: int,
        status_message: str,
        current_step: Optional[int] = None,
        total_steps: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Emit tool progress event for long-running tools.

        This event allows the frontend to display progress indicators
        for tools that take significant time to complete.

        Args:
            tool_id: Tool call identifier
            tool_name: Internal tool name
            progress_percentage: Completion percentage (0-100)
            status_message: Human-readable progress status
            current_step: Current step number (optional)
            total_steps: Total number of steps (optional)
            metadata: Additional tool-specific metadata
        """
        # Import here to avoid circular dependency
        from backend.app.agent.event_adapter import humanize_tool_name

        data = {
            "status": "progress",
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "tool_display_name": humanize_tool_name(tool_name),
            "progress_percentage": min(100, max(0, progress_percentage)),
            "status_message": status_message,
        }

        if current_step is not None:
            data["current_step"] = current_step
        if total_steps is not None:
            data["total_steps"] = total_steps
        if metadata:
            data["metadata"] = metadata

        return self._make_sse("tool_progress", data)

    def interrupt(
        self,
        interrupt_id: str,
        content: str,
        options: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Emit interrupt event for Human-in-the-Loop.

        Args:
            interrupt_id: Unique identifier for this interrupt
            content: Message to display to user
            options: List of options ({text: str, value: str})
            context: Additional context data
        """
        data = {
            "status": "interrupt",
            "id": interrupt_id,
            "content": content,
            "options": options,
            "session_id": self.session_id,
        }
        if context:
            data["context"] = context
        return self._make_sse("interrupt", data)

    def agent_initialized(
        self,
        sandbox_id: Optional[str] = None,
        vscode_url: Optional[str] = None,
        mcp_url: Optional[str] = None,
        codex_url: Optional[str] = None,
        design_url: Optional[str] = None,
        latex_url: Optional[str] = None,
        excalidraw_url: Optional[str] = None,
        graphiti_url: Optional[str] = None,
        start_type: str = "cold_start",
    ) -> str:
        """
        Emit agent_initialized event with all sandbox URLs.

        This consolidated event is expected by the II-Agent frontend to set up
        the agent UI and store all available sandbox service URLs.

        Args:
            sandbox_id: Sandbox identifier
            vscode_url: VS Code server URL (port 9000) for code editing
            mcp_url: MCP tool server URL (port 6060) for tool execution
            codex_url: Codex SSE server URL for complex coding tasks
            design_url: Design MCP server URL (port 6002) for Draw.io diagrams
            latex_url: LaTeX editor URL (port 9001) for document editing
            excalidraw_url: Excalidraw URL (port 6003) for diagram creation
            graphiti_url: Graphiti MCP URL (port 8500) for Knowledge Graph
            start_type: "cold_start" or "warm_start" indicating sandbox creation type
        """
        # Build data dict with only non-None URLs to keep payload clean
        data: Dict[str, Any] = {
            "status": "initialized",
            "session_id": self.session_id,
            "start_type": start_type,
        }

        # Add sandbox_id if available
        if sandbox_id:
            data["sandbox_id"] = sandbox_id

        # Add each URL only if it has a value (avoids null clutter in payload)
        if vscode_url:
            data["vscode_url"] = vscode_url
        if mcp_url:
            data["mcp_url"] = mcp_url
        if codex_url:
            data["codex_url"] = codex_url
        if design_url:
            data["design_url"] = design_url
        if latex_url:
            data["latex_url"] = latex_url
        if excalidraw_url:
            data["excalidraw_url"] = excalidraw_url
        if graphiti_url:
            data["graphiti_url"] = graphiti_url

        return self._make_sse("agent_initialized", data)

    @staticmethod
    def _make_sse(event_type: str, data: dict) -> str:
        """Create SSE formatted string with safe serialization."""
        json_data = safe_json_serialize(data)
        return f"event: {event_type}\ndata: {json_data}\n\n"

    # =========================================================================
    # AG-UI to II-Agent Event Transformation
    # =========================================================================

    def transform_ag_ui_event(self, event_type: str, data: dict) -> Optional[str]:
        """
        Transform an AG-UI Protocol event to II-Agent SSE format.

        Args:
            event_type: AG-UI event type
            data: Event data dictionary

        Returns:
            II-Agent formatted SSE string, or None if event should be skipped
        """
        # Message content events
        if event_type in ("message", "message_chunk"):
            content = data.get("content", "")
            if content:
                # Emit content_start if this is the first chunk
                result = ""
                if not self.content_started:
                    result = self.content_start()
                result += self.content_delta(content)
                return result
            return None

        # Reasoning events - consolidate into single thinking event
        if event_type == "reasoning_start":
            return self.thinking_start()

        if event_type == "reasoning_message_start":
            # Already handled by reasoning_start
            if not self.thinking_active:
                return self.thinking_start()
            return None

        if event_type == "reasoning_message_content":
            delta = data.get("delta", "")
            if delta:
                return self.thinking_delta(delta, data.get("signature"))
            return None

        if event_type in ("reasoning_message_end", "reasoning_end"):
            if self.thinking_active:
                return self.thinking_stop()
            return None

        # Tool call events
        if event_type == "tool_call_start":
            tool_id = data.get("toolCallId") or data.get("id", "")
            tool_name = data.get("toolCallName") or data.get("name", "")
            return self.tool_call_start(tool_id, tool_name)

        if event_type == "tool_call_args":
            tool_id = data.get("toolCallId") or data.get("id", "")
            delta = data.get("delta", "")
            if delta:
                return self.tool_call_delta(tool_id, delta)
            return None

        if event_type == "tool_call_end":
            tool_id = data.get("toolCallId") or data.get("id", "")
            tool_name = data.get("toolCallName") or data.get("name", "")
            # Get accumulated input from data if available
            input_json = data.get("input", "{}")
            return self.tool_call_stop(tool_id, tool_name, input_json)

        # Tool result
        if event_type == "tool_result":
            tool_id = data.get("toolCallId") or data.get("tool_call_id", "")
            tool_name = data.get("toolName") or data.get("name", "")
            output = data.get("content") or data.get("output", "")
            is_error = data.get("is_error", False)
            return self.tool_result(tool_id, tool_name, str(output), is_error)

        # Tool progress events (for long-running tools)
        if event_type == "tool_progress":
            tool_id = data.get("tool_call_id", "")
            tool_name = data.get("tool_name", "")
            progress = data.get("progress_percentage", 0)
            status_message = data.get("status_message", "")
            current_step = data.get("current_step")
            total_steps = data.get("total_steps")
            metadata = data.get("metadata")
            return self.tool_progress(
                tool_id=tool_id,
                tool_name=tool_name,
                progress_percentage=progress,
                status_message=status_message,
                current_step=current_step,
                total_steps=total_steps,
                metadata=metadata
            )

        # Status events
        if event_type == "status":
            status_type = data.get("type", "info")
            message = data.get("message", "")
            # Pass through additional data
            extra = {k: v for k, v in data.items() if k not in ("type", "message")}
            return self.status_update(status_type, message, **extra)

        # Error events
        if event_type == "error":
            message = data.get("error") or data.get("message", "Unknown error")
            code = data.get("code", "error")
            return self.error(message, code)

        # Interrupt events - pass through with transformation
        if event_type == "interrupt":
            return self._make_sse("interrupt", {
                "status": "interrupt",
                "id": data.get("id", f"interrupt-{uuid4().hex[:8]}"),
                "content": data.get("content", ""),
                "options": data.get("options", []),
                "context": data.get("context"),
                "session_id": self.session_id,
            })

        # Sub-agent completion events
        if event_type == "sub_agent_complete":
            return self._make_sse("sub_agent_complete", {
                "status": "info",
                "text": data.get("text") or data.get("output", ""),
                "chain_name": data.get("chain_name", ""),
                "thread_id": data.get("thread_id", self.session_id),
            })

        # Pass through unknown events as-is
        return self._make_sse(event_type, data)


# =============================================================================
# Tool Display Name Utilities
# =============================================================================

# Mapping of internal tool names to human-readable display names
TOOL_DISPLAY_NAMES: Dict[str, str] = {
    # =========================================================================
    # Browser Tools (tool_server/tools/browser)
    # =========================================================================
    "browser_click": "Clicking Element",
    "browser_wait": "Waiting for Element",
    "browser_view_interactive_elements": "Viewing Interactive Elements",
    "browser_scroll_down": "Scrolling Down",
    "browser_scroll_up": "Scrolling Up",
    "browser_switch_tab": "Switching Tab",
    "browser_open_new_tab": "Opening New Tab",
    "browser_get_select_options": "Getting Select Options",
    "browser_select_dropdown_option": "Selecting Dropdown Option",
    "browser_navigation": "Navigating Browser",
    "browser_restart": "Restarting Browser",
    "browser_enter_text": "Entering Text",
    "browser_press_key": "Pressing Key",
    "browser_drag": "Dragging Element",
    "browser_enter_multi_texts": "Entering Multiple Texts",
    "browser_use": "Using Browser",

    # =========================================================================
    # Shell Tools (tool_server/tools/shell)
    # =========================================================================
    "shell_init": "Initializing Shell",
    "shell_run_command": "Running Command",
    "shell_view": "Viewing Terminal",
    "shell_stop_command": "Stopping Command",
    "shell_list": "Listing Shells",
    "shell_write_to_process": "Writing to Process",
    "bash": "Running Command",
    "shell_execute": "Executing Shell Command",

    # =========================================================================
    # File System Tools (tool_server/tools/file_system)
    # =========================================================================
    "file_read": "Reading File",
    "file_write": "Writing File",
    "file_edit": "Editing File",
    "apply_patch": "Applying Patch",
    "str_replace_editor": "Replacing Text",
    "ast_grep": "AST Search",
    "grep": "Searching Content",
    "lsp": "Language Server",
    "read": "Reading File",
    "write": "Writing File",
    "edit": "Editing File",
    "list_dir": "Listing Directory",
    "glob": "Finding Files",

    # =========================================================================
    # Web Tools (tool_server/tools/web)
    # =========================================================================
    "web_search": "Searching Web",
    "web_visit": "Visiting Website",
    "web_visit_compress": "Visiting Website",
    "image_search": "Searching Images",
    "read_remote_image": "Reading Remote Image",
    "web_batch_search": "Batch Web Search",
    "tavily_search_results_json": "Searching Web (Tavily)",

    # =========================================================================
    # Media Tools (tool_server/tools/media)
    # =========================================================================
    "generate_video": "Generating Video",
    "generate_image": "Generating Image",
    "image_generate": "Generating Image",
    "video_generate": "Generating Video",

    # =========================================================================
    # Dev Tools (tool_server/tools/dev)
    # =========================================================================
    "fullstack_init": "Initializing Project",
    "save_checkpoint": "Saving Checkpoint",
    "register_port": "Registering Port",
    "get_database_connection": "Connecting to Database",
    "fullstack_project_init": "Initializing Full-Stack Project",

    # =========================================================================
    # Slide System Tools (tool_server/tools/slide_system)
    # =========================================================================
    "slide_write": "Writing Slide",
    "slide_edit": "Editing Slide",
    "slide_apply_patch": "Patching Slide",
    "slide_template_init": "Initializing Slide Template",
    "presentation": "Managing Presentation",

    # =========================================================================
    # Document Tools (tool_server/tools/documents)
    # =========================================================================
    "document_template_init": "Initializing Document Template",
    "document_compile": "Compiling Document",
    "latex_compile": "Compiling LaTeX",

    # =========================================================================
    # Design Tools (tool_server/tools/design) - Draw.io
    # =========================================================================
    "design_init": "Initializing Design",
    "design_create": "Creating Design Element",
    "design_edit": "Editing Design",
    "design_get": "Getting Design",
    "design_export": "Exporting Design",

    # =========================================================================
    # Excalidraw Tools (tool_server/tools/excalidraw)
    # =========================================================================
    "excalidraw_init": "Initializing Excalidraw",
    "excalidraw_create": "Creating Element",
    "excalidraw_update": "Updating Element",
    "excalidraw_delete": "Deleting Element",
    "excalidraw_query": "Querying Canvas",
    "excalidraw_batch_create": "Batch Creating Elements",
    "excalidraw_group": "Grouping Elements",
    "excalidraw_ungroup": "Ungrouping Elements",
    "excalidraw_align": "Aligning Elements",
    "excalidraw_distribute": "Distributing Elements",
    "excalidraw_lock": "Locking Element",
    "excalidraw_unlock": "Unlocking Element",
    "excalidraw_resource": "Managing Resource",

    # =========================================================================
    # Productivity Tools (tool_server/tools/productivity)
    # =========================================================================
    "todo_read": "Reading Tasks",
    "todo_write": "Writing Tasks",

    # =========================================================================
    # Agent Tools (tool_server/tools/agent)
    # =========================================================================
    "message_user": "Messaging User",
    "return_control_to_user": "Returning Control",

    # =========================================================================
    # Academic/Research Tools (src/tools/academic)
    # =========================================================================
    "paper_search": "Searching Papers",
    "get_paper_details": "Getting Paper Details",
    "search_authors": "Searching Authors",
    "get_author_details": "Getting Author Details",
    "get_author_papers": "Getting Author Papers",
    "semantic_scholar_search": "Searching Semantic Scholar",
    "arxiv_search": "Searching arXiv",
    "arxiv_search_tool": "Searching arXiv",
    "pubmed_central": "Searching PubMed",
    "pubmed_search": "Searching PubMed",
    "google_scholar": "Searching Google Scholar",
    "semantic_scholar": "Searching Semantic Scholar",

    # =========================================================================
    # People & Company Search Tools (src/tools)
    # =========================================================================
    "people_search": "Searching People",
    "company_search": "Searching Companies",
    "mcp_search": "MCP Search",

    # =========================================================================
    # Crawl & Retrieval Tools (src/tools)
    # =========================================================================
    "crawl": "Crawling Website",
    "retriever": "Retrieving Documents",
    "human_feedback": "Requesting Feedback",

    # =========================================================================
    # TTS & Voice Tools (src/tools)
    # =========================================================================
    "tts": "Text to Speech",
    "volcengine_tts": "Generating Speech",
    "vapi_voice": "Voice Assistant",

    # =========================================================================
    # Vision Tools (agents/middleware)
    # =========================================================================
    "view_image": "Viewing Image",
    "reality_defender": "Analyzing Media",

    # =========================================================================
    # Memory & Summarization Tools (agents/middleware)
    # =========================================================================
    "agent_memory": "Managing Memory",
    "summarization": "Summarizing Content",
    "background_investigation": "Background Research",

    # =========================================================================
    # MCP Tools (generic MCP prefixed tools)
    # =========================================================================
    "mcp_codex_execute": "Running Codex",
    "mcp_codex_read": "Reading from Codex",
    "mcp_codex_write": "Writing to Codex",
    "mcp_claude_code": "Running Claude Code",
    "mcp_filesystem_read": "Reading Filesystem",
    "mcp_filesystem_write": "Writing to Filesystem",
    "mcp_browser_navigate": "Navigating Browser",
    "mcp_browser_click": "Clicking Element",
    "mcp_browser_type": "Typing Text",
    "mcp_browser_screenshot": "Taking Screenshot",

    # =========================================================================
    # Sub-agent & Task Tools
    # =========================================================================
    "sub_agent": "Delegating to Sub-Agent",
    "sub_agent_researcher": "Research Agent",
    "task": "Running Task",
    "codex_agent": "Codex Agent",
    "codex_delegate": "Delegating to Codex Agent",
    "design_document_agent": "Design Document Agent",
    "browser_subagent": "Browser Sub-Agent",
    "request_human_input": "Requesting Human Input",

    # =========================================================================
    # Code Execution Tools
    # =========================================================================
    "python_execute": "Executing Python",
    "javascript_execute": "Executing JavaScript",
    "code_execute": "Executing Code",

    # =========================================================================
    # Data Tools
    # =========================================================================
    "sql_query": "Running SQL Query",
    "dataframe_operation": "Processing Data",
    "plot_chart": "Creating Chart",
    "export_data": "Exporting Data",
    "spreadsheet": "Managing Spreadsheet",
    "upload_file": "Uploading File",

    # =========================================================================
    # Sequential Thinking
    # =========================================================================
    "sequential_thinking": "Thinking",

    # =========================================================================
    # Additional Browser Tools (from frontend TOOL enum)
    # =========================================================================
    "browser_wait_for": "Waiting for Condition",
    "browser_close": "Closing Browser",
    "browser_console_messages": "Reading Console",
    "browser_evaluate": "Evaluating Script",
    "browser_handle_dialog": "Handling Dialog",
    "browser_hover": "Hovering Element",
    "browser_navigate": "Navigating",
    "browser_network_requests": "Viewing Network",
    "browser_select_option": "Selecting Option",
    "browser_snapshot": "Taking Snapshot",
    "browser_take_screenshot": "Taking Screenshot",
    "browser_type": "Typing Text",
    "browser_tab_close": "Closing Tab",
    "browser_tab_list": "Listing Tabs",
    "browser_tab_new": "Opening Tab",
    "browser_tab_select": "Selecting Tab",
    "browser_mouse_click_xy": "Clicking at Coordinates",
    "browser_mouse_drag_xy": "Dragging to Coordinates",
    "browser_mouse_move_xy": "Moving Mouse",

    # =========================================================================
    # Additional Shell Tools (from frontend TOOL enum)
    # =========================================================================
    "shell_exec": "Executing Command",
    "shell_kill_process": "Killing Process",
    "shell_wait": "Waiting for Command",

    # =========================================================================
    # Bash Tool Variants (uppercase from frontend)
    # =========================================================================
    "Bash": "Running Command",
    "BashInit": "Initializing Shell",
    "BashView": "Viewing Terminal",
    "BashStop": "Stopping Command",
    "BashKill": "Killing Process",
    "BashList": "Listing Sessions",
    "BashWriteToProcess": "Writing to Process",

    # =========================================================================
    # File Tool Variants (uppercase from frontend)
    # =========================================================================
    "Read": "Reading File",
    "Write": "Writing File",
    "Edit": "Editing File",
    "LS": "Listing Directory",
    "Glob": "Finding Files",
    "ASTGrep": "AST Search",
    "MultiEdit": "Multiple Edits",
    "str_replace_based_edit_tool": "String Replace",

    # =========================================================================
    # Task & Agent Tools (from frontend)
    # =========================================================================
    "Task": "Running Task",
    "reviewer_agent": "Reviewing",
    "deep_research": "Deep Research",

    # =========================================================================
    # Slide Tools (uppercase from frontend)
    # =========================================================================
    "SlideWrite": "Writing Slide",
    "SlideEdit": "Editing Slide",
    "slide_deck_init": "Initializing Slides",
    "slide_deck_complete": "Completing Slides",

    # =========================================================================
    # Todo Tools (uppercase from frontend)
    # =========================================================================
    "TodoWrite": "Writing Tasks",
    "TodoRead": "Reading Tasks",

    # =========================================================================
    # Media & Content Tools (from frontend)
    # =========================================================================
    "generate_long_video_from_text": "Generating Long Video",
    "generate_long_video_from_image": "Generating Video from Image",
    "generate_audio_response": "Generating Audio",
    "audio_transcribe": "Transcribing Audio",
    "pdf_text_extract": "Extracting PDF Text",
    "display_image": "Displaying Image",
    "list_html_links": "Listing HTML Links",

    # =========================================================================
    # Deployment Tools (from frontend)
    # =========================================================================
    "static_deploy": "Deploying Static Site",
    "register_deployment": "Registering Deployment",
    "complete": "Completing",

    # =========================================================================
    # Additional MCP & Codex Tools (from frontend)
    # =========================================================================
    "codex_execute": "Running Codex",
    "codex_review": "Reviewing with Codex",
    "mcp_codex_review": "Codex Review",
    "mcp_codex-as-mcp_codex_execute": "Running Codex",
    "mcp_codex-as-mcp_codex_review": "Reviewing with Codex",
    "mcp_tool": "MCP Tool",
    "get_openai_api_key": "Getting API Key",

    # =========================================================================
    # Background Middleware Tools (background_middleware/tools.py)
    # =========================================================================
    "background_task": "Spawning Background Task",
    "wait_for_subagents": "Waiting for Subagents",
    "task_progress": "Checking Task Progress",

    # =========================================================================
    # Persistent Task Middleware Tools (persistent_task_middleware.py)
    # =========================================================================
    "view_tasks": "Viewing Tasks",
    "create_tasks": "Creating Tasks",
    "update_tasks": "Updating Tasks",
    "delete_tasks": "Deleting Tasks",
    "clear_all_tasks": "Clearing All Tasks",

    # =========================================================================
    # Sandbox Spreadsheet & Upload Tools (src/tools)
    # =========================================================================
    "sb_spreadsheet": "Managing Spreadsheet",
    "sb_upload_file": "Uploading File",
}


# =============================================================================
# Tool Name Normalization Map (Backend -> Frontend TOOL Enum)
# =============================================================================
# This maps backend tool names (snake_case) to frontend TOOL enum values.
# The frontend handleClickAction switch statement matches on these values.
# If a tool is not in this map, the original tool name is used.

TOOL_NAME_MAP: Dict[str, str] = {
    # =========================================================================
    # Productivity Tools (PascalCase in frontend)
    # =========================================================================
    "todo_write": "TodoWrite",
    "todo_read": "TodoRead",

    # =========================================================================
    # File System Tools (PascalCase in frontend)
    # =========================================================================
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "file_read": "Read",
    "file_write": "Write",
    "file_edit": "Edit",
    "list_dir": "LS",
    "ls": "LS",
    "glob": "Glob",
    "ast_grep": "ASTGrep",
    "grep": "ASTGrep",
    "multi_edit": "MultiEdit",
    "apply_patch": "apply_patch",
    "str_replace_editor": "str_replace_based_edit_tool",
    "str_replace_based_edit_tool": "str_replace_based_edit_tool",
    "lsp": "lsp",

    # =========================================================================
    # Shell/Bash Tools (PascalCase in frontend)
    # =========================================================================
    "bash": "Bash",
    "shell_init": "BashInit",
    "shell_run_command": "Bash",
    "shell_view": "BashView",
    "shell_stop_command": "BashStop",
    "shell_list": "BashList",
    "shell_write_to_process": "BashWriteToProcess",
    "shell_execute": "Bash",
    "bash_init": "BashInit",
    "bash_view": "BashView",
    "bash_stop": "BashStop",
    "bash_kill": "BashKill",
    "bash_list": "BashList",
    "bash_write_to_process": "BashWriteToProcess",
    "shell_exec": "shell_exec",
    "shell_kill_process": "shell_kill_process",
    "shell_wait": "shell_wait",

    # =========================================================================
    # Slide Tools (PascalCase in frontend)
    # =========================================================================
    "slide_write": "SlideWrite",
    "slide_edit": "SlideEdit",
    "slide_apply_patch": "slide_apply_patch",
    "slide_template_init": "slide_template_init",
    "slide_deck_init": "slide_deck_init",
    "slide_deck_complete": "slide_deck_complete",
    "presentation": "presentation",

    # =========================================================================
    # Task & Agent Tools
    # =========================================================================
    "task": "Task",
    "sub_agent": "sub_agent",
    "sub_agent_researcher": "sub_agent_researcher",
    "design_document_agent": "design_document_agent",
    "reviewer_agent": "reviewer_agent",
    "codex_agent": "codex_agent",
    "codex_delegate": "codex_delegate",
    "browser_subagent": "browser_subagent",
    "request_human_input": "request_human_input",

    # =========================================================================
    # Browser Tools (snake_case - same in both)
    # =========================================================================
    "browser_use": "browser_use",
    "browser_click": "browser_click",
    "browser_close": "browser_close",
    "browser_console_messages": "browser_console_messages",
    "browser_drag": "browser_drag",
    "browser_evaluate": "browser_evaluate",
    "browser_handle_dialog": "browser_handle_dialog",
    "browser_hover": "browser_hover",
    "browser_navigate": "browser_navigate",
    "browser_network_requests": "browser_network_requests",
    "browser_press_key": "browser_press_key",
    "browser_select_option": "browser_select_option",
    "browser_snapshot": "browser_snapshot",
    "browser_take_screenshot": "browser_take_screenshot",
    "browser_type": "browser_type",
    "browser_wait_for": "browser_wait_for",
    "browser_tab_close": "browser_tab_close",
    "browser_tab_list": "browser_tab_list",
    "browser_tab_new": "browser_tab_new",
    "browser_tab_select": "browser_tab_select",
    "browser_mouse_click_xy": "browser_mouse_click_xy",
    "browser_mouse_drag_xy": "browser_mouse_drag_xy",
    "browser_mouse_move_xy": "browser_mouse_move_xy",
    "browser_navigation": "browser_navigation",
    "browser_wait": "browser_wait",
    "browser_view_interactive_elements": "browser_view_interactive_elements",
    "browser_scroll_down": "browser_scroll_down",
    "browser_scroll_up": "browser_scroll_up",
    "browser_switch_tab": "browser_switch_tab",
    "browser_open_new_tab": "browser_open_new_tab",
    "browser_get_select_options": "browser_get_select_options",
    "browser_select_dropdown_option": "browser_select_dropdown_option",
    "browser_restart": "browser_restart",
    "browser_enter_text": "browser_enter_text",
    "browser_enter_multi_texts": "browser_enter_multi_texts",

    # =========================================================================
    # Web Tools
    # =========================================================================
    "web_search": "web_search",
    "web_batch_search": "web_batch_search",
    "image_search": "image_search",
    "web_visit": "web_visit",
    "web_visit_compress": "web_visit_compress",
    "tavily_search_results_json": "tavily_search_results_json",

    # =========================================================================
    # Media Tools
    # =========================================================================
    "generate_image": "generate_image",
    "generate_video": "generate_video",
    "image_generate": "generate_image",
    "video_generate": "generate_video",
    "generate_long_video_from_text": "generate_long_video_from_text",
    "generate_long_video_from_image": "generate_long_video_from_image",
    "generate_audio_response": "generate_audio_response",
    "audio_transcribe": "audio_transcribe",
    "pdf_text_extract": "pdf_text_extract",
    "display_image": "display_image",
    "list_html_links": "list_html_links",
    "read_remote_image": "read_remote_image",

    # =========================================================================
    # Dev & Deployment Tools
    # =========================================================================
    "fullstack_init": "fullstack_project_init",
    "fullstack_project_init": "fullstack_project_init",
    "save_checkpoint": "save_checkpoint",
    "register_port": "register_port",
    "get_database_connection": "get_database_connection",
    "get_openai_api_key": "get_openai_api_key",
    "static_deploy": "static_deploy",
    "register_deployment": "register_deployment",
    "complete": "complete",

    # =========================================================================
    # Document Tools
    # =========================================================================
    "document_template_init": "document_template_init",
    "document_compile": "document_compile",
    "latex_compile": "latex_compile",

    # =========================================================================
    # Design Tools (Draw.io)
    # =========================================================================
    "design_init": "design_init",
    "design_create": "design_create",
    "design_edit": "design_edit",
    "design_get": "design_get",
    "design_export": "design_export",

    # =========================================================================
    # Excalidraw Tools
    # =========================================================================
    "excalidraw_init": "excalidraw_init",
    "excalidraw_create": "excalidraw_create",
    "excalidraw_update": "excalidraw_update",
    "excalidraw_delete": "excalidraw_delete",
    "excalidraw_query": "excalidraw_query",
    "excalidraw_batch_create": "excalidraw_batch_create",
    "excalidraw_group": "excalidraw_group",
    "excalidraw_ungroup": "excalidraw_ungroup",
    "excalidraw_align": "excalidraw_align",
    "excalidraw_distribute": "excalidraw_distribute",
    "excalidraw_lock": "excalidraw_lock",
    "excalidraw_unlock": "excalidraw_unlock",
    "excalidraw_resource": "excalidraw_resource",

    # =========================================================================
    # Academic/Research Tools
    # =========================================================================
    "paper_search": "paper_search",
    "get_paper_details": "get_paper_details",
    "search_authors": "search_authors",
    "get_author_details": "get_author_details",
    "get_author_papers": "get_author_papers",
    "semantic_scholar_search": "semantic_scholar_search",
    "arxiv_search": "arxiv_search",
    "arxiv_search_tool": "arxiv_search_tool",
    "pubmed_central": "pubmed_central",
    "pubmed_search": "pubmed_search",
    "google_scholar": "google_scholar",
    "semantic_scholar": "semantic_scholar",
    "deep_research": "deep_research",

    # =========================================================================
    # People & Company Search Tools
    # =========================================================================
    "people_search": "people_search",
    "company_search": "company_search",
    "mcp_search": "mcp_search",

    # =========================================================================
    # Crawl & Retrieval Tools
    # =========================================================================
    "retriever": "retriever",
    "human_feedback": "human_feedback",

    # =========================================================================
    # TTS & Voice Tools
    # =========================================================================
    "tts": "tts",
    "volcengine_tts": "volcengine_tts",
    "vapi_voice": "vapi_voice",

    # =========================================================================
    # Vision Tools
    # =========================================================================
    "view_image": "view_image",
    "reality_defender": "reality_defender",

    # =========================================================================
    # Memory & Summarization Tools
    # =========================================================================
    "agent_memory": "agent_memory",
    "summarization": "summarization",
    "background_investigation": "background_investigation",

    # =========================================================================
    # Code Execution Tools
    # =========================================================================
    "python_execute": "python_execute",
    "javascript_execute": "javascript_execute",
    "code_execute": "code_execute",

    # =========================================================================
    # Data Tools
    # =========================================================================
    "sql_query": "sql_query",
    "dataframe_operation": "dataframe_operation",
    "plot_chart": "plot_chart",
    "export_data": "export_data",
    "spreadsheet": "spreadsheet",
    "upload_file": "upload_file",

    # =========================================================================
    # Core Agent Tools
    # =========================================================================
    "sequential_thinking": "sequential_thinking",
    "message_user": "message_user",
    "return_control_to_user": "return_control_to_user",

    # =========================================================================
    # MCP & Codex Tools
    # =========================================================================
    "mcp_tool": "mcp_tool",
    "codex_execute": "codex_execute",
    "codex_review": "codex_review",
    "mcp_codex_execute": "mcp_codex_execute",
    "mcp_codex_review": "mcp_codex_review",
    "mcp_codex_read": "mcp_codex_read",
    "mcp_codex_write": "mcp_codex_write",
    "mcp_codex-as-mcp_codex_execute": "mcp_codex-as-mcp_codex_execute",
    "mcp_codex-as-mcp_codex_review": "mcp_codex-as-mcp_codex_review",
    "mcp_claude_code": "mcp_claude_code",
    "mcp_filesystem_read": "mcp_filesystem_read",
    "mcp_filesystem_write": "mcp_filesystem_write",
    "mcp_browser_navigate": "mcp_browser_navigate",
    "mcp_browser_click": "mcp_browser_click",
    "mcp_browser_type": "mcp_browser_type",
    "mcp_browser_screenshot": "mcp_browser_screenshot",

    # =========================================================================
    # Background Middleware Tools
    # =========================================================================
    "background_task": "background_task",
    "wait_for_subagents": "wait_for_subagents",
    "task_progress": "task_progress",

    # =========================================================================
    # Persistent Task Middleware Tools
    # =========================================================================
    "view_tasks": "view_tasks",
    "create_tasks": "create_tasks",
    "update_tasks": "update_tasks",
    "delete_tasks": "delete_tasks",
    "clear_all_tasks": "clear_all_tasks",

    # =========================================================================
    # Sandbox Tools
    # =========================================================================
    "sb_spreadsheet": "sb_spreadsheet",
    "sb_upload_file": "sb_upload_file",
}


def normalize_tool_name(tool_name: str) -> str:
    """
    Convert backend tool name to frontend TOOL enum value.

    This function maps backend snake_case tool names to the string values
    expected by the frontend TOOL enum and handleClickAction switch statement.

    Args:
        tool_name: Internal backend tool name (e.g., "todo_write", "read")

    Returns:
        Frontend-compatible tool name (e.g., "TodoWrite", "Read")
    """
    if not tool_name:
        return ""

    # Check explicit mapping first
    if tool_name in TOOL_NAME_MAP:
        return TOOL_NAME_MAP[tool_name]

    # Handle mcp_ prefix - check if base name is in map
    if tool_name.startswith("mcp_"):
        base_name = tool_name[4:]  # Remove "mcp_"
        if base_name in TOOL_NAME_MAP:
            return TOOL_NAME_MAP[base_name]

    # Return original name if no mapping found
    # This allows unknown tools to still flow through
    return tool_name


def humanize_tool_name(tool_name: str) -> str:
    """
    Convert tool name to human-readable display format.

    Priority:
    1. Check TOOL_DISPLAY_NAMES mapping
    2. Handle mcp_ prefix specially
    3. Fall back to title-casing the name

    Args:
        tool_name: Internal tool name (e.g., "web_search", "mcp_codex_execute")

    Returns:
        Human-readable name (e.g., "Searching Web", "Running Codex")
    """
    if not tool_name:
        return "Tool"

    # Check explicit mapping first
    if tool_name in TOOL_DISPLAY_NAMES:
        return TOOL_DISPLAY_NAMES[tool_name]

    # Handle mcp_ prefix
    if tool_name.startswith("mcp_"):
        # Remove mcp_ prefix and humanize the rest
        base_name = tool_name[4:]  # Remove "mcp_"
        if base_name in TOOL_DISPLAY_NAMES:
            return TOOL_DISPLAY_NAMES[base_name]
        # Title case with underscores replaced
        return base_name.replace("_", " ").title()

    # Default: title case with underscores replaced
    return tool_name.replace("_", " ").title()



from backend.app.agent.stream_buffer import StreamBuffer

# =============================================================================
# WebSocket Event Adapter (Agent Mode)
# =============================================================================

class IIAgentWebSocketAdapter:
    """
    Adapter for WebSocket agent events.

    Transforms AG-UI Protocol events to II-Agent WebSocket format.
    WebSocket events are emitted as (event_type, data) tuples.
    
    Now supports stateful buffering via StreamBuffer to ensure atomic events.
    """
    
    def __init__(self):
        self.buffer = StreamBuffer()

    # AG-UI to II-Agent WebSocket event type mapping


    # AG-UI to II-Agent WebSocket event type mapping
    EVENT_TYPE_MAP = {
        # Message events
        "message_chunk": "agent_response",
        "message": "agent_response",

        # Reasoning events - consolidate to agent_thinking
        "reasoning_start": "agent_thinking",
        "reasoning_message_start": None,  # Skip (merged into agent_thinking)
        "reasoning_message_content": "agent_thinking",
        "reasoning_message_end": None,  # Skip
        "reasoning_end": "agent_thinking",

        # Tool events (Buffered)
        "tool_call_start": "tool_call",
        "tool_call_args": "tool_call",
        "tool_call_end": "tool_call",
        
        # Tool events (Atomic)
        "tool_result": "tool_result",
        "tool_progress": "tool_progress",

        # Status events
        "status": "status_update",

        # Error/interrupt - keep same
        "error": "error",
        "interrupt": "interrupt",
        "agent_response_interrupted": "agent_response_interrupted",

        # Completion
        "complete": "complete",

        # Sub-agent events
        "sub_agent_complete": "sub_agent_complete",
        
        # Metrics & Ops
        "metrics_update": "metrics_update",
        "model_compact": "model_compact",
    }

    def process_event(self, ag_ui_event_type: str, data: dict) -> Tuple[Optional[str], Optional[dict]]:
        """
        Stateful processing: Buffers streams, emits atomic events.
        """
        # 1. Pass through buffer
        # StreamBuffer handles tool_call_*, reasoning_*, message_chunk
        # It returns (atomic_type, atomic_data) if ready, or (None,None) if buffering.
        # It returns (original_type, data) if it doesn't handle the type.
        buf_type, buf_data = self.buffer.process_event(ag_ui_event_type, data)
        
        if buf_type is None:
            return None, None # Buffering in progress
            
        # 2. If buffer produced an atomic event (tool_call, agent_thinking, agent_response),
        # return it directly. These match the II-Agent protocol.
        if buf_type in ["tool_call", "agent_thinking", "agent_response", "agent_response_interrupted", "metrics_update"]:
             return buf_type, buf_data

        # 3. For passthrough events, use the static transform logic
        # buf_type here is the original event type (e.g. "status", "error")
        return self.transform(buf_type, buf_data)
        
    @classmethod
    def transform(

        cls,
        ag_ui_event_type: str,
        data: dict
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        Transform AG-UI event to II-Agent WebSocket format.

        Args:
            ag_ui_event_type: AG-UI event type
            data: Event data dictionary

        Returns:
            Tuple of (event_type, content) for Socket.IO emission.
            Returns (None, None) if event should be skipped.
        """
        new_type = cls.EVENT_TYPE_MAP.get(ag_ui_event_type, ag_ui_event_type)

        if new_type is None:
            return None, None

        # Transform data based on event type
        new_data = cls._transform_data(ag_ui_event_type, new_type, data)
        return new_type, new_data

    @classmethod
    def _transform_data(
        cls,
        original_type: str,
        new_type: str,
        data: dict
    ) -> dict:
        """
        Transform event data to II-Agent WebSocket format.

        Args:
            original_type: Original AG-UI event type
            new_type: New II-Agent event type
            data: Original event data

        Returns:
            Transformed event data
        """
        if new_type == "agent_response":
            return {
                "text": data.get("content") or data.get("delta", ""),
                "message_id": data.get("id") or data.get("message_id"),
            }

        if new_type == "agent_thinking":
            # Handle different reasoning event types
            if original_type == "reasoning_start":
                return {
                    "status": "start",
                    "thinking_id": data.get("messageId"),
                }
            elif original_type == "reasoning_message_content":
                return {
                    "status": "delta",
                    "text": data.get("delta", ""),
                    "thinking_id": data.get("messageId"),
                }
            elif original_type == "reasoning_end":
                return {
                    "status": "stop",
                    "thinking_id": data.get("messageId"),
                }
            return {"text": data.get("delta", "")}

        if new_type == "tool_call":
            # Handle different tool call stages
            tool_name = data.get("toolName") or data.get("toolCallName") or data.get("name", "")
            tool_display_name = humanize_tool_name(tool_name)

            if original_type == "tool_call_start":
                return {
                    "status": "start",
                    "tool_name": tool_name,
                    "tool_display_name": tool_display_name,
                    "tool_call_id": data.get("toolCallId") or data.get("id", ""),
                }
            elif original_type == "tool_call_args":
                return {
                    "status": "delta",
                    "tool_call_id": data.get("toolCallId") or data.get("id", ""),
                    "tool_input": data.get("delta", ""),
                }
            elif original_type == "tool_call_end":
                return {
                    "status": "stop",
                    "tool_call_id": data.get("toolCallId") or data.get("id", ""),
                    "tool_name": tool_name,
                    "tool_display_name": tool_display_name,
                    "tool_input": data.get("input", ""),
                }
            return {
                "tool_name": tool_name,
                "tool_display_name": tool_display_name,
                "tool_call_id": data.get("toolCallId") or data.get("id", ""),
                "tool_input": data.get("delta") or data.get("input", ""),
            }

        if new_type == "tool_result":
            raw_tool_name = data.get("toolName") or data.get("tool_name") or data.get("name", "")
            # Normalize tool name so it matches the TOOL_CALL's normalized name
            # (e.g., "todo_write" → "TodoWrite", matching what StreamBuffer does for tool_call)
            tool_name = normalize_tool_name(raw_tool_name) if raw_tool_name else ""

            # Extract raw result — agent.py already unwraps ToolMessage objects
            # and MCP content blocks, so this is typically a string, dict, or list.
            raw_result = data.get("content") or data.get("result") or data.get("output", "")

            # ── Normalize result to a frontend-consumable value ──
            # The frontend expects result to be a string (either plain text
            # or a JSON string that it can JSON.parse). We handle each type:
            if isinstance(raw_result, dict) and "content" in raw_result:
                inner = raw_result["content"]
                if isinstance(inner, str) and inner.strip()[:1] in ('[', '{'):
                    # Unwrap JSON: {"content": "[{...}]"} → "[{...}]"
                    result = inner
                else:
                    # Keep as-is for HTML/object content (slides, etc.)
                    result = json.dumps(raw_result, default=str)
            elif isinstance(raw_result, (dict, list)):
                result = json.dumps(raw_result, default=str)
            else:
                result = raw_result

            return {
                "tool_call_id": data.get("toolCallId") or data.get("tool_call_id", ""),
                "tool_name": tool_name,
                "tool_display_name": humanize_tool_name(raw_tool_name) if raw_tool_name else "",
                "result": result,
                "is_error": data.get("is_error", False),
            }

        if new_type == "tool_progress":
            tool_name = data.get("tool_name", "")
            return {
                "tool_call_id": data.get("tool_call_id", ""),
                "tool_name": tool_name,
                "tool_display_name": humanize_tool_name(tool_name),
                "progress_percentage": data.get("progress_percentage", 0),
                "status_message": data.get("status_message", ""),
                "current_step": data.get("current_step"),
                "total_steps": data.get("total_steps"),
                "metadata": data.get("metadata"),
            }

        if new_type == "status_update":
            return {
                "status_type": data.get("type", "info"),
                "message": data.get("message", ""),
                **{k: v for k, v in data.items() if k not in ("type", "message")}
            }

        if new_type == "error":
            return {
                "error": data.get("error") or data.get("message", "Unknown error"),
                "code": data.get("code", "error"),
            }

        if new_type == "complete":
            result = {
                "status": "done",
                "message_id": data.get("message_id"),
                "finish_reason": data.get("finish_reason", "end_turn"),
            }
            # Include elapsed_ms if available
            if data.get("elapsed_ms") is not None:
                result["elapsed_ms"] = data.get("elapsed_ms")
            # Include usage statistics if available
            if data.get("usage"):
                result["usage"] = data.get("usage")
            return result

        if new_type == "sub_agent_complete":
            return {
                "text": data.get("text") or data.get("output", ""),
                "chain_name": data.get("chain_name", ""),
                "thread_id": data.get("thread_id", ""),
            }

        # Pass through other data as-is
        return data

    @classmethod
    def create_agent_initialized_event(
        cls,
        session_id: str,
        sandbox_id: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, dict]:
        """
        Create agent_initialized event for WebSocket.

        Args:
            session_id: Session identifier
            sandbox_id: Sandbox identifier if available
            **kwargs: Additional data (vscode_url, mcp_url, etc.)
        """
        return "agent_initialized", {
            "session_id": session_id,
            "sandbox_id": sandbox_id,
            **kwargs
        }

    @classmethod
    def create_complete_event(
        cls,
        session_id: str,
        finish_reason: str = "end_turn",
        **kwargs
    ) -> Tuple[str, dict]:
        """
        Create complete event for WebSocket.

        Args:
            session_id: Session identifier
            finish_reason: Reason for completion
            **kwargs: Additional data
        """
        return "complete", {
            "status": "done",
            "session_id": session_id,
            "finish_reason": finish_reason,
            **kwargs
        }


# =============================================================================
# Helper Functions
# =============================================================================

def create_sse_adapter(
    session_id: str,
    model_id: Optional[str] = None
) -> IIAgentSSEAdapter:
    """
    Factory function to create an SSE adapter.

    Args:
        session_id: Session/thread identifier
        model_id: Optional model identifier

    Returns:
        Configured IIAgentSSEAdapter instance
    """
    return IIAgentSSEAdapter(
        session_id=session_id,
        model_id=model_id
    )


def transform_sse_to_websocket(
    sse_event: str
) -> Optional[Tuple[str, dict]]:
    """
    Transform an SSE event string to WebSocket format.

    Parses the SSE format and transforms using IIAgentWebSocketAdapter.

    Args:
        sse_event: SSE formatted string (event: type\ndata: json\n\n)

    Returns:
        Tuple of (event_type, data) or None if parsing fails
    """
    try:
        lines = sse_event.strip().split('\n')
        event_type = None
        data = None

        for line in lines:
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data_str = line[5:].strip()
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = {'raw': data_str}

        if event_type and data:
            return IIAgentWebSocketAdapter.transform(event_type, data)

        return None
    except Exception:
        return None
