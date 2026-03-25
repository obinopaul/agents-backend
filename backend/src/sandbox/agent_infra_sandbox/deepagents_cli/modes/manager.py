"""Mode manager for handling skill set injection.

This module provides the ModeManager class which:
- Lists available modes from skill_sets/ directory
- Activates modes by copying skill folders to the workspace
- Tracks the currently active mode for a session
"""

import shutil
from pathlib import Path
from typing import Any

from deepagents_cli.config import console, COLORS


# Available modes and their descriptions
AVAILABLE_MODES = {
    "data_scientist": {
        "display_name": "Data Scientist",
        "description": "Skills for EDA, visualization, and ML pipelines",
        "folder": "data_scientist",
    },
    "software_developer": {
        "display_name": "Software Developer",
        "description": "Skills for code review, testing, and development workflows",
        "folder": "software_developer",
    },
    "scientific_skills": {
        "display_name": "Scientific Skills",
        "description": "Skills for scientific research, analysis, and Data Science",
        "folder": "scientific_skills",
    },
    "basic": {
        "display_name": "Basic Skills",
        "description": "Skills for basic tasks",
        "folder": "basic",
    },
}


class ModeManager:
    """Manages mode activation and skill injection."""
    
    def __init__(self, skill_sets_dir: Path | None = None):
        """Initialize the mode manager.
        
        Args:
            skill_sets_dir: Path to skill sets directory. Defaults to modes/skill_sets/ 
                           relative to this module.
        """
        if skill_sets_dir is None:
            self.skill_sets_dir = Path(__file__).parent / "skill_sets"
        else:
            self.skill_sets_dir = Path(skill_sets_dir)
        
        self._current_mode: str | None = None
    
    @property
    def current_mode(self) -> str | None:
        """Get the currently active mode."""
        return self._current_mode
    
    def list_modes(self) -> list[dict[str, str]]:
        """List all available modes.
        
        Returns:
            List of dicts with 'name', 'display_name', 'description' keys
        """
        modes = []
        for mode_id, mode_info in AVAILABLE_MODES.items():
            mode_dir = self.skill_sets_dir / mode_info["folder"]
            available = mode_dir.exists()
            modes.append({
                "name": mode_id,
                "display_name": mode_info["display_name"],
                "description": mode_info["description"],
                "available": available,
            })
        return modes
    
    def get_mode_skills(self, mode_name: str) -> list[dict[str, Any]]:
        """Get list of skills in a mode.
        
        Args:
            mode_name: Name of the mode
            
        Returns:
            List of skill info dicts with 'name', 'path', 'has_scripts' keys
        """
        if mode_name not in AVAILABLE_MODES:
            return []
        
        mode_dir = self.skill_sets_dir / AVAILABLE_MODES[mode_name]["folder"]
        if not mode_dir.exists():
            return []
        
        skills = []
        for skill_dir in mode_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skills.append({
                        "name": skill_dir.name,
                        "path": str(skill_dir),
                        "has_scripts": (skill_dir / "scripts").exists(),
                    })
        return skills
    
    def activate_mode_local(
        self,
        mode_name: str,
        target_skills_dir: Path,
    ) -> dict[str, Any]:
        """Activate a mode by copying skills to local directory.
        
        Args:
            mode_name: Name of the mode to activate
            target_skills_dir: Local skills directory (e.g., ~/.deepagents/agent/skills/)
            
        Returns:
            Result dict with 'success', 'skills_copied', 'error' keys
        """
        if mode_name not in AVAILABLE_MODES:
            return {
                "success": False,
                "error": f"Unknown mode: {mode_name}. Use /mode list to see available modes.",
                "skills_copied": [],
            }
        
        mode_dir = self.skill_sets_dir / AVAILABLE_MODES[mode_name]["folder"]
        if not mode_dir.exists():
            return {
                "success": False,
                "error": f"Mode skill set not found at {mode_dir}",
                "skills_copied": [],
            }
        
        # Ensure target directory exists
        target_skills_dir = Path(target_skills_dir)
        target_skills_dir.mkdir(parents=True, exist_ok=True)
        
        skills_copied = []
        errors = []
        
        for skill_dir in mode_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                target_skill = target_skills_dir / skill_dir.name
                try:
                    if target_skill.exists():
                        shutil.rmtree(target_skill)
                    shutil.copytree(skill_dir, target_skill)
                    skills_copied.append(skill_dir.name)
                except Exception as e:
                    errors.append(f"{skill_dir.name}: {e}")
        
        self._current_mode = mode_name
        
        if errors:
            return {
                "success": False,
                "error": f"Some skills failed to copy: {', '.join(errors)}",
                "skills_copied": skills_copied,
            }
        
        return {
            "success": True,
            "skills_copied": skills_copied,
            "mode": mode_name,
        }
    
    async def activate_mode_sandbox(
        self,
        mode_name: str,
        sandbox_skills_dir: str,
        file_tool,
    ) -> dict[str, Any]:
        """Activate a mode by copying skills to sandbox via MCP.
        
        Args:
            mode_name: Name of the mode to activate
            sandbox_skills_dir: Path in sandbox (e.g., /workspace/.deepagents/skills/)
            file_tool: The sandbox_file_operations MCP tool
            
        Returns:
            Result dict with 'success', 'skills_copied', 'error' keys
        """
        if mode_name not in AVAILABLE_MODES:
            return {
                "success": False,
                "error": f"Unknown mode: {mode_name}",
                "skills_copied": [],
            }
        
        mode_dir = self.skill_sets_dir / AVAILABLE_MODES[mode_name]["folder"]
        if not mode_dir.exists():
            return {
                "success": False,
                "error": f"Mode skill set not found at {mode_dir}",
                "skills_copied": [],
            }
        
        skills_copied = []
        errors = []
        
        for skill_dir in mode_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_name = skill_dir.name
                try:
                    # Copy all files in the skill folder
                    for file_path in skill_dir.rglob("*"):
                        if file_path.is_file():
                            relative = file_path.relative_to(skill_dir)
                            target_path = f"{sandbox_skills_dir}/{skill_name}/{relative}"
                            content = file_path.read_text(encoding="utf-8", errors="replace")
                            
                            await file_tool.ainvoke({
                                "operation": "write",
                                "path": target_path,
                                "content": content,
                            })
                    
                    skills_copied.append(skill_name)
                except Exception as e:
                    errors.append(f"{skill_name}: {e}")
        
        self._current_mode = mode_name
        
        if errors:
            return {
                "success": False,
                "error": f"Some skills failed: {', '.join(errors)}",
                "skills_copied": skills_copied,
            }
        
        return {
            "success": True,
            "skills_copied": skills_copied,
            "mode": mode_name,
        }


def print_modes_list(modes: list[dict]) -> None:
    """Pretty print available modes."""
    console.print("\n[bold]Available Modes:[/bold]\n", style=COLORS["primary"])
    
    for mode in modes:
        status = "✓" if mode.get("available", True) else "✗"
        name = mode["name"]
        display = mode["display_name"]
        desc = mode["description"]
        
        console.print(f"  {status} [bold]{name}[/bold] ({display})", style=COLORS["primary"])
        console.print(f"    {desc}", style=COLORS["dim"])
    
    console.print("\n[dim]Use: /mode <name> to activate a mode[/dim]\n")
