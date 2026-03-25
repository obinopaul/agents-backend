"""
Tool Filter Registry — Controls which tools are available per agent role.

This module provides a centralized, declarative configuration for filtering
tools based on the agent's role (e.g., base_node, planner, coder, general_subagent).

Design Principles:
    - Unknown roles get ALL tools (safe default — never silently break agents)
    - MCP/sandbox tools are accepted by default (opt-out, not opt-in)
    - Explicit excludes always win over includes
    - Easy to extend: just add a new role entry to ROLE_CONFIGS

Usage:
    from backend.src.config.tool_filter_config import apply_tool_filter

    filtered = apply_tool_filter("general_subagent", loaded_tools)

Inspired by ii-agent's AgentTypeConfig.TOOLSETS pattern.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Categories
# =============================================================================

class ToolCategory(str, Enum):
    """Logical groupings of tools for category-based filtering."""
    HITL = "hitl"
    WEB_SEARCH = "web_search"
    RAG = "rag"
    RESEARCH = "research"
    VISION = "vision"
    DELEGATION = "delegation"
    BROWSER = "browser"
    SHELL = "shell"
    FILE_SYSTEM = "file_system"
    MEDIA = "media"
    DEV_TOOLS = "dev_tools"     
    SLIDE_TOOLS = "slide_tools"
    DOCUMENT_TOOLS = "document_tools"
    DESIGN_TOOLS = "design_tools"
    EXCALIDRAW = "excalidraw"
    TODOS = "todos"
    BACKGROUND_TOOLS = "background_tools"


# Maps tool.name → set of categories it belongs to
TOOL_CATEGORY_MAP: dict[str, set[str]] = {
    # HITL
    "request_human_input": {ToolCategory.HITL, ToolCategory.BACKGROUND_TOOLS},
    # Web search & crawling
    "web_search": {ToolCategory.WEB_SEARCH},
    "crawl_tool": {ToolCategory.WEB_SEARCH},
    "web_visit": {ToolCategory.WEB_SEARCH},
    "web_visit_compress": {ToolCategory.WEB_SEARCH},
    "image_search": {ToolCategory.WEB_SEARCH},
    "web_batch_search": {ToolCategory.WEB_SEARCH},
    "tavily_search_results_json": {ToolCategory.WEB_SEARCH},
    "mcp_search": {ToolCategory.WEB_SEARCH},
    # RAG / retriever
    "local_search_tool": {ToolCategory.RAG},
    # Research / academic tools
    "people_search_tool": {ToolCategory.RESEARCH},
    "company_search_tool": {ToolCategory.RESEARCH},
    "paper_search_tool": {ToolCategory.RESEARCH},
    "get_paper_details_tool": {ToolCategory.RESEARCH},
    "search_authors_tool": {ToolCategory.RESEARCH},
    "get_author_details_tool": {ToolCategory.RESEARCH},
    "get_author_papers_tool": {ToolCategory.RESEARCH},
    "semantic_scholar_search_tool": {ToolCategory.RESEARCH},
    "arxiv_search_tool": {ToolCategory.RESEARCH},
    "pubmed_central_tool": {ToolCategory.RESEARCH},
    "arxiv_search": {ToolCategory.RESEARCH},
    "pubmed_central": {ToolCategory.RESEARCH},
    "pubmed_search": {ToolCategory.RESEARCH},
    "google_scholar": {ToolCategory.RESEARCH},
    "semantic_scholar": {ToolCategory.RESEARCH},
    # Vision
    "view_image": {ToolCategory.VISION},
    "read_remote_image": {ToolCategory.VISION},
    "reality_defender": {ToolCategory.VISION},
    # Delegation
    "codex_delegate": {ToolCategory.DELEGATION, ToolCategory.BACKGROUND_TOOLS},
    # Browser
    "browser_click": {ToolCategory.BROWSER},
    "browser_wait": {ToolCategory.BROWSER},
    "browser_view_interactive_elements": {ToolCategory.BROWSER},
    "browser_scroll_down": {ToolCategory.BROWSER},
    "browser_scroll_up": {ToolCategory.BROWSER},
    "browser_switch_tab": {ToolCategory.BROWSER},
    "browser_open_new_tab": {ToolCategory.BROWSER},
    "browser_get_select_options": {ToolCategory.BROWSER},
    "browser_select_dropdown_option": {ToolCategory.BROWSER},
    "browser_navigation": {ToolCategory.BROWSER},
    "browser_restart": {ToolCategory.BROWSER},
    "browser_enter_text": {ToolCategory.BROWSER},
    "browser_press_key": {ToolCategory.BROWSER},
    "browser_drag": {ToolCategory.BROWSER},
    "browser_enter_multi_texts": {ToolCategory.BROWSER},
    "browser_use": {ToolCategory.BROWSER},
    "browser_wait_for": {ToolCategory.BROWSER},
    "browser_close": {ToolCategory.BROWSER},
    "browser_console_messages": {ToolCategory.BROWSER},
    "browser_evaluate": {ToolCategory.BROWSER},
    "browser_handle_dialog": {ToolCategory.BROWSER},
    "browser_hover": {ToolCategory.BROWSER},
    "browser_navigate": {ToolCategory.BROWSER},
    "browser_network_requests": {ToolCategory.BROWSER},
    "browser_select_option": {ToolCategory.BROWSER},
    "browser_snapshot": {ToolCategory.BROWSER},
    "browser_take_screenshot": {ToolCategory.BROWSER},
    "browser_type": {ToolCategory.BROWSER},
    "browser_tab_close": {ToolCategory.BROWSER},
    "browser_tab_list": {ToolCategory.BROWSER},
    "browser_tab_new": {ToolCategory.BROWSER},
    "browser_tab_select": {ToolCategory.BROWSER},
    "browser_mouse_click_xy": {ToolCategory.BROWSER},
    "browser_mouse_drag_xy": {ToolCategory.BROWSER},
    "browser_mouse_move_xy": {ToolCategory.BROWSER},
    # Shell Tools
    "shell_init": {ToolCategory.SHELL},
    "shell_run_command": {ToolCategory.SHELL},
    "shell_view": {ToolCategory.SHELL},
    "shell_stop_command": {ToolCategory.SHELL},
    "shell_list": {ToolCategory.SHELL},
    "shell_write_to_process": {ToolCategory.SHELL},
    "bash": {ToolCategory.SHELL},
    "shell_execute": {ToolCategory.SHELL},
    "shell_exec": {ToolCategory.SHELL},
    "shell_kill_process": {ToolCategory.SHELL},
    "shell_wait": {ToolCategory.SHELL},
    "Bash": {ToolCategory.SHELL},
    "BashInit": {ToolCategory.SHELL},
    "BashView": {ToolCategory.SHELL},
    "BashStop": {ToolCategory.SHELL},
    "BashKill": {ToolCategory.SHELL},
    "BashList": {ToolCategory.SHELL},
    "BashWriteToProcess": {ToolCategory.SHELL},
    # File System Tools
    "file_read": {ToolCategory.FILE_SYSTEM},
    "file_write": {ToolCategory.FILE_SYSTEM},
    "file_edit": {ToolCategory.FILE_SYSTEM},
    "apply_patch": {ToolCategory.FILE_SYSTEM},
    "str_replace_editor": {ToolCategory.FILE_SYSTEM},
    "ast_grep": {ToolCategory.FILE_SYSTEM},
    "grep": {ToolCategory.FILE_SYSTEM},
    "lsp": {ToolCategory.FILE_SYSTEM},
    "read": {ToolCategory.FILE_SYSTEM},
    "write": {ToolCategory.FILE_SYSTEM},
    "edit": {ToolCategory.FILE_SYSTEM},
    "list_dir": {ToolCategory.FILE_SYSTEM},
    "glob": {ToolCategory.FILE_SYSTEM},
    "Read": {ToolCategory.FILE_SYSTEM},
    "Write": {ToolCategory.FILE_SYSTEM},
    "Edit": {ToolCategory.FILE_SYSTEM},
    "LS": {ToolCategory.FILE_SYSTEM},
    "Glob": {ToolCategory.FILE_SYSTEM},
    "ASTGrep": {ToolCategory.FILE_SYSTEM},
    "MultiEdit": {ToolCategory.FILE_SYSTEM},
    "str_replace_based_edit_tool": {ToolCategory.FILE_SYSTEM},
    # Media
    "generate_video": {ToolCategory.MEDIA},
    "generate_image": {ToolCategory.MEDIA},
    "image_generate": {ToolCategory.MEDIA},
    "video_generate": {ToolCategory.MEDIA},
    # Dev Tools 
    "fullstack_init": {ToolCategory.DEV_TOOLS},
    "save_checkpoint": {ToolCategory.DEV_TOOLS},
    "register_port": {ToolCategory.DEV_TOOLS},
    "get_database_connection": {ToolCategory.DEV_TOOLS},
    "fullstack_project_init": {ToolCategory.DEV_TOOLS},
    # Slide Tools
    "slide_write": {ToolCategory.SLIDE_TOOLS},
    "slide_edit": {ToolCategory.SLIDE_TOOLS},
    "slide_apply_patch": {ToolCategory.SLIDE_TOOLS},
    "slide_template_init": {ToolCategory.SLIDE_TOOLS},
    "presentation": {ToolCategory.SLIDE_TOOLS},
    "SlideWrite": {ToolCategory.SLIDE_TOOLS},
    "SlideEdit": {ToolCategory.SLIDE_TOOLS},
    "slide_deck_init": {ToolCategory.SLIDE_TOOLS},
    "slide_deck_complete": {ToolCategory.SLIDE_TOOLS},
    # Document Tools
    "document_template_init": {ToolCategory.DOCUMENT_TOOLS},
    "document_compile": {ToolCategory.DOCUMENT_TOOLS},
    "latex_compile": {ToolCategory.DOCUMENT_TOOLS},
    # Design Tools
    "design_init": {ToolCategory.DESIGN_TOOLS},
    "design_create": {ToolCategory.DESIGN_TOOLS},
    "design_edit": {ToolCategory.DESIGN_TOOLS},
    "design_get": {ToolCategory.DESIGN_TOOLS},
    "design_export": {ToolCategory.DESIGN_TOOLS},
    # Excalidraw tools
    "excalidraw_init": {ToolCategory.EXCALIDRAW},
    "excalidraw_create": {ToolCategory.EXCALIDRAW},
    "excalidraw_update": {ToolCategory.EXCALIDRAW},
    "excalidraw_delete": {ToolCategory.EXCALIDRAW},
    "excalidraw_query": {ToolCategory.EXCALIDRAW},
    "excalidraw_batch_create": {ToolCategory.EXCALIDRAW},
    "excalidraw_group": {ToolCategory.EXCALIDRAW},
    "excalidraw_ungroup": {ToolCategory.EXCALIDRAW},
    "excalidraw_align": {ToolCategory.EXCALIDRAW},
    "excalidraw_distribute": {ToolCategory.EXCALIDRAW},
    "excalidraw_lock": {ToolCategory.EXCALIDRAW},
    "excalidraw_unlock": {ToolCategory.EXCALIDRAW},
    "excalidraw_resource": {ToolCategory.EXCALIDRAW},
    # To-do tools
    "TodoWrite": {ToolCategory.TODOS},
    "TodoRead": {ToolCategory.TODOS},
    "todo_read": {ToolCategory.TODOS},
    "todo_write": {ToolCategory.TODOS},
    # Background tools
    "background_task": {ToolCategory.BACKGROUND_TOOLS},
    "wait_for_subagents": {ToolCategory.BACKGROUND_TOOLS},
    "task_progress": {ToolCategory.BACKGROUND_TOOLS},
    "view_tasks": {ToolCategory.BACKGROUND_TOOLS},
    "create_tasks": {ToolCategory.BACKGROUND_TOOLS},
    "update_tasks": {ToolCategory.BACKGROUND_TOOLS},
    "delete_tasks": {ToolCategory.BACKGROUND_TOOLS},
    "clear_all_tasks": {ToolCategory.BACKGROUND_TOOLS},
    "sub_agent": {ToolCategory.BACKGROUND_TOOLS},
    "sub_agent_researcher": {ToolCategory.BACKGROUND_TOOLS},
    "task": {ToolCategory.BACKGROUND_TOOLS},
    "codex_agent": {ToolCategory.BACKGROUND_TOOLS},
    "design_document_agent": {ToolCategory.BACKGROUND_TOOLS},
    "browser_subagent": {ToolCategory.BACKGROUND_TOOLS},
}


def _get_tool_categories(tool_name: str) -> set[str]:
    """Return the categories a tool belongs to, or empty set if uncategorized."""
    return TOOL_CATEGORY_MAP.get(tool_name, set())


# =============================================================================
# Role Tool Configuration
# =============================================================================

@dataclass
class RoleToolConfig:
    """Declarative tool filter for a specific agent role.

    Filter precedence (highest → lowest):
        1. exclude_tools — always removed, no exceptions
        2. include_tools — if set, ONLY these tools pass (whitelist mode)
        3. exclude_categories — tools in these categories are removed
        4. include_categories — if set, only tools in these categories pass
        5. Default — tool is allowed

    MCP / dynamic sandbox tools are handled separately via ``allow_mcp_tools``.
    """
    # Explicit tool-name-level filters
    include_tools: Optional[List[str]] = None   # None = not in whitelist mode
    exclude_tools: Optional[List[str]] = None

    # Category-level filters
    include_categories: Optional[List[str]] = None  # None = all categories allowed
    exclude_categories: Optional[List[str]] = None

    # MCP / sandbox tools (default: accept all)
    allow_mcp_tools: bool = True


# =============================================================================
# Role Configurations
# =============================================================================
# Add or modify entries here to control each role's tool access.
# If a role is NOT listed, it gets ALL tools (no filtering).

ROLE_CONFIGS: dict[str, RoleToolConfig] = {
    # ── Main graph node ─────────────────────────────────────────────────
    # base_node gets everything — no filtering
    "base_node": RoleToolConfig(),

    # ── Sub-agents ──────────────────────────────────────────────────────
    # General-purpose sub-agent: exclude delegation tools to avoid
    # recursive delegation chains (subagent → codex → subagent …)
    "general_subagent": RoleToolConfig(
        exclude_tools=["codex_delegate"],
    ),

    # ── Module roles (deep-agent modules) ───────────────────────────────
    # Planner: full access — needs web search & research for planning
    "planner": RoleToolConfig(),

    # Analyzer: full access — needs research + vision for analysis
    "analyzer": RoleToolConfig(),

    # Coder: needs sandbox/MCP tools, exclude research noise
    "coder": RoleToolConfig(
        exclude_categories=[ToolCategory.RESEARCH],
    ),

    # Executor: needs sandbox/MCP tools, exclude research noise
    "executor": RoleToolConfig(
        exclude_categories=[ToolCategory.RESEARCH],
    ),

    # Verifier: vision + HITL + MCP (for sandbox verification)
    "verifier": RoleToolConfig(
        exclude_categories=[ToolCategory.RESEARCH, ToolCategory.DELEGATION],
    ),
}


# =============================================================================
# MCP Tool Detection
# =============================================================================

def _is_mcp_tool(tool) -> bool:
    """Detect whether a tool was loaded from an MCP server.

    MCP tools have their description prefixed with "Powered by '<server>'."
    by the loader in nodes.py / module nodes.
    """
    desc = getattr(tool, "description", "") or ""
    return desc.startswith("Powered by '")


# =============================================================================
# Public API
# =============================================================================

def apply_tool_filter(role: str, tools: Sequence) -> list:
    """Filter *tools* based on *role* configuration.

    Args:
        role: The agent role identifier (e.g. ``"base_node"``, ``"general_subagent"``).
        tools: Sequence of tool objects (``BaseTool`` or similar with a ``.name`` attr).

    Returns:
        A new list containing only the tools allowed for *role*.
        If *role* is unknown, returns all tools unchanged.

    Filter order:
        1. Unknown role → return all tools
        2. MCP tools → accept/reject based on ``allow_mcp_tools``
        3. ``exclude_tools`` → always removed
        4. ``include_tools`` → whitelist mode
        5. ``exclude_categories`` → category blacklist
        6. ``include_categories`` → category whitelist
        7. Default → allow
    """
    config = ROLE_CONFIGS.get(role)
    if config is None:
        # Unknown role — pass everything through (safe default)
        return list(tools)

    filtered: list = []
    excluded_names: list[str] = []

    for tool in tools:
        name = getattr(tool, "name", "")

        # ── MCP tools ───────────────────────────────────────────────
        if _is_mcp_tool(tool):
            if config.allow_mcp_tools:
                filtered.append(tool)
            else:
                excluded_names.append(name)
            continue

        # ── Explicit exclude (highest priority for non-MCP tools) ───
        if config.exclude_tools and name in config.exclude_tools:
            excluded_names.append(name)
            continue

        # ── Explicit include (whitelist mode) ───────────────────────
        if config.include_tools is not None:
            if name in config.include_tools:
                filtered.append(tool)
            else:
                excluded_names.append(name)
            continue

        # ── Category-based filtering ────────────────────────────────
        categories = _get_tool_categories(name)

        # Exclude categories takes precedence
        if config.exclude_categories and categories:
            if categories & set(config.exclude_categories):
                excluded_names.append(name)
                continue

        # Include categories (whitelist mode for categories)
        if config.include_categories is not None:
            if categories and (categories & set(config.include_categories)):
                filtered.append(tool)
            else:
                # Tool not in any included category — exclude
                excluded_names.append(name)
            continue

        # ── Default: allow ──────────────────────────────────────────
        filtered.append(tool)

    if excluded_names:
        logger.info(
            f"[ToolFilter] role={role}: allowed {len(filtered)}/{len(tools)} tools, "
            f"excluded: {excluded_names}"
        )
    else:
        logger.debug(f"[ToolFilter] role={role}: all {len(tools)} tools allowed")

    return filtered
