
import pytest
from unittest.mock import patch, MagicMock
from typing import AsyncGenerator

@pytest.fixture(scope="session", autouse=True)
def mock_plugin_parsing():
    """Mock plugin parsing to avoid Redis connection during app registration."""
    with patch("backend.plugin.tools.parse_plugin_config", return_value=([], [])):
        yield

@pytest.fixture(scope="session", autouse=True)
def mock_heavy_services():
    """Mock heavy services initialization."""
    with patch("backend.src.services.sandbox_service.sandbox_service.initialize", new_callable=MagicMock) as mock_sandbox_init, \
         patch("backend.src.graph.checkpointer.checkpointer_manager.initialize", new_callable=MagicMock) as mock_checkpoint_init, \
         patch("backend.src.services.sandbox_service.sandbox_service.shutdown", new_callable=MagicMock), \
         patch("backend.src.graph.checkpointer.checkpointer_manager.shutdown", new_callable=MagicMock):
        
        # Make them async mocks
        async def async_noop(): pass
        mock_sandbox_init.side_effect = async_noop
        mock_checkpoint_init.side_effect = async_noop
        
        yield

@pytest.fixture(scope="session")
def app(mock_plugin_parsing, mock_heavy_services):
    """
    Create FastAPI app instance for testing.
    This runs after the plugin mocking is active.
    """
    from backend.core.registrar import register_app
    return register_app()

@pytest.fixture
async def client(app) -> AsyncGenerator:
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
