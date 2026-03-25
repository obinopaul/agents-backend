import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.crud.crud_slide_template import slide_template_dao
from backend.app.agent.model.slide_template import SlideTemplate
from backend.database.db import async_db_session

from backend.core.path_conf import BASE_PATH

logger = logging.getLogger(__name__)

# Path to assets/templates relative to project root
# We use BASE_PATH (backend/) -> parent (project root) -> assets -> templates
DEFAULT_ASSETS_PATH = BASE_PATH.parent / "assets" / "templates"

class TemplateSeeder:
    """Service to seed slide templates from the filesystem."""
    
    def __init__(self, assets_path: Path = DEFAULT_ASSETS_PATH):
        self.assets_path = assets_path
        logger.info(f"TemplateSeeder initialized with assets path: {self.assets_path.absolute()}")
        
    async def seed(self) -> int:
        """
        Scan assets directory and upsert templates.
        Returns number of templates seeded.
        """
        if not self.assets_path.exists():
            logger.warning(f"Template assets path not found: {self.assets_path.absolute()}")
            return 0
            
        count = 0
        async with async_db_session() as db:
            for item in self.assets_path.iterdir():
                if item.is_dir():
                    try:
                        await self._process_template_dir(db, item)
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to seed template {item.name}: {e}")
                        
        logger.info(f"Seeded {count} slide templates successfully.")
        return count
        
    async def _process_template_dir(self, db: AsyncSession, dir_path: Path):
        """Process a single template directory."""
        template_id = dir_path.name
        
        # 1. Try to read metadata.json
        metadata = {}
        meta_file = dir_path / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Error reading metadata for {template_id}: {e}")
                
        # 2. Derive basic info if missing
        name = metadata.get("name", template_id.replace("_", " ").title())
        description = metadata.get("description", f"{name} presentation template")
        colors = metadata.get("colors", [])
        
        # 3. Find images
        # Prioritize 'image.png' or 'thumb.png' for thumbnail
        thumbnail_path = None
        images = []
        
        # List all valid image files
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        all_files = sorted([f for f in dir_path.iterdir() if f.suffix.lower() in valid_exts])
        
        # Strategy:
        # - Check specific names for thumbnail
        # - Collect others as previews
        
        for f in all_files:
            rel_path = f"/assets/templates/{template_id}/{f.name}" # Frontend accessible path
            
            if f.name.lower() in ("image.png", "thumb.png", "thumbnail.png"):
                thumbnail_path = rel_path
            else:
                images.append(rel_path)
                
        # If no explicit thumbnail, use first image
        if not thumbnail_path and images:
            thumbnail_path = images[0]
            
        # 4. Upsert into DB
        existing = await slide_template_dao.get_by_template_id(db, template_id)
        
        if existing:
            # Update
            await slide_template_dao.update(
                db, 
                existing.id,
                name=name,
                description=description,
                thumbnail_path=thumbnail_path,
                assets_path=str(dir_path), # Store relative FS path if needed? Or just rely on convention?
                images=images,
                colors=colors,
                is_active=True # Reactivate if it was there
            )
            logger.info(f"Updated template: {name}")
        else:
            # Create
            await slide_template_dao.create(
                db,
                template_id=template_id,
                name=name,
                description=description,
                thumbnail_path=thumbnail_path,
                assets_path=str(dir_path),
                images=images,
                colors=colors
            )
            logger.info(f"Created template: {name}")

async def seed_templates_on_startup():
    """Wrapper to run seeder."""
    seeder = TemplateSeeder()
    await seeder.seed()
