"""Session command handlers for managing sandbox workspaces.

Provides CLI commands for:
- /session or /session list - List all sessions
- /session create <name> - Create new session
- /session connect <name> - Connect to existing session
- /session delete <name> - Delete session
- /session current - Show current session
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rich.table import Table

from deepagents_cli.config import console
from deepagents_cli.session_registry import SessionInfo, SessionRegistry

if TYPE_CHECKING:
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend


class SessionManager:
    """Manages sandbox sessions from within the CLI.
    
    Provides interactive commands for creating, listing, connecting to,
    and deleting sandbox workspace sessions.
    """
    
    def __init__(
        self, 
        registry: Optional[SessionRegistry] = None,
        backend: Optional["AgentInfraBackend"] = None,
    ) -> None:
        """Initialize session manager.
        
        Args:
            registry: Session registry (loads from disk if not provided)
            backend: Sandbox backend for workspace operations
        """
        self.registry = registry or SessionRegistry.load()
        self.backend = backend
        self._pending_session: Optional[str] = None
    
    def handle_command(self, args: list[str]) -> tuple[bool, Optional[str]]:
        """Handle a /session command.
        
        Args:
            args: Command arguments (e.g., ["create", "my-project"])
            
        Returns:
            Tuple of (handled: bool, switch_to_session: Optional[str])
            If switch_to_session is not None, the CLI should reconnect to that session
        """
        if not args or args[0] in ("list", "ls"):
            self._list_sessions()
            return True, None
        
        subcommand = args[0].lower()
        
        if subcommand == "create":
            if len(args) < 2:
                console.print("[red]Usage: /session create <name> [description][/red]")
                return True, None
            name = args[1]
            description = " ".join(args[2:]) if len(args) > 2 else ""
            return self._create_session(name, description)
        
        if subcommand in ("connect", "switch", "use"):
            if len(args) < 2:
                console.print("[red]Usage: /session connect <name>[/red]")
                return True, None
            return self._connect_session(args[1])
        
        if subcommand in ("delete", "rm", "remove"):
            if len(args) < 2:
                console.print("[red]Usage: /session delete <name> [--force][/red]")
                return True, None
            force = "--force" in args or "-f" in args
            return self._delete_session(args[1], force)
        
        if subcommand in ("current", "info"):
            self._show_current()
            return True, None
        
        # Unknown subcommand - show help
        self._show_help()
        return True, None
    
    def _list_sessions(self) -> None:
        """List all sessions in a table."""
        sessions = self.registry.list_sessions()
        active = self.registry.active_session
        
        if not sessions:
            console.print("[dim]No sessions found. Create one with: /session create <name>[/dim]")
            return
        
        table = Table(title="📁 Sandbox Sessions", show_header=True, header_style="bold cyan")
        table.add_column("", width=2)  # Active indicator
        table.add_column("Name", style="bold")
        table.add_column("Created", style="dim")
        table.add_column("Last Accessed", style="dim")
        table.add_column("Description")
        
        for session in sessions:
            is_active = "→" if session.name == active else ""
            from datetime import datetime
            # Format created time
            try:
                dt_created = datetime.fromisoformat(session.created_at)
                created_str = dt_created.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_str = session.created_at[:16] if session.created_at else ""
            # Format last accessed time
            try:
                dt_accessed = datetime.fromisoformat(session.last_accessed)
                accessed_str = dt_accessed.strftime("%Y-%m-%d %H:%M")
            except Exception:
                accessed_str = session.last_accessed[:16] if session.last_accessed else ""
            
            table.add_row(
                is_active,
                session.name,
                created_str,
                accessed_str,
                session.description or "-",
            )
        
        console.print()
        console.print(table)
        console.print()
        console.print("[dim]Use '/session connect <name>' to switch sessions[/dim]")
        console.print()
    
    def _create_session(self, name: str, description: str = "") -> tuple[bool, Optional[str]]:
        """Create a new session."""
        try:
            # Check if already exists
            if self.registry.get_session(name):
                console.print(f"[yellow]Session '{name}' already exists. Use '/session connect {name}' to switch.[/yellow]")
                return True, None
            
            # Create in registry
            session = self.registry.create_session(name, description)
            
            # Initialize workspace in sandbox if backend available
            if self.backend:
                self.backend.initialize_workspace(session_name=name, agent_name="agent")
            
            console.print()
            console.print(f"[green]✓ Created session: {name}[/green]")
            console.print(f"[dim]Workspace: {session.workspace_path}[/dim]")
            console.print("[yellow]Note: Restart CLI or use '/session connect' to activate the new session.[/yellow]")
            console.print()
            
            return True, name
            
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return True, None
    
    def _connect_session(self, name: str) -> tuple[bool, Optional[str]]:
        """Connect to an existing session."""
        session = self.registry.get_session(name)
        
        if not session:
            console.print(f"[red]Session '{name}' not found.[/red]")
            console.print("[dim]Use '/session list' to see available sessions.[/dim]")
            return True, None
        
        # Update active session in registry
        self.registry.set_active_session(name)
        
        console.print()
        console.print(f"[green]✓ Switching to session: {name}[/green]")
        console.print(f"[dim]Workspace: {session.workspace_path}[/dim]")
        console.print("[yellow]Please restart the CLI for the change to take effect.[/yellow]")
        console.print("[dim]Or exit and run: python -m deepagents_cli --session {name}[/dim]")
        console.print()
        
        # Signal that we want to switch sessions (requires CLI restart)
        self._pending_session = name
        return True, name
    
    def _delete_session(self, name: str, force: bool = False) -> tuple[bool, Optional[str]]:
        """Delete a session and its workspace files."""
        session = self.registry.get_session(name)
        
        if not session:
            console.print(f"[red]Session '{name}' not found.[/red]")
            return True, None
        
        if name == self.registry.active_session:
            console.print("[red]Cannot delete the active session. Switch to another session first.[/red]")
            return True, None
        
        # Always delete workspace files from sandbox
        if self.backend:
            self.backend.delete_workspace(name, force=True)
        
        # Remove from registry
        self.registry.delete_session(name)
        
        console.print()
        console.print(f"[green]✓ Deleted session and workspace: {name}[/green]")
        console.print()
        
        return True, None
    
    def _show_current(self) -> None:
        """Show current session info."""
        session = self.registry.get_active_session()
        
        if not session:
            console.print("[dim]No active session. Create one with: /session create <name>[/dim]")
            return
        
        console.print()
        console.print(f"[bold cyan]Current Session: {session.name}[/bold cyan]")
        console.print(f"  [dim]Created:[/dim] {session.created_at[:16]}")
        console.print(f"  [dim]Last Accessed:[/dim] {session.last_accessed[:16]}")
        console.print(f"  [dim]Workspace:[/dim] {session.workspace_path}")
        if session.description:
            console.print(f"  [dim]Description:[/dim] {session.description}")
        console.print()
    
    def _show_help(self) -> None:
        """Show session command help."""
        console.print()
        console.print("[bold cyan]Session Commands:[/bold cyan]")
        console.print()
        console.print("  [green]/session[/green] or [green]/session list[/green]")
        console.print("    List all sandbox sessions")
        console.print()
        console.print("  [green]/session create <name> [description][/green]")
        console.print("    Create a new isolated workspace session")
        console.print()
        console.print("  [green]/session connect <name>[/green]")
        console.print("    Switch to an existing session")
        console.print()
        console.print("  [green]/session delete <name> [--force][/green]")
        console.print("    Remove session (--force deletes workspace files)")
        console.print()
        console.print("  [green]/session current[/green]")
        console.print("    Show current active session")
        console.print()


# Global session manager instance (set by main.py)
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> Optional[SessionManager]:
    """Get the global session manager."""
    return _session_manager


def set_session_manager(manager: SessionManager) -> None:
    """Set the global session manager."""
    global _session_manager
    _session_manager = manager
