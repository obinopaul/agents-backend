
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from backend.src.services.template_seeder import TemplateSeeder, DEFAULT_ASSETS_PATH

async def run_test():
    print(f"Checking assets path: {DEFAULT_ASSETS_PATH}")
    if not DEFAULT_ASSETS_PATH.exists():
        print("ERROR: Assets path does not exist!")
        return

    print("Assets path exists. Mocking DB...")
    
    with patch("backend.src.services.template_seeder.async_db_session") as mock_session_ctx:
        mock_db = AsyncMock()
        # Mock the context manager protocol
        mock_session_ctx.return_value.__aenter__.return_value = mock_db
        
        with patch("backend.src.services.template_seeder.slide_template_dao") as mock_dao:
            # Mock DAO methods
            mock_dao.get_by_template_id = AsyncMock(return_value=None)
            mock_dao.create = AsyncMock()
            mock_dao.update = AsyncMock()
            
            print("Initializing Seeder...")
            seeder = TemplateSeeder()
            
            print("Running seed()...")
            try:
                count = await seeder.seed()
                print(f"Seed complete. Count: {count}")
                
                if count == 0:
                    print("ERROR: Count is 0")
                else:
                    print("SUCCESS: Seeded successfully")
                    print(f"Create called: {mock_dao.create.called}")
                    if mock_dao.create.called:
                        print(f"First call args: {mock_dao.create.call_args}")

            except Exception as e:
                print(f"EXCEPTION during seed: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except Exception as e:
        print(f"Root Exception: {e}")
        import traceback
        traceback.print_exc()
