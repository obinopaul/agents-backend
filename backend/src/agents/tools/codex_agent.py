"""
Codex Agent - LangChain Tool for Codex SSE Event Streaming

This tool connects to the Codex SSE HTTP server running inside the sandbox
and streams events back. It allows the main agent to delegate complex
coding tasks to Codex as a sub-agent.

Based on II Agent's codex.py implementation, adapted for LangChain.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type, Callable, Awaitable
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Input Schema
# =============================================================================

class CodexAgentInput(BaseModel):
    """Input schema for CodexAgent tool."""
    
    prompt: str = Field(
        description="The instruction or task for the Codex agent to perform."
    )
    work_dir: str = Field(
        default="/workspace",
        description="The working directory for the Codex agent to use."
    )


# =============================================================================
# Event Types (for event callback)
# =============================================================================

class CodexEventType:
    """Event types emitted by Codex SSE server."""
    
    AGENT_MESSAGE = "agent_message"
    AGENT_REASONING = "agent_reasoning"
    AGENT_REASONING_RAW = "agent_reasoning_raw_content"
    MCP_TOOL_CALL_BEGIN = "mcp_tool_call_begin"
    MCP_TOOL_CALL_END = "mcp_tool_call_end"
    EXEC_COMMAND_BEGIN = "exec_command_begin"
    EXEC_COMMAND_END = "exec_command_end"
    WEB_SEARCH_BEGIN = "web_search_begin"
    WEB_SEARCH_END = "web_search_end"
    PATCH_APPLY_BEGIN = "patch_apply_begin"
    PATCH_APPLY_END = "patch_apply_end"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    
    # Delta events (streaming, ignored)
    AGENT_MESSAGE_DELTA = "agent_message_delta"
    AGENT_REASONING_DELTA = "agent_reasoning_delta"
    EXEC_OUTPUT_DELTA = "exec_command_output_delta"


# =============================================================================
# Event Callback Type
# =============================================================================

# Callback signature: async def callback(event_type: str, data: dict) -> None
CodexEventCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]


# =============================================================================
# CodexAgent Tool
# =============================================================================

class CodexAgentTool(BaseTool):
    """
    LangChain tool that delegates tasks to the Codex SSE sub-agent.
    
    The Codex agent runs inside the sandbox on port 1324 (sse-http-server).
    This tool sends a prompt to Codex and streams back events, collecting
    the final result to return to the main agent.
    
    Usage:
        codex_tool = CodexAgentTool(codex_url="http://sandbox:1324/messages")
        result = await codex_tool.ainvoke({"prompt": "Create a FastAPI app", "work_dir": "/workspace"})
    """
    
    name: str = "codex_delegate"
    description: str = (
        "Delegate tasks to the Codex AI sub-agent. "
        "Only use this tool when the user EXPLICITLY asks to delegate to Codex "
        "or specifically mentions 'use Codex' or 'delegate to Codex'. "
        "Do NOT use this tool by default for coding tasks — use your own "
        "sandbox tools (Bash, Read, Write, Edit, etc.) instead. "
        "Codex can write code, execute commands, search the web, and apply patches. "
        "Input: A clear prompt describing what you want Codex to accomplish."
    )
    args_schema: Type[BaseModel] = CodexAgentInput
    
    # Configuration
    codex_url: str = Field(description="Full URL to Codex SSE server's /messages endpoint")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    
    # Optional: Session/Run tracking
    session_id: Optional[str] = Field(default=None, description="Session ID for tracking")
    run_id: Optional[str] = Field(default=None, description="Run ID for tracking")
    
    # Optional: Event callback for streaming events to frontend
    event_callback: Optional[CodexEventCallback] = Field(
        default=None, 
        exclude=True,  # Don't include in serialization
        description="Async callback for streaming events"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(
        self,
        prompt: str,
        work_dir: str = "/workspace",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Sync execution not supported - use async version."""
        raise NotImplementedError("CodexAgentTool only supports async execution. Use ainvoke().")
    
    async def _arun(
        self,
        prompt: str,
        work_dir: str = "/workspace",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute the Codex agent with the given prompt.
        
        Connects to the Codex SSE server, sends the prompt, and streams
        back events until task completion.
        
        Args:
            prompt: The task description for Codex
            work_dir: Working directory inside the sandbox
            run_manager: LangChain callback manager (optional)
            
        Returns:
            The final result message from Codex
        """
        # Prepare payload for Codex server
        payload = {
            "type": "user_message",
            "message": prompt,
            "work_dir": work_dir,
        }
        
        logger.info(f"CodexAgentTool: Sending task to {self.codex_url}")
        logger.debug(f"CodexAgentTool: Payload = {payload}")
        
        try:
            result_text = await self._stream_codex_events(payload)
            logger.info(f"CodexAgentTool: Task completed with {len(result_text)} chars result")
            
            # Emit sub-agent complete event if callback provided
            if self.event_callback:
                await self.event_callback("sub_agent_complete", {
                    "agent": "codex",
                    "message": "Codex agent completed",
                })
            
            return result_text
            
        except httpx.TimeoutException as e:
            error_msg = f"Codex agent timed out after {self.timeout}s: {str(e)}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Codex server returned error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"
            
        except Exception as e:
            error_msg = f"Codex agent failed: {str(e)}"
            logger.exception(error_msg)
            return f"ERROR: {error_msg}"
    
    async def _stream_codex_events(self, payload: Dict[str, Any]) -> str:
        """
        Stream events from Codex server and process them.
        
        Args:
            payload: The request payload to send to Codex
            
        Returns:
            The final result text from Codex
        """
        collected_output: List[str] = []
        task_complete_message: Optional[str] = None
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.codex_url,
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # Parse SSE format: "data: {json}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        try:
                            event_data = json.loads(data_str)
                            complete_msg = await self._process_codex_event(
                                event_data, collected_output
                            )
                            # Track the task_complete message if returned
                            if complete_msg is not None:
                                task_complete_message = complete_msg
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse Codex event: {e}")
                            if self.event_callback:
                                await self.event_callback("error", {
                                    "message": f"Failed to parse event: {e}",
                                    "source": "codex_agent",
                                })
        
        # Return the task_complete message if available, otherwise join collected outputs
        if task_complete_message:
            return task_complete_message
        elif collected_output:
            return "\n".join(collected_output)
        else:
            return "Codex agent completed with no output"
    
    async def _process_codex_event(
        self, 
        event_data: Dict[str, Any], 
        collected_output: List[str]
    ) -> Optional[str]:
        """
        Process an individual Codex SSE event.
        
        Event types handled:
        - agent_message: Agent's text response
        - agent_reasoning: Agent's thinking/reasoning
        - mcp_tool_call_begin/end: MCP tool execution
        - exec_command_begin/end: Shell command execution
        - web_search_begin/end: Web search
        - patch_apply_begin/end: Code patch application
        - task_complete: Task finished
        - error: Error occurred
        
        Args:
            event_data: The parsed JSON event data
            collected_output: List to collect output strings
            
        Returns:
            The completion message if this is a task_complete event, None otherwise
        """
        event_type = event_data.get("type", "unknown")
        
        # -----------------------------------------------------------------
        # Agent Message/Response
        # -----------------------------------------------------------------
        if event_type == CodexEventType.AGENT_MESSAGE:
            message = event_data.get("message", "")
            collected_output.append(message)
            
            if self.event_callback:
                await self.event_callback("agent_response", {
                    "text": message,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Agent Reasoning (thinking)
        # -----------------------------------------------------------------
        elif event_type in (CodexEventType.AGENT_REASONING, CodexEventType.AGENT_REASONING_RAW):
            thinking_text = event_data.get("text", "")
            
            if self.event_callback:
                await self.event_callback("agent_thinking", {
                    "text": thinking_text,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # MCP Tool Call Begin
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.MCP_TOOL_CALL_BEGIN:
            invocation = event_data.get("invocation", {})
            call_id = event_data.get("call_id", f"mcp_{id(event_data)}")
            server = invocation.get("server", "unknown")
            tool = invocation.get("tool", "unknown")
            arguments = invocation.get("arguments", {})
            
            if self.event_callback:
                await self.event_callback("tool_call_start", {
                    "tool_call_id": call_id,
                    "tool_name": f"{server}.{tool}",
                    "tool_input": arguments,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # MCP Tool Call End
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.MCP_TOOL_CALL_END:
            invocation = event_data.get("invocation", {})
            call_id = event_data.get("call_id", f"mcp_{id(event_data)}")
            server = invocation.get("server", "unknown")
            tool = invocation.get("tool", "unknown")
            result = event_data.get("result", {})
            
            # Parse Ok/Err result format
            is_error = False
            tool_output = ""
            if isinstance(result, dict):
                if "Ok" in result:
                    tool_output = str(result["Ok"])
                elif "Err" in result:
                    tool_output = str(result["Err"])
                    is_error = True
                else:
                    tool_output = str(result)
            else:
                tool_output = str(result)
            
            collected_output.append(f"[MCP:{tool}] {tool_output}")
            
            if self.event_callback:
                await self.event_callback("tool_call_end", {
                    "tool_call_id": call_id,
                    "tool_name": f"{server}.{tool}",
                    "result": tool_output,
                    "is_error": is_error,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Exec Command Begin (shell execution)
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.EXEC_COMMAND_BEGIN:
            call_id = event_data.get("call_id", f"exec_{id(event_data)}")
            command = event_data.get("command", [])
            cwd = event_data.get("cwd", "")
            
            if self.event_callback:
                await self.event_callback("tool_call_start", {
                    "tool_call_id": call_id,
                    "tool_name": "Bash",
                    "tool_input": {"command": " ".join(command), "cwd": cwd},
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Exec Command End
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.EXEC_COMMAND_END:
            call_id = event_data.get("call_id", f"exec_{id(event_data)}")
            stdout = event_data.get("stdout", "")
            stderr = event_data.get("stderr", "")
            exit_code = event_data.get("exit_code", 0)
            formatted_output = event_data.get("formatted_output", "")
            
            is_error = exit_code != 0
            output = formatted_output or (stdout + stderr)
            
            collected_output.append(f"[bash] {output}")
            
            if self.event_callback:
                await self.event_callback("tool_call_end", {
                    "tool_call_id": call_id,
                    "tool_name": "Bash",
                    "result": output,
                    "is_error": is_error,
                    "exit_code": exit_code,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Web Search Begin
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.WEB_SEARCH_BEGIN:
            call_id = event_data.get("call_id", f"websearch_{id(event_data)}")
            
            if self.event_callback:
                await self.event_callback("tool_call_start", {
                    "tool_call_id": call_id,
                    "tool_name": "web_search",
                    "tool_input": {},
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Web Search End
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.WEB_SEARCH_END:
            call_id = event_data.get("call_id", f"websearch_{id(event_data)}")
            query = event_data.get("query", "")
            
            collected_output.append(f"[web_search] Query: {query}")
            
            if self.event_callback:
                await self.event_callback("tool_call_end", {
                    "tool_call_id": call_id,
                    "tool_name": "web_search",
                    "result": f"Search completed for: {query}",
                    "is_error": False,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Patch Apply Begin
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.PATCH_APPLY_BEGIN:
            call_id = event_data.get("call_id", f"patch_{id(event_data)}")
            changes = event_data.get("changes", {})
            
            if self.event_callback:
                await self.event_callback("tool_call_start", {
                    "tool_call_id": call_id,
                    "tool_name": "apply_patch",
                    "tool_input": {"changes": changes},
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Patch Apply End
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.PATCH_APPLY_END:
            call_id = event_data.get("call_id", f"patch_{id(event_data)}")
            stdout = event_data.get("stdout", "")
            stderr = event_data.get("stderr", "")
            success = event_data.get("success", False)
            
            output = stdout if stdout else stderr
            collected_output.append(f"[apply_patch] {output}")
            
            if self.event_callback:
                await self.event_callback("tool_call_end", {
                    "tool_call_id": call_id,
                    "tool_name": "apply_patch",
                    "result": output,
                    "is_error": not success,
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Task Complete
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.TASK_COMPLETE:
            last_message = event_data.get("last_agent_message")
            final_msg = last_message or "Task completed"
            
            if self.event_callback:
                await self.event_callback("task_complete", {
                    "message": final_msg,
                    "source": "codex",
                })
            
            # Return the completion message to be used as the final result
            return final_msg
        
        # -----------------------------------------------------------------
        # Error
        # -----------------------------------------------------------------
        elif event_type == CodexEventType.ERROR:
            error_msg = event_data.get("message", "Unknown error")
            collected_output.append(f"ERROR: {error_msg}")
            
            if self.event_callback:
                await self.event_callback("error", {
                    "message": f"[Codex] {error_msg}",
                    "source": "codex",
                })
        
        # -----------------------------------------------------------------
        # Ignore delta events and approval requests
        # -----------------------------------------------------------------
        elif event_type in (
            CodexEventType.AGENT_MESSAGE_DELTA,
            CodexEventType.AGENT_REASONING_DELTA,
            "agent_reasoning_raw_content_delta",
            CodexEventType.EXEC_OUTPUT_DELTA,
            "exec_approval_request",
            "apply_patch_approval_request",
            "agent_reasoning_section_break",
        ):
            # Silently ignore streaming/approval events
            pass
        
        else:
            logger.debug(f"CodexAgentTool: Ignoring unknown event type: {event_type}")
        
        # Return None for all non-completion events
        return None


# =============================================================================
# Factory Function
# =============================================================================

def create_codex_tool(
    codex_url: str,
    timeout: int = 300,
    session_id: Optional[str] = None,
    event_callback: Optional[CodexEventCallback] = None,
) -> CodexAgentTool:
    """
    Factory function to create a CodexAgentTool.
    
    Args:
        codex_url: Full URL to Codex SSE server (e.g., "http://sandbox:1324/messages")
        timeout: Request timeout in seconds
        session_id: Optional session ID for tracking
        event_callback: Optional async callback for streaming events
        
    Returns:
        Configured CodexAgentTool instance
    """
    return CodexAgentTool(
        codex_url=codex_url,
        timeout=timeout,
        session_id=session_id,
        event_callback=event_callback,
    )
