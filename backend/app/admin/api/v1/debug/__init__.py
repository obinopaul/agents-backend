from fastapi import APIRouter

from backend.app.admin.api.v1.debug.scripts import router as scripts_router

router = APIRouter(prefix='/debug')
router.include_router(scripts_router)

__all__ = ['router']
