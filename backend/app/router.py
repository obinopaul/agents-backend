from fastapi import APIRouter

from backend.app.admin.api.router import v1 as admin_v1
from backend.app.agent.api.router import v1 as agent_v1
from backend.app.task.api.router import v1 as task_v1
from backend.src.billing.endpoints import billing_router
from backend.core.conf import settings

router = APIRouter()

router.include_router(admin_v1)
router.include_router(agent_v1)
router.include_router(task_v1)
router.include_router(billing_router, prefix=f"{settings.FASTAPI_API_V1_PATH}/billing", tags=["Billing"])

