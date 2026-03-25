"""Async skill loader for sandbox environments.

This module provides async functions to load skills from a remote sandbox
using the sandbox's file system API (run_cmd, read_file) instead of local paths.

Usage:
    from backend.src.agents.middleware.skills_middleware.sandbox_load import (
        list_skills_from_sandbox
    )
    
    skills = await list_skills_from_sandbox(sandbox)
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox

from backend.src.agents.middleware.skills_middleware.load import (
    MAX_SKILL_DESCRIPTION_LENGTH,
    MAX_SKILL_FILE_SIZE,
    SkillMetadata,
)

logger = logging.getLogger(__name__)

# Default skills directory in sandbox
DEFAULT_SANDBOX_SKILLS_DIR = "/workspace/.deepagents/skills"


def _parse_skill_metadata_from_content(
    content: str,
    skill_md_path: str,
    source: str = "sandbox",
) -> SkillMetadata | None:
    """Parse YAML frontmatter from SKILL.md content.
    
    This is adapted from load.py's _parse_skill_metadata but works with
    content strings instead of file paths.
    
    Args:
        content: The SKILL.md file content as string.
        skill_md_path: Path to the SKILL.md file (for metadata).
        source: Source identifier (default: "sandbox").
    
    Returns:
        SkillMetadata if parsing succeeds, None otherwise.
    """
    try:
        # Check content size
        if len(content) > MAX_SKILL_FILE_SIZE:
            logger.warning("Skipping %s: content too large", skill_md_path)
            return None

        # Match YAML frontmatter between --- delimiters
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            logger.warning("Skipping %s: no valid YAML frontmatter found", skill_md_path)
            return None

        frontmatter_str = match.group(1)

        # Parse YAML
        try:
            frontmatter_data = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML in %s: %s", skill_md_path, e)
            return None

        if not isinstance(frontmatter_data, dict):
            logger.warning("Skipping %s: frontmatter is not a mapping", skill_md_path)
            return None

        # Validate required fields
        name = frontmatter_data.get("name")
        description = frontmatter_data.get("description")

        if not name or not description:
            logger.warning(
                "Skipping %s: missing required 'name' or 'description'", skill_md_path
            )
            return None

        # Truncate description if needed
        description_str = str(description)
        if len(description_str) > MAX_SKILL_DESCRIPTION_LENGTH:
            description_str = description_str[:MAX_SKILL_DESCRIPTION_LENGTH]

        return SkillMetadata(
            name=str(name),
            description=description_str,
            path=skill_md_path,
            source=source,
            license=frontmatter_data.get("license"),
            compatibility=frontmatter_data.get("compatibility"),
            metadata=frontmatter_data.get("metadata"),
            allowed_tools=frontmatter_data.get("allowed-tools"),
        )

    except Exception as e:
        logger.warning("Error parsing %s: %s", skill_md_path, e)
        return None


async def list_skills_from_sandbox(
    sandbox: "BaseSandbox",
    skills_dir: str = DEFAULT_SANDBOX_SKILLS_DIR,
) -> list[SkillMetadata]:
    """List skills from a sandbox filesystem.
    
    Uses sandbox.run_cmd() to list directories and sandbox.read_file() to
    read SKILL.md contents. This is the async/sandbox equivalent of load.py's
    list_skills() function.
    
    Args:
        sandbox: The sandbox instance to read skills from.
        skills_dir: Path to skills directory in sandbox (default: /workspace/.deepagents/skills).
    
    Returns:
        List of SkillMetadata for all valid skills found.
    
    Example:
        >>> skills = await list_skills_from_sandbox(sandbox)
        >>> for skill in skills:
        ...     print(f"{skill['name']}: {skill['description']}")
    """
    skills: list[SkillMetadata] = []
    
    try:
        # Check if skills directory exists
        check_result = await sandbox.run_cmd(f"test -d {skills_dir} && echo 'exists' || echo 'missing'")
        if "missing" in check_result:
            logger.info("Skills directory %s not found in sandbox", skills_dir)
            return []
        
        # List subdirectories (skill folders)
        result = await sandbox.run_cmd(f"ls -1 {skills_dir} 2>/dev/null || true")
        
        if not result or not result.strip():
            logger.info("No skills found in %s", skills_dir)
            return []
        
        skill_names = [name.strip() for name in result.strip().split("\n") if name.strip()]
        
        for skill_name in skill_names:
            skill_md_path = f"{skills_dir}/{skill_name}/SKILL.md"
            
            try:
                # Read SKILL.md content from sandbox
                content = await sandbox.read_file(skill_md_path)
                
                if not content:
                    continue
                
                # Parse metadata from content
                metadata = _parse_skill_metadata_from_content(
                    content=content,
                    skill_md_path=skill_md_path,
                    source="sandbox",
                )
                
                if metadata:
                    skills.append(metadata)
                    logger.debug("Loaded skill: %s from %s", metadata["name"], skill_md_path)
                    
            except Exception as e:
                logger.debug("Could not read skill %s: %s", skill_name, e)
                continue
        
        logger.info("Loaded %d skills from sandbox", len(skills))
        return skills
        
    except Exception as e:
        logger.warning("Error listing skills from sandbox: %s", e)
        return []


async def get_skill_content(
    sandbox: "BaseSandbox",
    skill_name: str,
    skills_dir: str = DEFAULT_SANDBOX_SKILLS_DIR,
) -> str | None:
    """Get the full SKILL.md content for a specific skill.
    
    Args:
        sandbox: The sandbox instance.
        skill_name: Name of the skill to read.
        skills_dir: Path to skills directory in sandbox.
    
    Returns:
        Full SKILL.md content as string, or None if not found.
    """
    skill_md_path = f"{skills_dir}/{skill_name}/SKILL.md"
    
    try:
        content = await sandbox.read_file(skill_md_path)
        return content if content else None
    except Exception as e:
        logger.warning("Could not read skill %s: %s", skill_name, e)
        return None


def format_skills_for_prompt(
    skills: list[SkillMetadata],
    skills_dir: str = DEFAULT_SANDBOX_SKILLS_DIR,
) -> str:
    """Format skills metadata into a prompt section for injection into system prompt.
    
    This creates a human-readable section that informs the agent about available
    skills and how to use them.
    
    Args:
        skills: List of skill metadata from list_skills_from_sandbox().
        skills_dir: Path to skills directory for display.
    
    Returns:
        Formatted string ready for injection into system prompt.
        Empty string if no skills available.
    
    Example output:
        ## Available Skills
        
        You have access to the following skills in `/workspace/.deepagents/skills`:
        
        - **web-research**: Research topics using web search and summarization
          → Read `/workspace/.deepagents/skills/web-research/SKILL.md` for instructions
        
        - **code-review**: Review code and suggest improvements
          → Read `/workspace/.deepagents/skills/code-review/SKILL.md` for instructions
    """
    if not skills:
        return ""
    
    lines = [
        "",
        "## Available Skills",
        "",
        f"You have access to the following skills in `{skills_dir}`:",
        "",
    ]
    
    for skill in skills:
        name = skill.get("name", "unknown")
        description = skill.get("description", "No description")
        path = skill.get("path", f"{skills_dir}/{name}/SKILL.md")
        
        lines.append(f"- **{name}**: {description}")
        lines.append(f"  → Read `{path}` for full instructions")
        lines.append("")
    
    lines.append("When a task matches a skill, read the SKILL.md file for detailed instructions.")
    lines.append("")
    
    return "\n".join(lines)

