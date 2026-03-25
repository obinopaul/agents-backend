"""Slide template initialization tool for creating presentations from templates."""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any

from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.workspace import WorkspaceManager


NAME = "slide_template_init"
DISPLAY_NAME = "Initialize slide presentation from template"

DESCRIPTION = """Initializes a new presentation from pre-designed professional templates.

## Overview
This tool scaffolds a complete presentation from beautiful, professionally-designed HTML templates. 
Instead of creating slides from scratch, start with a polished template and customize it.

## Available Templates (18 options)

### Professional & Corporate
- **minimalist** - Clean, modern design with neutral colors. Perfect for business presentations.
- **minimalist_2** - Alternative minimal style with subtle accents.
- **black_and_white_clean** - Formal B&W design for legal, corporate, or serious topics.
- **premium_black** - Luxury dark theme for premium products or executive presentations.
- **premium_green** - Premium eco-friendly theme with sophisticated green accents.

### Data & Analytics
- **numbers_clean** - Clean design optimized for charts, graphs, and statistics.
- **numbers_colorful** - Vibrant data visualization with colorful charts.
- **competitor_analysis_blue** - Blue-themed for market research and competitive analysis.

### Startup & Business
- **startup** - Modern startup pitch deck with scaling/growth visuals.
- **elevator_pitch** - Concise format for quick investor pitches.

### Creative & Portfolio
- **colorful** - Vibrant multi-color design for creative/marketing content.
- **hipster** - Trendy, creative agency style with unique typography.
- **portfolio** - Showcase layout for creative work and case studies.
- **architect** - Professional architecture/construction theme.

### Academic & Educational
- **professor_gray** - Academic theme for lectures and research presentations.
- **textbook** - Educational style for tutorials and learning content.

### Industry-Specific
- **gamer_gray** - Dark theme for gaming, tech, and entertainment.
- **green** - Nature/sustainability theme for eco-friendly topics.

## Usage
1. Choose a template that matches your presentation's tone and purpose
2. Provide a presentation name (will be used as directory name)
3. The template will be copied to `presentations/<your_name>/`
4. All slides are editable HTML - customize content while keeping the design

## Post-Initialization
After initialization, use SlideWrite or SlideEdit to:
- Modify slide content (text, images)
- Add new slides following the template's style
- Remove slides you don't need
"""

# Template descriptions for AI context
TEMPLATE_DESCRIPTIONS = {
    "architect": "Professional architecture/construction theme with geometric shapes and clean lines. 17 slides covering: title, philosophy, company profile, vision/mission, services, team, portfolio, workflow, and contact.",
    "black_and_white_clean": "Formal black and white design for corporate, legal, or serious presentations. 11 slides with high contrast minimalist aesthetic.",
    "colorful": "Vibrant multi-color design for marketing, creative, and announcement content. 19 slides with dynamic color transitions and bold typography.",
    "competitor_analysis_blue": "Blue-themed business template for market research and competitive analysis. 7 slides focused on data comparison and strategic insights.",
    "elevator_pitch": "Concise startup pitch format with impactful slide layouts. 8 slides designed for quick, memorable presentations.",
    "gamer_gray": "Dark gaming/tech theme with modern, edgy aesthetics. 7 slides perfect for gaming, esports, or technology content.",
    "green": "Nature and sustainability theme for eco-friendly topics. 12 slides with organic shapes and nature-inspired design.",
    "hipster": "Trendy creative agency style with unique typography and layout. 16 slides featuring artistic design elements.",
    "minimalist": "Clean, modern design with neutral colors for business presentations. 13 slides including company profile, team, services, and contact sections.",
    "minimalist_2": "Alternative minimal style with subtle design accents. 14 slides with refined typography and whitespace.",
    "numbers_clean": "Clean design optimized for data, charts, and statistics. 11 slides built for financial reports and data presentations.",
    "numbers_colorful": "Colorful data visualization with vibrant chart designs. 11 slides making data engaging and accessible.",
    "portfolio": "Creative portfolio layout for showcasing work and case studies. 14 slides designed to highlight creative projects.",
    "premium_black": "Luxury dark theme for premium products and executive presentations. 12 slides with sophisticated dark aesthetic.",
    "premium_green": "Premium eco-brand theme with sophisticated green accents. 10 slides combining elegance with sustainability.",
    "professor_gray": "Academic theme for lectures, research, and educational content. 13 slides with scholarly design appropriate for academia.",
    "startup": "Modern startup pitch deck with growth and scaling visuals. 15 slides covering problem, solution, market, team, and financials.",
    "textbook": "Educational style for tutorials, courses, and learning content. 11 slides designed for instructional material.",
}

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "presentation_name": {
            "type": "string",
            "description": "Name for your presentation (lowercase, no spaces, use hyphens if needed). Example: `quarterly-report`, `product-launch`",
        },
        "template": {
            "type": "string",
            "description": "Template to use for the presentation",
            "enum": list(TEMPLATE_DESCRIPTIONS.keys()),
        },
    },
    "required": ["presentation_name", "template"],
}


def get_slides_root() -> Path:
    """Get the slides templates root directory.
    
    In E2B sandbox: /app/agents_backend/.slides
    In local development: Project root /.slides
    """
    # E2B sandbox path
    sandbox_path = Path("/app/agents_backend/.slides")
    if sandbox_path.exists():
        return sandbox_path
    
    # Alternative sandbox path
    alt_sandbox_path = Path("/app/.slides")
    if alt_sandbox_path.exists():
        return alt_sandbox_path
    
    # Local development - find via PYTHONPATH
    pythonpath = os.getenv("PYTHONPATH", "")
    for path in pythonpath.split(":"):
        p = Path(path)
        if p.exists():
            # Check current path
            slides_path = p / ".slides"
            if slides_path.exists():
                return slides_path
            # Check parent directories
            parent = p.parent
            while parent != parent.parent:
                slides_path = parent / ".slides"
                if slides_path.exists():
                    return slides_path
                parent = parent.parent
    
    # Last resort: try common development paths
    common_paths = [
        Path.cwd() / ".slides",
        Path.cwd().parent / ".slides",
    ]
    for p in common_paths:
        if p.exists():
            return p
    
    raise Exception(
        "Failed to find .slides directory. "
        "Expected at /app/agents_backend/.slides/ in sandbox or in project root locally."
    )


class SlideTemplateInitTool(BaseTool):
    """Tool for initializing presentations from templates."""
    
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False
    
    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        super().__init__()
        self.workspace_manager = workspace_manager
        self.presentations_dir = "presentations"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize presentation name for filesystem."""
        # Replace spaces and hyphens with underscores
        sanitized = name.replace(" ", "_").replace("-", "_")
        # Keep only alphanumeric and underscore
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
        # Ensure lowercase
        return sanitized.lower()
    
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the slide template initialization."""
        presentation_name = tool_input["presentation_name"]
        template = tool_input["template"]
        
        # Validate template exists
        if template not in TEMPLATE_DESCRIPTIONS:
            available = ", ".join(sorted(TEMPLATE_DESCRIPTIONS.keys()))
            return ToolResult(
                llm_content=f"Unknown template '{template}'. Available templates: {available}",
                user_display_content=f"Unknown template '{template}'",
                is_error=True,
            )
        
        # Get paths
        workspace_path = Path(self.workspace_manager.get_workspace_path())
        safe_name = self._sanitize_name(presentation_name)
        presentation_dir = workspace_path / self.presentations_dir / safe_name
        
        # Check if presentation already exists
        if presentation_dir.exists():
            return ToolResult(
                llm_content=(
                    f"Presentation '{safe_name}' already exists at {presentation_dir}. "
                    "Please choose a different name or delete the existing presentation first."
                ),
                user_display_content=f"Presentation '{safe_name}' already exists",
                is_error=True,
            )
        
        # Get template directory
        try:
            slides_root = get_slides_root()
        except Exception as e:
            return ToolResult(
                llm_content=str(e),
                user_display_content="Failed to find templates directory",
                is_error=True,
            )
        
        template_dir = slides_root / template
        if not template_dir.exists():
            return ToolResult(
                llm_content=f"Template directory not found: {template_dir}",
                user_display_content=f"Template '{template}' not found on filesystem",
                is_error=True,
            )
        
        # Create presentations directory if it doesn't exist
        presentations_root = workspace_path / self.presentations_dir
        presentations_root.mkdir(parents=True, exist_ok=True)
        
        # Copy template to presentation directory
        try:
            shutil.copytree(template_dir, presentation_dir)
        except Exception as e:
            return ToolResult(
                llm_content=f"Failed to copy template: {e}",
                user_display_content="Failed to initialize presentation",
                is_error=True,
            )
        
        # Update metadata.json paths
        metadata_file = presentation_dir / "metadata.json"
        slide_count = 0
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                
                # Update presentation name and title
                metadata["presentation_name"] = safe_name
                if "title" not in metadata or not metadata.get("title"):
                    metadata["title"] = presentation_name.replace("_", " ").replace("-", " ").title()
                metadata["updated_at"] = datetime.now().isoformat()
                
                # Update slide paths if they exist
                if "slides" in metadata:
                    slides_dict = metadata["slides"]
                    slide_count = len(slides_dict)
                    for slide_num, slide_info in slides_dict.items():
                        if isinstance(slide_info, dict):
                            filename = slide_info.get("filename", f"slide_{int(slide_num):02d}.html")
                            slide_info["file_path"] = f"{self.presentations_dir}/{safe_name}/{filename}"
                            slide_info["preview_url"] = f"/workspace/{self.presentations_dir}/{safe_name}/{filename}"
                
                metadata_file.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception as e:
                # Non-fatal error - presentation was copied, just metadata update failed
                pass
        
        # Count slides if we didn't get it from metadata
        if slide_count == 0:
            slide_files = list(presentation_dir.glob("slide_*.html"))
            slide_count = len(slide_files)
        
        # Build response
        presentation_metadata = {
            "type": "slide_presentation_metadata",
            "presentation_name": safe_name,
            "template": template,
            "template_description": TEMPLATE_DESCRIPTIONS[template],
            "presentation_directory": str(presentation_dir),
            "slide_count": slide_count,
        }
        
        # Build next steps guidance
        next_steps = (
            f"Next steps:\n"
            f"1. View the slides at {self.presentations_dir}/{safe_name}/slide_XX.html\n"
            f"2. Use SlideEdit to modify content while keeping the design\n"
            f"3. Use SlideWrite to add new slides following the template's style\n"
            f"4. Review metadata.json for slide titles and order"
        )
        
        return ToolResult(
            llm_content=(
                f"Successfully initialized presentation '{safe_name}' from '{template}' template.\n\n"
                f"Location: {presentation_dir}\n"
                f"Template: {template}\n"
                f"Slides: {slide_count} slides ready to customize\n\n"
                f"Template description: {TEMPLATE_DESCRIPTIONS[template]}\n\n"
                f"{next_steps}"
            ),
            user_display_content=[presentation_metadata],
            is_error=False,
        )
    
    async def execute_mcp_wrapper(
        self,
        presentation_name: str,
        template: str,
    ):
        """MCP wrapper for the tool."""
        return await self._mcp_wrapper(
            tool_input={
                "presentation_name": presentation_name,
                "template": template,
            }
        )
