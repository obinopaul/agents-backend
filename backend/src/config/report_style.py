"""Report style configuration for content generation.

This module defines the available report styles that influence
how AI content is generated and enhanced.
"""

from enum import Enum


class ReportStyle(str, Enum):
    """Report styles for content generation.
    
    Each style influences the tone, structure, and vocabulary
    used in generated content.
    """
    
    ACADEMIC = "academic"
    """Academic style: formal, detailed, well-cited."""
    
    POPULAR_SCIENCE = "popular_science"
    """Popular science style: accessible, engaging, educational."""
    
    NEWS = "news"
    """News style: concise, factual, objective."""
    
    SOCIAL_MEDIA = "social_media"
    """Social media style: brief, catchy, shareable."""
    
    STRATEGIC_INVESTMENT = "strategic_investment"
    """Strategic investment style: analytical, data-driven, actionable."""
