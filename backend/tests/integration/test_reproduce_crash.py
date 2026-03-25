
import pytest
from fastapi import FastAPI
from backend.app.agent.api.v1.templates import slide_router

def test_templates_router_startup():
    """
    Verifies that the templates router can be included in a FastAPI app
    without raising dependency injection errors (e.g. AssertionError).
    """
    app = FastAPI()
    try:
        app.include_router(slide_router, prefix="/api/v1/templates")
        # Trigger OpenAPI schema generation to validate dependencies
        _ = app.openapi()
    except Exception as e:
        pytest.fail(f"Failed to include slide_router or generate OpenAPI: {e}")
