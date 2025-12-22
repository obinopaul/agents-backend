"""Command handlers for slash commands and bash execution."""

import subprocess
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from .config import COLORS, DEEP_AGENTS_ASCII, console
from .ui import TokenTracker, print_banner, show_interactive_help


def handle_command(command: str, agent, token_tracker: TokenTracker) -> str | bool:
    """Handle slash commands. Returns 'exit' to exit, True if handled, False to pass to agent."""
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
