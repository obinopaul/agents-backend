"""Skill category configuration for agent sandboxes.

Three agent categories, each maps to ONE skill folder:
- general (default): basic skills for general-purpose agents
- scientific: scientific_skills for research & analysis
- academic: scientific_writer for academic writing & publishing

Usage:
    from backend.src.config.skill_config import get_skill_folder, AgentCategory
    
    folder = get_skill_folder("scientific")  # Returns "scientific_skills"
"""

from typing import Literal, get_args

# Type for valid agent categories
AgentCategory = Literal["general", "scientific", "academic"]

# Category to skill folder mapping (each category = ONE folder)
CATEGORY_SKILL_FOLDER: dict[AgentCategory, str] = {
    "general": "basic",
    "scientific": "scientific_skills",
    "academic": "scientific_writer",
}

# Default category when none specified
DEFAULT_CATEGORY: AgentCategory = "general"

# Valid categories for validation
VALID_CATEGORIES: tuple[str, ...] = get_args(AgentCategory)


def get_skill_folder(category: AgentCategory | str | None = None) -> str:
    """Get the skill folder name for an agent category.
    
    Args:
        category: Agent category ("general", "scientific", "academic").
                  Defaults to "general" if None or invalid.
    
    Returns:
        Skill folder name (e.g., "basic", "scientific_skills", "scientific_writer")
    
    Examples:
        >>> get_skill_folder("general")
        'basic'
        >>> get_skill_folder("scientific")
        'scientific_skills'
        >>> get_skill_folder("academic")
        'scientific_writer'
        >>> get_skill_folder(None)
        'basic'
    """
    if category is None or category not in VALID_CATEGORIES:
        category = DEFAULT_CATEGORY
    return CATEGORY_SKILL_FOLDER[category]  # type: ignore[index]


def is_valid_category(category: str | None) -> bool:
    """Check if a category string is valid.
    
    Args:
        category: Category string to validate.
    
    Returns:
        True if category is valid, False otherwise.
    """
    return category in VALID_CATEGORIES
