from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response

from backend.common.response.response_schema import ResponseModel
from backend.core.security.jwt import DependsJwtAuth
from backend.src.services.sandbox_service import sandbox_service
from backend.src.sandbox_server.models import (
    CreateSandboxRequest,
    CreateSandboxResponse,
    ConnectSandboxRequest,
    ConnectSandboxResponse,
    RunCommandRequest,
    RunCommandResponse,
    FileOperationRequest,
    FileOperationResponse,
    ExposePortRequest,
    ExposePortResponse,
    SandboxStatusResponse,
    SandboxInfo
)
from backend.src.sandbox_server.models.exceptions import (
    SandboxAuthenticationError,
    SandboxNotFoundException,
    SandboxTimeoutException,
    SandboxNotInitializedError,
)
import httpx

router = APIRouter(prefix="/sandboxes", tags=["Sandbox"])

def handle_sandbox_exception(e: Exception):
    """Handle sandbox exceptions and return appropriate HTTP status code."""
    if isinstance(e, SandboxAuthenticationError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    elif isinstance(e, SandboxNotFoundException) or isinstance(e, FileNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    elif isinstance(e, SandboxTimeoutException):
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    elif isinstance(e, SandboxNotInitializedError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    else:
        # Generic server error for other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

async def get_sandbox_service():
    if not sandbox_service._controller:
        await sandbox_service.initialize()
    return sandbox_service.controller

@router.post("/create", response_model=ResponseModel[CreateSandboxResponse], dependencies=[Depends(DependsJwtAuth)])
async def create_sandbox(request: CreateSandboxRequest, controller = Depends(get_sandbox_service)):
    """Create a new sandbox."""
    try:
        sandbox = await controller.create_sandbox(
            user_id=request.user_id,
            sandbox_template_id=request.sandbox_template_id,
        )
        return ResponseModel(
            data=CreateSandboxResponse(
                success=True,
                sandbox_id=sandbox.sandbox_id,
                provider_sandbox_id=sandbox.provider_sandbox_id,
                status="running",
                message="Sandbox created successfully",
            )
        )
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/connect", response_model=ResponseModel[ConnectSandboxResponse], dependencies=[Depends(DependsJwtAuth)])
async def connect_sandbox(request: ConnectSandboxRequest, controller = Depends(get_sandbox_service)):
    """Connect to or resume a sandbox."""
    try:
        sandbox = await controller.connect(sandbox_id=request.sandbox_id)
        status_val = await controller.get_sandbox_status(request.sandbox_id)
        return ResponseModel(
            data=ConnectSandboxResponse(
                success=True,
                sandbox_id=sandbox.sandbox_id,
                provider_sandbox_id=sandbox.provider_sandbox_id,
                status=status_val,
                message="Successfully connected to sandbox",
            )
        )
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/run-cmd", response_model=ResponseModel[RunCommandResponse], dependencies=[Depends(DependsJwtAuth)])
async def run_cmd(request: RunCommandRequest, controller = Depends(get_sandbox_service)):
    """Run a command in a sandbox."""
    try:
        output = await controller.run_cmd(
            request.sandbox_id, request.command, request.background
        )
        return ResponseModel(
            data=RunCommandResponse(
                success=True,
                output=output,
                message="Command executed successfully"
            )
        )
    except Exception as e:
        handle_sandbox_exception(e)

@router.get("/{sandbox_id}/status", response_model=ResponseModel[SandboxStatusResponse], dependencies=[Depends(DependsJwtAuth)])
async def get_sandbox_status(sandbox_id: str, controller = Depends(get_sandbox_service)):
    """Get the status of a sandbox."""
    try:
        sandbox_status = await controller.get_sandbox_status(sandbox_id)
        info = await controller.get_sandbox_info(sandbox_id)

        return ResponseModel(
            data=SandboxStatusResponse(
                success=True,
                sandbox_id=sandbox_id,
                status=sandbox_status,
                provider_sandbox_id=info.provider_sandbox_id if info else None,
                message="Status retrieved successfully",
            )
        )
    except Exception as e:
        handle_sandbox_exception(e)
