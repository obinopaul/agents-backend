"""Command handlers for slash commands and bash execution."""

import subprocess
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from .config import COLORS, DEEP_AGENTS_ASCII, console
from .ui import TokenTracker, print_banner, show_interactive_help


def _inject_mode_to_sandbox(
    manager,
    mode_name: str,
    workspace_path: str,
    mcp_tools: list,
) -> dict:
    """Inject mode skills to sandbox workspace via MCP.
    
    Uses synchronous wrapper to call async MCP sandbox_file_operations tool.
    
    Args:
        manager: ModeManager instance
        mode_name: Name of the mode to activate
        workspace_path: Sandbox workspace path (e.g., /home/gem/workspaces/session-xxx)
        mcp_tools: List of MCP tools (looking for sandbox_file_operations)
        
    Returns:
        Result dict with 'success', 'skills_copied', 'error' keys
    """
    import asyncio
    
    # Find the file operations tool (name may be 'file_operations' or 'sandbox_file_operations')
    file_tool = None
    for tool in mcp_tools:
        if tool.name in ("file_operations", "sandbox_file_operations"):
            file_tool = tool
            break
    
    if not file_tool:
        # List available tools for debugging
        tool_names = [t.name for t in mcp_tools[:10]]
        return {
            "success": False,
            "error": f"file_operations tool not found. Available: {', '.join(tool_names)}...",
            "skills_copied": [],
        }
    
    # Get skill folders from mode
    from deepagents_cli.modes.manager import AVAILABLE_MODES
    
    if mode_name not in AVAILABLE_MODES:
        return {
            "success": False,
            "error": f"Unknown mode: {mode_name}",
            "skills_copied": [],
        }
    
    mode_dir = manager.skill_sets_dir / AVAILABLE_MODES[mode_name]["folder"]
    if not mode_dir.exists():
        return {
            "success": False,
            "error": f"Mode skill set not found at {mode_dir}",
            "skills_copied": [],
        }
    
    sandbox_skills_dir = f"{workspace_path}/.deepagents/skills"
    skills_copied = []
    errors = []
    
    async def inject_skill(skill_dir):
        """Inject a single skill folder to sandbox."""
        skill_name = skill_dir.name
        files_written = 0
        
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                # Use as_posix() to convert Windows backslashes to Linux forward slashes
                relative = file_path.relative_to(skill_dir).as_posix()
                target_path = f"{sandbox_skills_dir}/{skill_name}/{relative}"
                
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    # Use 'action' parameter (not 'operation')
                    await file_tool.ainvoke({
                        "action": "write",
                        "path": target_path,
                        "content": content,
                    })
                    files_written += 1
                except Exception as e:
                    raise Exception(f"Failed to write {target_path}: {e}")
        
        return skill_name, files_written
    
    async def inject_all_skills():
        """Inject all skills from mode to sandbox."""
        nonlocal skills_copied, errors
        
        for skill_dir in mode_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                try:
                    skill_name, _ = await inject_skill(skill_dir)
                    skills_copied.append(skill_name)
                except Exception as e:
                    errors.append(str(e))
    
    # Run async injection in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, inject_all_skills())
                future.result(timeout=120)  # 2 minute timeout
        else:
            loop.run_until_complete(inject_all_skills())
    except Exception as e:
        errors.append(f"Injection failed: {e}")
    
    if errors and not skills_copied:
        return {
            "success": False,
            "error": "; ".join(errors),
            "skills_copied": skills_copied,
        }
    
    if errors:
        return {
            "success": True,
            "skills_copied": skills_copied,
            "warning": f"Some skills had errors: {'; '.join(errors)}",
        }
    
    return {
        "success": True,
        "skills_copied": skills_copied,
    }


def handle_command(
    command: str, 
    agent, 
    token_tracker: TokenTracker,
    sandbox_type: str | None = None,
    workspace_path: str | None = None,
    mcp_tools: list | None = None,
) -> str | bool:
    """Handle slash commands. Returns 'exit' to exit, True if handled, False to pass to agent.
    
    Args:
        command: The slash command string
        agent: The agent instance
        token_tracker: Token tracking instance
        sandbox_type: Type of sandbox (e.g., "agent_infra") or None for local
        workspace_path: Sandbox workspace path for skill injection
        mcp_tools: List of MCP tools for sandbox file operations
    """
    cmd = command.lower().strip().lstrip("/")
    parts = command.strip().lstrip("/").split()
    
    if cmd in ["quit", "exit", "q"]:
        return "exit"

    if cmd == "clear":
        # Reset agent conversation state
        agent.checkpointer = InMemorySaver()

        # Reset token tracking to baseline
        token_tracker.reset()

        # Clear screen and show fresh UI
        console.clear()
        print_banner()
        console.print(
            "... Fresh start! Screen cleared and conversation reset.", style=COLORS["agent"]
        )
        console.print()
        return True

    if cmd == "help":
        show_interactive_help()
        return True

    if cmd == "tokens":
        token_tracker.display_session()
        return True
    
    # Session management commands
    if parts and parts[0].lower() == "session":
        from deepagents_cli.session_commands import get_session_manager
        manager = get_session_manager()
        if manager:
            handled, _ = manager.handle_command(parts[1:] if len(parts) > 1 else [])
            return handled
        console.print("[yellow]Session manager not available.[/yellow]")
        return True
    
    # Model commands - show available models or switch model
    if parts and parts[0].lower() in ("models", "model"):
        import os
        from deepagents_cli.config import settings
        
        subcommand = parts[1].lower() if len(parts) > 1 else "list"
        
        if subcommand == "use" and len(parts) > 2:
            model_name = parts[2]
            # Determine which provider to set based on model name
            if model_name.startswith("gpt") or model_name.startswith("o1"):
                os.environ["OPENAI_MODEL"] = model_name
                console.print(f"[green]✓ Set model to: {model_name}[/green]")
                console.print("[yellow]Note: Restart CLI to use the new model.[/yellow]")
            elif model_name.startswith("claude"):
                os.environ["ANTHROPIC_MODEL"] = model_name
                console.print(f"[green]✓ Set model to: {model_name}[/green]")
                console.print("[yellow]Note: Restart CLI to use the new model.[/yellow]")
            elif model_name.startswith("gemini"):
                os.environ["GOOGLE_MODEL"] = model_name
                console.print(f"[green]✓ Set model to: {model_name}[/green]")
                console.print("[yellow]Note: Restart CLI to use the new model.[/yellow]")
            else:
                console.print(f"[red]Unknown model: {model_name}[/red]")
            return True
        
        # Show available models with correct priority indication
        console.print()
        console.print("[bold cyan]Available Models:[/bold cyan]")
        console.print()
        
        # Determine which provider is currently active (priority: OpenAI > Anthropic > Google)
        current_provider = None
        current_model = None
        if settings.has_openai:
            current_provider = "openai"
            current_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        elif settings.has_anthropic:
            current_provider = "anthropic"
            current_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        elif settings.has_google:
            current_provider = "google"
            current_model = os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash")
        
        # Show providers
        if settings.has_openai:
            active_marker = " ← active" if current_provider == "openai" else ""
            console.print(f"  [green]✓ OpenAI{active_marker}[/green]")
            models = ["gpt-4o", "gpt-4o-mini", "o1", "o1-mini"]
            for m in models:
                marker = " [cyan](current)[/cyan]" if m == current_model else ""
                console.print(f"    {m}{marker}")
        else:
            console.print("  [dim]✗ OpenAI (no API key)[/dim]")
            
        if settings.has_anthropic:
            active_marker = " ← active" if current_provider == "anthropic" else ""
            console.print(f"  [green]✓ Anthropic{active_marker}[/green]")
            models = ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]
            for m in models:
                marker = " [cyan](current)[/cyan]" if m == current_model else ""
                console.print(f"    {m}{marker}")
        else:
            console.print("  [dim]✗ Anthropic (no API key)[/dim]")
            
        if settings.has_google:
            active_marker = " ← active" if current_provider == "google" else ""
            console.print(f"  [green]✓ Google{active_marker}[/green]")
            models = ["gemini-2.0-flash", "gemini-1.5-pro"]
            for m in models:
                marker = " [cyan](current)[/cyan]" if m == current_model else ""
                console.print(f"    {m}{marker}")
        else:
            console.print("  [dim]✗ Google (no API key)[/dim]")
        
        console.print()
        console.print("[dim]To switch models: /model use <model-name>[/dim]")
        console.print("[dim]Priority: OpenAI > Anthropic > Google (first available is used)[/dim]")
        console.print()
        return True

    # Mode management commands
    if parts and parts[0].lower() == "mode":
        from deepagents_cli.modes.manager import ModeManager, print_modes_list
        
        manager = ModeManager()
        
        # Parse flags and mode name
        # Syntax: /mode [--sandbox|--local|--all] <mode_name>
        # Also: /mode list, /mode help
        flags = []
        remaining_args = []
        for arg in parts[1:]:
            if arg.startswith("--") or arg.startswith("-"):
                flags.append(arg.lower().lstrip("-"))
            else:
                remaining_args.append(arg)
        
        subcommand = remaining_args[0].lower() if remaining_args else ("help" if not flags else None)
        
        # Help
        if subcommand in ("help", "-h", "--help") or "help" in flags or "h" in flags:
            console.print("\n[bold]Mode Management[/bold]\n", style=COLORS["primary"])
            console.print("Modes are pre-configured skill sets that enhance the agent.\n")
            console.print("[bold]Commands:[/bold]")
            console.print("  /mode list                      List available modes")
            console.print("  /mode <name>                    Activate mode (default target)")
            console.print("  /mode --sandbox <name>          Inject to sandbox workspace only")
            console.print("  /mode --local <name>            Inject to local .deepagents/skills/ only")
            console.print("  /mode --all <name>              Inject to both sandbox and local")
            console.print("\n[bold]Available Modes:[/bold]")
            for mode in manager.list_modes():
                status = "✓" if mode.get("available", True) else "✗"
                console.print(f"  {status} {mode['name']:<20} {mode['description']}")
            if sandbox_type:
                console.print(f"\n[dim]Default target: sandbox ({workspace_path})[/dim]")
            else:
                console.print("\n[dim]Default target: local (.deepagents/skills/)[/dim]")
            console.print()
            return True
        
        # List
        if subcommand == "list" or "list" in flags:
            modes = manager.list_modes()
            print_modes_list(modes)
            return True
        
        # No mode name provided
        if not subcommand:
            console.print("\n[red]Please specify a mode name.[/red]")
            console.print("[dim]Usage: /mode [--sandbox|--local|--all] <mode_name>[/dim]")
            console.print("[dim]Try: /mode list[/dim]\n")
            return True
        
        mode_name = subcommand
        available_modes = [m["name"] for m in manager.list_modes()]
        
        if mode_name not in available_modes:
            console.print(f"\n[red]Unknown mode: {mode_name}[/red]")
            console.print(f"[dim]Available: {', '.join(available_modes)}[/dim]\n")
            return True
        
        # Determine injection targets based on flags
        inject_sandbox = False
        inject_local = False
        
        if "all" in flags:
            inject_sandbox = True
            inject_local = True
        elif "sandbox" in flags:
            inject_sandbox = True
        elif "local" in flags:
            inject_local = True
        else:
            # Default: sandbox if available, otherwise local
            if sandbox_type == "agent_infra" and mcp_tools and workspace_path:
                inject_sandbox = True
            else:
                inject_local = True
        
        results = []
        
        # Inject to sandbox
        if inject_sandbox:
            if sandbox_type == "agent_infra" and mcp_tools and workspace_path:
                console.print(f"\n[dim]Injecting '{mode_name}' to sandbox...[/dim]")
                result = _inject_mode_to_sandbox(manager, mode_name, workspace_path, mcp_tools)
                if result["success"]:
                    skills = result["skills_copied"]
                    console.print(f"[green]✓ Sandbox: Injected {len(skills)} skills to {workspace_path}/.deepagents/skills/[/green]")
                    results.append(("sandbox", True, skills))
                else:
                    console.print(f"[red]✗ Sandbox injection failed: {result.get('error')}[/red]")
                    results.append(("sandbox", False, []))
            else:
                console.print("[yellow]⚠ Sandbox not available (use --sandbox agent_infra flag when starting CLI)[/yellow]")
                results.append(("sandbox", False, []))
        
        # Inject locally
        if inject_local:
            target_dir = Path.cwd() / ".deepagents" / "skills"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            console.print(f"\n[dim]Injecting '{mode_name}' locally...[/dim]" if not inject_sandbox else f"[dim]Injecting '{mode_name}' locally...[/dim]")
            result = manager.activate_mode_local(mode_name, target_dir)
            if result["success"]:
                skills = result["skills_copied"]
                console.print(f"[green]✓ Local: Injected {len(skills)} skills to {target_dir}[/green]")
                results.append(("local", True, skills))
            else:
                console.print(f"[red]✗ Local injection failed: {result.get('error')}[/red]")
                results.append(("local", False, []))
        
        # Summary
        successes = [r for r in results if r[1]]
        if successes:
            console.print(f"\n[green]✓ Mode '{mode_name}' activated![/green]")
        else:
            console.print(f"\n[red]✗ Mode '{mode_name}' activation failed[/red]")
        console.print()
        
        return True

    console.print()
    console.print(f"[yellow]Unknown command: /{parts[0] if parts else cmd}[/yellow]")
    console.print("[dim]Type /help for available commands.[/dim]")
    console.print()
    return True


def execute_bash_command(command: str) -> bool:
    """Execute a bash command and display output. Returns True if handled."""
    cmd = command.strip().lstrip("!")

    if not cmd:
        return True

    try:
        console.print()
        console.print(f"[dim]$ {cmd}[/dim]")

        # Execute the command
        result = subprocess.run(
            cmd, check=False, shell=True, capture_output=True, text=True, timeout=30, cwd=Path.cwd()
        )

        # Display output
        if result.stdout:
            console.print(result.stdout, style=COLORS["dim"], markup=False)
        if result.stderr:
            console.print(result.stderr, style="red", markup=False)

        # Show return code if non-zero
        if result.returncode != 0:
            console.print(f"[dim]Exit code: {result.returncode}[/dim]")

        console.print()
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]Command timed out after 30 seconds[/red]")
        console.print()
        return True
    except Exception as e:
        console.print(f"[red]Error executing command: {e}[/red]")
        console.print()
        return True
