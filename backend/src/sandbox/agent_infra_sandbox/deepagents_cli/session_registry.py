"""Session registry for managing sandbox workspace sessions.

This module provides local storage for sandbox sessions, allowing users to:
- Create named project sessions
- List existing sessions
- Connect to/switch between sessions
- Delete sessions

Sessions are stored locally at ~/.deepagents/sessions.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SessionInfo:
    """Information about a sandbox session."""
    
    name: str
    """Unique session name (e.g., 'calculator-project')"""
    
    created_at: str
    """ISO format timestamp of creation"""
    
    last_accessed: str
    """ISO format timestamp of last access"""
    
    workspace_path: str
    """Path to workspace in sandbox (e.g., '/home/gem/workspaces/calculator-project')"""
    
    shell_session_id: Optional[str] = None
    """Shell session ID for this workspace"""
    
    description: str = ""
    """Optional description of the session/project"""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "workspace_path": self.workspace_path,
            "shell_session_id": self.shell_session_id,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            workspace_path=data["workspace_path"],
            shell_session_id=data.get("shell_session_id"),
            description=data.get("description", ""),
        )


@dataclass
class SessionRegistry:
    """Registry for managing sandbox sessions.
    
    Stores session information locally at ~/.deepagents/sessions.json
    """
    
    sessions: dict[str, SessionInfo] = field(default_factory=dict)
    """Map of session name to session info"""
    
    active_session: Optional[str] = None
    """Currently active session name"""
    
    _registry_path: Path = field(default_factory=lambda: Path.home() / ".deepagents" / "sessions.json")
    
    # Default workspace base path in sandbox
    WORKSPACE_BASE = "/home/gem/workspaces"
    
    @classmethod
    def load(cls, registry_path: Optional[Path] = None) -> "SessionRegistry":
        """Load session registry from disk.
        
        Args:
            registry_path: Optional custom path to registry file
            
        Returns:
            Loaded SessionRegistry instance
        """
        path = registry_path or (Path.home() / ".deepagents" / "sessions.json")
        
        if not path.exists():
            # Create empty registry
            registry = cls(_registry_path=path)
            registry.save()
            return registry
        
        try:
            data = json.loads(path.read_text())
            sessions = {
                name: SessionInfo.from_dict(info)
                for name, info in data.get("sessions", {}).items()
            }
            return cls(
                sessions=sessions,
                active_session=data.get("active_session"),
                _registry_path=path,
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Corrupted file - start fresh
            registry = cls(_registry_path=path)
            registry.save()
            return registry
    
    def save(self) -> None:
        """Save session registry to disk."""
        # Ensure directory exists
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "sessions": {
                name: info.to_dict()
                for name, info in self.sessions.items()
            },
            "active_session": self.active_session,
        }
        
        self._registry_path.write_text(json.dumps(data, indent=2))
    
    def create_session(
        self,
        name: str,
        description: str = "",
    ) -> SessionInfo:
        """Create a new session.
        
        Args:
            name: Unique session name
            description: Optional description
            
        Returns:
            Created SessionInfo
            
        Raises:
            ValueError: If session already exists
        """
        if name in self.sessions:
            raise ValueError(f"Session '{name}' already exists")
        
        # Validate name (alphanumeric, hyphens, underscores only)
        if not name or not all(c.isalnum() or c in "-_" for c in name):
            raise ValueError(
                f"Invalid session name '{name}'. "
                "Use only alphanumeric characters, hyphens, and underscores."
            )
        
        now = datetime.now().isoformat()
        workspace_path = f"{self.WORKSPACE_BASE}/{name}"
        
        session = SessionInfo(
            name=name,
            created_at=now,
            last_accessed=now,
            workspace_path=workspace_path,
            description=description,
        )
        
        self.sessions[name] = session
        self.active_session = name
        self.save()
        
        return session
    
    def get_session(self, name: str) -> Optional[SessionInfo]:
        """Get session by name."""
        return self.sessions.get(name)
    
    def get_active_session(self) -> Optional[SessionInfo]:
        """Get currently active session."""
        if self.active_session:
            return self.sessions.get(self.active_session)
        return None
    
    def set_active_session(self, name: str) -> SessionInfo:
        """Set the active session.
        
        Args:
            name: Session name to activate
            
        Returns:
            The activated SessionInfo
            
        Raises:
            ValueError: If session doesn't exist
        """
        if name not in self.sessions:
            raise ValueError(f"Session '{name}' not found")
        
        self.active_session = name
        self.sessions[name].last_accessed = datetime.now().isoformat()
        self.save()
        
        return self.sessions[name]
    
    def delete_session(self, name: str) -> bool:
        """Delete a session from registry.
        
        Note: This only removes from registry, not the actual workspace files.
        
        Args:
            name: Session name to delete
            
        Returns:
            True if deleted, False if not found
        """
        if name not in self.sessions:
            return False
        
        del self.sessions[name]
        
        if self.active_session == name:
            self.active_session = None
        
        self.save()
        return True
    
    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions sorted by last accessed (most recent first)."""
        return sorted(
            self.sessions.values(),
            key=lambda s: s.last_accessed,
            reverse=True,
        )
    
    def get_or_create_default(self) -> SessionInfo:
        """Get or create a default session.
        
        Returns the active session if one exists, otherwise creates
        a 'default' session.
        """
        if self.active_session and self.active_session in self.sessions:
            return self.sessions[self.active_session]
        
        if "default" in self.sessions:
            return self.set_active_session("default")
        
        return self.create_session("default", "Default workspace session")
