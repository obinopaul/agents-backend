"""Persistent Task Management Middleware.

This middleware provides robust task/todo management with sections, granular CRUD,
and configurable storage backends. Converted from task_list_tool.py to work with
LangChain's middleware architecture.

Storage Backends:
- "store": Uses LangGraph Store (persistent via thread_id) - DEFAULT
- "state": Uses agent state (ephemeral, per-run only)

Features:
- Sections for organizing tasks into phases
- Granular CRUD operations (view, create, update, delete)
- Batch operations for efficiency
- Task states: pending, in_progress, completed, cancelled

Usage:
    from backend.src.agents.middleware.persistent_task_middleware import (
        PersistentTaskMiddleware,
    )
    
    agent = create_agent(
        model="openai:gpt-4o",
        middleware=[PersistentTaskMiddleware()],
        store=InMemoryStore(),  # Required for persistent storage
    )
"""

from __future__ import annotations

import json
import logging
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, List, Literal, Optional, cast

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.store.base import BaseStore
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import NotRequired, TypedDict

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelCallResult,
    ModelRequest,
    ModelResponse,
    OmitFromInput,
)
from langchain.tools import InjectedState, InjectedStore, InjectedToolCallId

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    
logger = logging.getLogger(__name__)


# =============================================================================
# Task Status and Models
# =============================================================================

class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Section(BaseModel):
    """A section for organizing related tasks."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    
    class Config:
        frozen = False


class Task(BaseModel):
    """A single task with content and status."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    status: TaskStatus = TaskStatus.PENDING
    section_id: str  # Reference to section ID
    
    class Config:
        frozen = False


class TaskData(TypedDict):
    """Storage format for tasks."""
    sections: list[dict]
    tasks: list[dict]


# =============================================================================
# State Schema
# =============================================================================

class TaskPlanningState(AgentState):
    """State schema for the persistent task middleware."""
    
    task_sections: Annotated[NotRequired[list[dict]], OmitFromInput]
    """List of task sections for organizing work."""
    
    tasks: Annotated[NotRequired[list[dict]], OmitFromInput]
    """List of task items with status tracking."""


# =============================================================================
# Tool Descriptions
# =============================================================================

VIEW_TASKS_DESCRIPTION = """View all tasks and sections in the current task list.

Use this REGULARLY throughout execution to:
- Check current progress
- Identify the next task to execute
- Review completed work
- Verify task completion status

Best practices:
- Use this every 2-3 task completions
- Always use before final output to verify all tasks are complete
- Execute tasks in the exact order they appear"""

CREATE_TASKS_DESCRIPTION = """Create tasks organized by sections. Supports both single section and multi-section batch creation.

WHEN TO CREATE TASK LISTS (ONLY FOR SIGNIFICANT TASKS):
- Extensive multi-item research (10+ items)
- Complex content creation projects
- Multi-phase processes requiring planning
- Projects with 5+ distinct steps

DO NOT create task lists for:
- Simple questions or single-step tasks
- Quick operations that can be completed immediately
- Trivial requests

TASK CREATION STRUCTURE:
1. Section 1: Individual Research - One task per item
2. Section 2: Data Verification - Cross-check findings
3. Section 3: Synthesis - Compile findings
4. Section 4: Output Creation - Create deliverables

Parameters:
- sections: List of {title: str, tasks: list[str]} for batch creation
- section_title: Single section title (creates if doesn't exist)
- section_id: Existing section ID to add tasks to
- task_contents: List of task strings (use with section_title or section_id)"""

UPDATE_TASKS_DESCRIPTION = """Update one or more tasks. Mark tasks as 'completed' IMMEDIATELY after finishing.

EFFICIENT BATCHING: When you've completed multiple tasks, batch them into a single update call.

Task States:
- pending: Not started
- in_progress: Currently working on
- completed: Finished successfully
- cancelled: No longer needed

Parameters:
- task_ids: Single task ID (string) or list of task IDs
- status: New status (pending, in_progress, completed, cancelled)
- content: Updated task content
- section_id: Move task to different section"""

DELETE_TASKS_DESCRIPTION = """Delete one or more tasks and/or sections.

Use this when tasks become unnecessary or redundant. Active task list management includes removing tasks that are no longer needed.

Parameters:
- task_ids: Single task ID or list of task IDs to delete
- section_ids: Single section ID or list of section IDs (deletes all tasks in section)
- confirm: Must be true to delete sections"""

CLEAR_ALL_DESCRIPTION = """Clear all tasks and sections (creates completely empty state).

Parameters:
- confirm: Must be true to confirm clearing everything"""


SYSTEM_PROMPT = """## Task Management

You have access to a task management system to help you plan and track complex objectives.

**When to Use:**
- Complex multi-step tasks (5+ steps)
- Large research projects (10+ items)
- Multi-phase work requiring organization

**When NOT to Use:**
- Simple requests (1-3 steps)
- Trivial questions
- Quick operations

**Task Management Rules:**
1. Create granular, specific tasks - one per research item
2. Mark tasks IN_PROGRESS before starting work
3. Mark tasks COMPLETED immediately after finishing (don't batch)
4. Use view_tasks every 2-3 completions to check progress
5. Execute tasks in exact order they appear
6. Remove unnecessary tasks with delete_tasks

**Task States:**
- pending: Not started
- in_progress: Currently working on
- completed: Finished successfully
- cancelled: No longer needed"""


# =============================================================================
# Storage Utilities
# =============================================================================

def _get_store_namespace(thread_id: str) -> tuple:
    """Get the namespace for storing tasks in LangGraph store."""
    return ("persistent_tasks", thread_id)


async def _load_from_store(store: BaseStore, thread_id: str) -> TaskData:
    """Load task data from LangGraph store."""
    try:
        namespace = _get_store_namespace(thread_id)
        result = await store.aget(namespace, "task_data")
        if result and result.value:
            return result.value
    except Exception as e:
        logger.warning(f"Error loading from store: {e}")
    return {"sections": [], "tasks": []}


async def _save_to_store(store: BaseStore, thread_id: str, data: TaskData) -> None:
    """Save task data to LangGraph store."""
    try:
        namespace = _get_store_namespace(thread_id)
        await store.aput(namespace, "task_data", data)
    except Exception as e:
        logger.error(f"Error saving to store: {e}")
        raise


def _load_from_state(state: dict) -> TaskData:
    """Load task data from agent state."""
    return {
        "sections": state.get("task_sections", []),
        "tasks": state.get("tasks", []),
    }


def _format_response(sections: List[Section], tasks: List[Task]) -> dict:
    """Format task data for response display."""
    # Group tasks by section
    section_map = {s.id: s for s in sections}
    grouped_tasks = {}
    
    for task in tasks:
        section_id = task.section_id
        if section_id not in grouped_tasks:
            grouped_tasks[section_id] = []
        grouped_tasks[section_id].append(task.model_dump())
    
    # Build formatted sections
    formatted_sections = []
    for section in sections:
        section_tasks = grouped_tasks.get(section.id, [])
        if section_tasks:
            formatted_sections.append({
                "id": section.id,
                "title": section.title,
                "tasks": section_tasks
            })
    
    # Calculate stats
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)
    
    return {
        "sections": formatted_sections,
        "total_tasks": len(tasks),
        "total_sections": len(sections),
        "stats": {
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "cancelled": cancelled,
        }
    }


def _parse_list_param(value: Any) -> list:
    """Parse a parameter that could be a string, single value, or list."""
    if value is None:
        return []
    if isinstance(value, str):
        # Try to parse as JSON array
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return [value]  # Not a list after parsing, treat as single
        except json.JSONDecodeError:
            return [value]  # Not JSON, treat as single ID
    elif isinstance(value, list):
        return value
    else:
        return [value]


# =============================================================================
# Tool Functions
# =============================================================================

@tool(description=VIEW_TASKS_DESCRIPTION)
async def view_tasks(
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    store: Annotated[Optional[BaseStore], InjectedStore] = None,
) -> Command:
    """View all tasks and sections in the current task list."""
    try:
        # Get thread_id from config or state
        thread_id = state.get("configurable", {}).get("thread_id", "__default__")
        
        # Load data from store if available, otherwise from state
        if store:
            data = await _load_from_store(store, thread_id)
        else:
            data = _load_from_state(state)
        
        sections = [Section(**s) for s in data.get("sections", [])]
        tasks = [Task(**t) for t in data.get("tasks", [])]
        
        response = _format_response(sections, tasks)
        
        return Command(
            update={
                "messages": [ToolMessage(
                    json.dumps(response, indent=2),
                    tool_call_id=tool_call_id
                )]
            }
        )
    except Exception as e:
        logger.error(f"Error viewing tasks: {e}")
        return Command(
            update={
                "messages": [ToolMessage(
                    f"Error viewing tasks: {str(e)}",
                    tool_call_id=tool_call_id
                )]
            }
        )


@tool(description=CREATE_TASKS_DESCRIPTION)
async def create_tasks(
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    store: Annotated[Optional[BaseStore], InjectedStore] = None,
    sections: Optional[List[dict]] = None,
    section_title: Optional[str] = None,
    section_id: Optional[str] = None,
    task_contents: Optional[List[str]] = None,
) -> Command:
    """Create tasks organized by sections."""
    try:
        thread_id = state.get("configurable", {}).get("thread_id", "__default__")
        
        # Parse sections if string
        if sections is not None and isinstance(sections, str):
            try:
                sections = json.loads(sections)
            except json.JSONDecodeError as e:
                return Command(update={"messages": [ToolMessage(
                    f"Invalid JSON in sections: {e}",
                    tool_call_id=tool_call_id
                )]})
        
        # Parse task_contents if string
        if task_contents is not None and isinstance(task_contents, str):
            try:
                task_contents = json.loads(task_contents)
            except json.JSONDecodeError as e:
                return Command(update={"messages": [ToolMessage(
                    f"Invalid JSON in task_contents: {e}",
                    tool_call_id=tool_call_id
                )]})
        
        # Load existing data
        if store:
            data = await _load_from_store(store, thread_id)
        else:
            data = _load_from_state(state)
        
        existing_sections = [Section(**s) for s in data.get("sections", [])]
        existing_tasks = [Task(**t) for t in data.get("tasks", [])]
        section_map = {s.id: s for s in existing_sections}
        title_map = {s.title.lower(): s for s in existing_sections}
        
        created_tasks = 0
        created_sections = 0
        
        if sections:
            # Batch creation across multiple sections
            for section_data in sections:
                if not isinstance(section_data, dict):
                    continue
                section_title_input = section_data.get("title", "Untitled")
                task_list = section_data.get("tasks", [])
                
                # Find or create section
                title_lower = section_title_input.lower()
                if title_lower in title_map:
                    target_section = title_map[title_lower]
                else:
                    target_section = Section(title=section_title_input)
                    existing_sections.append(target_section)
                    title_map[title_lower] = target_section
                    created_sections += 1
                
                # Create tasks
                for task_content in task_list:
                    if isinstance(task_content, str):
                        new_task = Task(content=task_content, section_id=target_section.id)
                        existing_tasks.append(new_task)
                        created_tasks += 1
        else:
            # Single section creation
            if not task_contents:
                return Command(update={"messages": [ToolMessage(
                    "Must provide either 'sections' array or 'task_contents' with section info",
                    tool_call_id=tool_call_id
                )]})
            
            if not section_id and not section_title:
                return Command(update={"messages": [ToolMessage(
                    "Must specify either 'section_id' or 'section_title'",
                    tool_call_id=tool_call_id
                )]})
            
            target_section = None
            
            if section_id:
                if section_id not in section_map:
                    return Command(update={"messages": [ToolMessage(
                        f"Section ID '{section_id}' not found",
                        tool_call_id=tool_call_id
                    )]})
                target_section = section_map[section_id]
            elif section_title:
                title_lower = section_title.lower()
                if title_lower in title_map:
                    target_section = title_map[title_lower]
                else:
                    target_section = Section(title=section_title)
                    existing_sections.append(target_section)
                    created_sections += 1
            
            for content in task_contents:
                new_task = Task(content=content, section_id=target_section.id)
                existing_tasks.append(new_task)
                created_tasks += 1
        
        # Prepare data for storage
        new_data: TaskData = {
            "sections": [s.model_dump() for s in existing_sections],
            "tasks": [t.model_dump() for t in existing_tasks],
        }
        
        # Save to store or return state update
        if store:
            await _save_to_store(store, thread_id, new_data)
            response = _format_response(existing_sections, existing_tasks)
            return Command(update={"messages": [ToolMessage(
                json.dumps(response, indent=2),
                tool_call_id=tool_call_id
            )]})
        else:
            response = _format_response(existing_sections, existing_tasks)
            return Command(update={
                "task_sections": new_data["sections"],
                "tasks": new_data["tasks"],
                "messages": [ToolMessage(
                    json.dumps(response, indent=2),
                    tool_call_id=tool_call_id
                )]
            })
    except Exception as e:
        logger.error(f"Error creating tasks: {e}")
        return Command(update={"messages": [ToolMessage(
            f"Error creating tasks: {str(e)}",
            tool_call_id=tool_call_id
        )]})


@tool(description=UPDATE_TASKS_DESCRIPTION)
async def update_tasks(
    task_ids: str | List[str],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    store: Annotated[Optional[BaseStore], InjectedStore] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
    section_id: Optional[str] = None,
) -> Command:
    """Update one or more tasks."""
    try:
        thread_id = state.get("configurable", {}).get("thread_id", "__default__")
        
        # Parse task_ids
        target_task_ids = _parse_list_param(task_ids)
        if not target_task_ids:
            return Command(update={"messages": [ToolMessage(
                "Task IDs are required",
                tool_call_id=tool_call_id
            )]})
        
        # Load data
        if store:
            data = await _load_from_store(store, thread_id)
        else:
            data = _load_from_state(state)
        
        sections = [Section(**s) for s in data.get("sections", [])]
        tasks = [Task(**t) for t in data.get("tasks", [])]
        section_map = {s.id: s for s in sections}
        task_map = {t.id: t for t in tasks}
        
        # Validate task IDs
        missing_tasks = [tid for tid in target_task_ids if tid not in task_map]
        if missing_tasks:
            return Command(update={"messages": [ToolMessage(
                f"Task IDs not found: {missing_tasks}",
                tool_call_id=tool_call_id
            )]})
        
        # Validate section_id
        if section_id and section_id not in section_map:
            return Command(update={"messages": [ToolMessage(
                f"Section ID '{section_id}' not found",
                tool_call_id=tool_call_id
            )]})
        
        # Apply updates
        updated_count = 0
        for tid in target_task_ids:
            task = task_map[tid]
            if content is not None:
                task.content = content
            if status is not None:
                task.status = TaskStatus(status)
            if section_id is not None:
                task.section_id = section_id
            updated_count += 1
        
        # Prepare data
        new_data: TaskData = {
            "sections": [s.model_dump() for s in sections],
            "tasks": [t.model_dump() for t in tasks],
        }
        
        # Save and respond
        if store:
            await _save_to_store(store, thread_id, new_data)
            response = _format_response(sections, tasks)
            return Command(update={"messages": [ToolMessage(
                json.dumps(response, indent=2),
                tool_call_id=tool_call_id
            )]})
        else:
            response = _format_response(sections, tasks)
            return Command(update={
                "task_sections": new_data["sections"],
                "tasks": new_data["tasks"],
                "messages": [ToolMessage(
                    json.dumps(response, indent=2),
                    tool_call_id=tool_call_id
                )]
            })
    except Exception as e:
        logger.error(f"Error updating tasks: {e}")
        return Command(update={"messages": [ToolMessage(
            f"Error updating tasks: {str(e)}",
            tool_call_id=tool_call_id
        )]})


@tool(description=DELETE_TASKS_DESCRIPTION)
async def delete_tasks(
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    store: Annotated[Optional[BaseStore], InjectedStore] = None,
    task_ids: Optional[str | List[str]] = None,
    section_ids: Optional[str | List[str]] = None,
    confirm: bool = False,
) -> Command:
    """Delete one or more tasks and/or sections."""
    try:
        # Validate inputs
        if not task_ids and not section_ids:
            return Command(update={"messages": [ToolMessage(
                "Must provide either task_ids or section_ids",
                tool_call_id=tool_call_id
            )]})
        
        if section_ids and not confirm:
            return Command(update={"messages": [ToolMessage(
                "Must set confirm=true to delete sections",
                tool_call_id=tool_call_id
            )]})
        
        thread_id = state.get("configurable", {}).get("thread_id", "__default__")
        
        # Load data
        if store:
            data = await _load_from_store(store, thread_id)
        else:
            data = _load_from_state(state)
        
        sections = [Section(**s) for s in data.get("sections", [])]
        tasks = [Task(**t) for t in data.get("tasks", [])]
        section_map = {s.id: s for s in sections}
        task_map = {t.id: t for t in tasks}
        
        remaining_tasks = tasks.copy()
        remaining_sections = sections.copy()
        
        # Delete tasks
        if task_ids:
            target_task_ids = set(_parse_list_param(task_ids))
            missing = [tid for tid in target_task_ids if tid not in task_map]
            if missing:
                return Command(update={"messages": [ToolMessage(
                    f"Task IDs not found: {missing}",
                    tool_call_id=tool_call_id
                )]})
            remaining_tasks = [t for t in tasks if t.id not in target_task_ids]
        
        # Delete sections
        if section_ids:
            target_section_ids = set(_parse_list_param(section_ids))
            missing = [sid for sid in target_section_ids if sid not in section_map]
            if missing:
                return Command(update={"messages": [ToolMessage(
                    f"Section IDs not found: {missing}",
                    tool_call_id=tool_call_id
                )]})
            remaining_sections = [s for s in sections if s.id not in target_section_ids]
            remaining_tasks = [t for t in remaining_tasks if t.section_id not in target_section_ids]
        
        # Prepare data
        new_data: TaskData = {
            "sections": [s.model_dump() for s in remaining_sections],
            "tasks": [t.model_dump() for t in remaining_tasks],
        }
        
        # Save and respond
        if store:
            await _save_to_store(store, thread_id, new_data)
            response = _format_response(remaining_sections, remaining_tasks)
            return Command(update={"messages": [ToolMessage(
                json.dumps(response, indent=2),
                tool_call_id=tool_call_id
            )]})
        else:
            response = _format_response(remaining_sections, remaining_tasks)
            return Command(update={
                "task_sections": new_data["sections"],
                "tasks": new_data["tasks"],
                "messages": [ToolMessage(
                    json.dumps(response, indent=2),
                    tool_call_id=tool_call_id
                )]
            })
    except Exception as e:
        logger.error(f"Error deleting tasks: {e}")
        return Command(update={"messages": [ToolMessage(
            f"Error deleting tasks: {str(e)}",
            tool_call_id=tool_call_id
        )]})


@tool(description=CLEAR_ALL_DESCRIPTION)
async def clear_all_tasks(
    confirm: bool,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    store: Annotated[Optional[BaseStore], InjectedStore] = None,
) -> Command:
    """Clear all tasks and sections."""
    try:
        if not confirm:
            return Command(update={"messages": [ToolMessage(
                "Must set confirm=true to clear all data",
                tool_call_id=tool_call_id
            )]})
        
        thread_id = state.get("configurable", {}).get("thread_id", "__default__")
        
        # Empty data
        new_data: TaskData = {"sections": [], "tasks": []}
        
        # Save and respond
        if store:
            await _save_to_store(store, thread_id, new_data)
            return Command(update={"messages": [ToolMessage(
                json.dumps({"sections": [], "total_tasks": 0, "total_sections": 0}, indent=2),
                tool_call_id=tool_call_id
            )]})
        else:
            return Command(update={
                "task_sections": [],
                "tasks": [],
                "messages": [ToolMessage(
                    json.dumps({"sections": [], "total_tasks": 0, "total_sections": 0}, indent=2),
                    tool_call_id=tool_call_id
                )]
            })
    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
        return Command(update={"messages": [ToolMessage(
            f"Error clearing tasks: {str(e)}",
            tool_call_id=tool_call_id
        )]})


# =============================================================================
# Middleware Class
# =============================================================================

class PersistentTaskMiddleware(AgentMiddleware):
    """Middleware that provides persistent task management capabilities.
    
    This middleware adds task planning tools that allow agents to create and manage
    structured task lists with sections for complex multi-step operations.
    
    Features:
    - Sections for organizing tasks into phases
    - Granular CRUD operations (view, create, update, delete)
    - Batch operations for efficiency
    - Task states: pending, in_progress, completed, cancelled
    
    Storage:
    - Primary: LangGraph Store (persistent via thread_id)
    - Fallback: Agent State (ephemeral, per-run only)
    
    Example:
        ```python
        from langchain.agents import create_agent
        from langgraph.store.memory import InMemoryStore
        from backend.src.agents.middleware.persistent_task_middleware import (
            PersistentTaskMiddleware,
        )
        
        agent = create_agent(
            "openai:gpt-4o",
            middleware=[PersistentTaskMiddleware()],
            store=InMemoryStore(),  # For persistent storage
        )
        ```
    """
    
    state_schema = TaskPlanningState
    
    def __init__(
        self,
        *,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        """Initialize the PersistentTaskMiddleware.
        
        Args:
            system_prompt: Custom system prompt for task management guidance.
        """
        super().__init__()
        self.system_prompt = system_prompt
        self.tools = [
            view_tasks,
            create_tasks,
            update_tasks,
            delete_tasks,
            clear_all_tasks,
        ]
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        """Update the system message to include the task management prompt."""
        if request.system_message is not None:
            new_system_content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{self.system_prompt}"},
            ]
        else:
            new_system_content = [{"type": "text", "text": self.system_prompt}]
        new_system_message = SystemMessage(
            content=cast("list[str | dict[str, str]]", new_system_content)
        )
        return handler(request.override(system_message=new_system_message))
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Update the system message to include the task management prompt (async)."""
        if request.system_message is not None:
            new_system_content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{self.system_prompt}"},
            ]
        else:
            new_system_content = [{"type": "text", "text": self.system_prompt}]
        new_system_message = SystemMessage(
            content=cast("list[str | dict[str, str]]", new_system_content)
        )
        return await handler(request.override(system_message=new_system_message))


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "PersistentTaskMiddleware",
    "TaskPlanningState",
    "TaskStatus",
    "Section",
    "Task",
]
