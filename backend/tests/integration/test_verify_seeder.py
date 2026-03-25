
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from backend.src.services.template_seeder import TemplateSeeder, DEFAULT_ASSETS_PATH

@pytest.mark.asyncio
async def test_template_seeder_logic():
    """
    Verifies that the TemplateSeeder:
    1. Finds the assets directory.
    2. Iterates over subdirectories (slide templates).
    3. correctly parses files to identify thumbnails and images.
    """
    
    # 1. Verify assets path exists
    assert DEFAULT_ASSETS_PATH.exists(), f"Assets path not found at {DEFAULT_ASSETS_PATH}"
    
    # 2. Mock DB interactions to avoid actual DB writes
    with patch("backend.src.services.template_seeder.async_db_session") as mock_session_ctx:
        mock_db = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_db
        
        with patch("backend.src.services.template_seeder.slide_template_dao") as mock_dao:
            # Mock get_by_template_id to return None (simulate new templates)
            mock_dao.get_by_template_id.return_value = None
            
            seeder = TemplateSeeder()
            
            # Run the seed
            count = await seeder.seed()
            
            # 3. Assertions
            # We expect at least one template (e.g. 'architect') from previous tools
            assert count > 0, "Seeder found 0 templates, expected > 0"
            
            # Verify dao.create was called
            assert mock_dao.create.called, "DAO create was not called"
            
            # Inspect one call to verify data structure
            # call_args is (args, kwargs)
            # kwargs should contain 'template_id', 'images', 'thumbnail_path'
            call_args = mock_dao.create.call_args[1]
            assert "template_id" in call_args
            assert "images" in call_args
            assert "thumbnail_path" in call_args
            
            print(f"Successfully simulated seeding of {count} templates.")
