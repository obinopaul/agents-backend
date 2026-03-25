"""Command handler for /mode commands.

Provides CLI integration for mode management:
    /mode           - Show help
    /mode list      - List available modes
    /mode <name>    - Activate a mode
"""

import argparse
from pathlib import Path
from typing import Any

from deepagents_cli.config import console, COLORS, settings
from deepagents_cli.modes.manager import ModeManager, print_modes_list


def setup_mode_parser() -> argparse.ArgumentParser:
    """Create argument parser for /mode command."""
    parser = argparse.ArgumentParser(
        prog="/mode",
        description="Manage agent modes (pre-configured skill sets)",
        add_help=False,
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="help",
        help="Action: 'list' to show modes, or mode name to activate",
    )
    return parser


async def execute_mode_command(
    args: list[str],
    assistant_id: str,
    sandbox_type: str | None = None,
    mcp_tools: list | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Execute a /mode command.
    
    Args:
        args: Command arguments (excluding '/mode')
        assistant_id: Agent identifier for skill storage
        sandbox_type: Type of sandbox ("agent_infra", etc.) or None for local
        mcp_tools: List of MCP tools (for sandbox mode injection)
        workspace_path: Sandbox workspace path
        
    Returns:
        Result dict with execution status
    """
    manager = ModeManager()
    
    if not args or args[0] in ("help", "-h", "--help"):
        _print_mode_help()
        return {"success": True, "action": "help"}
    
    action = args[0].lower()
    
    if action == "list":
        modes = manager.list_modes()
        print_modes_list(modes)
        return {"success": True, "action": "list", "modes": modes}
    
    # Otherwise, treat action as mode name
    mode_name = action
    
    # Check if mode exists
    available_modes = [m["name"] for m in manager.list_modes()]
    if mode_name not in available_modes:
        console.print(f"\n[red]Unknown mode: {mode_name}[/red]")
        console.print(f"[dim]Available modes: {', '.join(available_modes)}[/dim]\n")
        return {"success": False, "error": f"Unknown mode: {mode_name}"}
    
    # Activate mode based on sandbox type
    if sandbox_type == "agent_infra" and mcp_tools:
        # Inject skills into sandbox
        result = await _activate_sandbox_mode(
            manager, mode_name, mcp_tools, workspace_path
        )
    else:
        # Inject skills locally
        result = _activate_local_mode(manager, mode_name, assistant_id)
    
    return result


def _print_mode_help() -> None:
    """Print help for /mode command."""
    console.print("\n[bold]Mode Management[/bold]\n", style=COLORS["primary"])
    console.print("Modes are pre-configured skill sets that enhance the agent's capabilities.\n")
    console.print("[bold]Commands:[/bold]")
    console.print("  /mode list           List available modes")
    console.print("  /mode <name>         Activate a mode (injects skills)")
    console.print("\n[bold]Examples:[/bold]")
    console.print("  /mode list")
    console.print("  /mode data_scientist")
    console.print("  /mode software_developer")
    console.print()


def _activate_local_mode(
    manager: ModeManager,
    mode_name: str,
    assistant_id: str,
) -> dict[str, Any]:
    """Activate mode by copying skills locally."""
    target_dir = settings.ensure_user_skills_dir(assistant_id)
    
    console.print(f"\n[dim]Activating mode: {mode_name}...[/dim]")
    
    result = manager.activate_mode_local(mode_name, target_dir)
    
    if result["success"]:
        skills = result["skills_copied"]
        console.print(f"[green]✓ Mode '{mode_name}' activated![/green]")
        console.print(f"[dim]Injected {len(skills)} skills: {', '.join(skills)}[/dim]")
        console.print(f"[dim]Skills directory: {target_dir}[/dim]\n")
    else:
        console.print(f"[red]✗ Failed to activate mode: {result.get('error')}[/red]\n")
    
    return result


async def _activate_sandbox_mode(
    manager: ModeManager,
    mode_name: str,
    mcp_tools: list,
    workspace_path: str | None,
) -> dict[str, Any]:
    """Activate mode by copying skills to sandbox via MCP."""
    # Find the file operations tool
    file_tool = None
    for tool in mcp_tools:
        if tool.name == "sandbox_file_operations":
            file_tool = tool
            break
    
    if not file_tool:
        console.print("[yellow]⚠ sandbox_file_operations tool not found[/yellow]")
        console.print("[dim]Falling back to local mode activation[/dim]")
        return {"success": False, "error": "MCP file tool not available"}
    
    # Determine sandbox skills directory
    sandbox_skills_dir = "/workspace/.deepagents/skills"
    if workspace_path:
        sandbox_skills_dir = f"{workspace_path}/.deepagents/skills"
    
    console.print(f"\n[dim]Activating mode: {mode_name} in sandbox...[/dim]")
    
    result = await manager.activate_mode_sandbox(
        mode_name, sandbox_skills_dir, file_tool
    )
    
    if result["success"]:
        skills = result["skills_copied"]
        console.print(f"[green]✓ Mode '{mode_name}' activated in sandbox![/green]")
        console.print(f"[dim]Injected {len(skills)} skills: {', '.join(skills)}[/dim]")
        console.print(f"[dim]Sandbox skills: {sandbox_skills_dir}[/dim]\n")
    else:
        console.print(f"[red]✗ Failed to activate mode: {result.get('error')}[/red]\n")
    
    return result
