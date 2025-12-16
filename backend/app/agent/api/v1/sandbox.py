from typing import Any, Optional, Union

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
    SandboxInfo,
    ScheduleTimeoutRequest,
    UploadFileFromUrlRequest,
    DownloadToPresignedUrlRequest,
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
        
@router.get("/{sandbox_id}/info", response_model=ResponseModel[SandboxInfo], dependencies=[Depends(DependsJwtAuth)])
async def get_sandbox_info(sandbox_id: str, controller=Depends(get_sandbox_service)):
    """Get detailed information about a sandbox."""
    try:
        info = await controller.get_sandbox_info(sandbox_id)
        if not info:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sandbox {sandbox_id} not found")
        
        # Add success field if missing (though ResponseModel handles wrapper)
        # SandboxInfo model might not have success/message fields, that's fine for the data payload
        return ResponseModel(data=info)
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/schedule-timeout", response_model=ResponseModel[dict], dependencies=[Depends(DependsJwtAuth)])
async def schedule_timeout(request: ScheduleTimeoutRequest, controller=Depends(get_sandbox_service)):
    """Schedule a timeout for a sandbox."""
    try:
        await controller.schedule_timeout(
            sandbox_id=request.sandbox_id, timeout_seconds=request.timeout_seconds
        )
        return ResponseModel(data={"success": True, "message": "Timeout scheduled successfully"})
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/{sandbox_id}/pause", response_model=ResponseModel[dict], dependencies=[Depends(DependsJwtAuth)])
async def pause_sandbox(sandbox_id: str, reason: str = "manual", controller=Depends(get_sandbox_service)):
    """Pause a sandbox."""
    try:
        await controller.pause_sandbox(sandbox_id, reason)
        return ResponseModel(data={"success": True, "message": f"Sandbox paused successfully (reason: {reason})"})
    except Exception as e:
        handle_sandbox_exception(e)

@router.delete("/{sandbox_id}", response_model=ResponseModel[dict], dependencies=[Depends(DependsJwtAuth)])
async def delete_sandbox(sandbox_id: str, controller=Depends(get_sandbox_service)):
    """Delete a sandbox."""
    try:
        await controller.delete_sandbox(sandbox_id)
        return ResponseModel(data={"success": True, "message": "Sandbox deleted successfully"})
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/expose-port", response_model=ResponseModel[ExposePortResponse], dependencies=[Depends(DependsJwtAuth)])
async def expose_port(request: ExposePortRequest, controller=Depends(get_sandbox_service)):
    """Expose a port from a sandbox."""
    try:
        url = await controller.expose_port(request.sandbox_id, request.port)
        return ResponseModel(data=ExposePortResponse(success=True, url=url, message=f"Port {request.port} exposed successfully"))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/write-file", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def write_file(request: FileOperationRequest, controller=Depends(get_sandbox_service)):
    """Write a file to a sandbox."""
    try:
        if not request.content:
            raise HTTPException(status_code=400, detail="Content is required")
        success = await controller.write_file(request.sandbox_id, request.file_path, request.content)
        return ResponseModel(data=FileOperationResponse(success=success, message=f"File written to {request.file_path}"))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/read-file", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def read_file(request: FileOperationRequest, controller=Depends(get_sandbox_service)):
    """Read a file from a sandbox."""
    try:
        content = await controller.read_file(request.sandbox_id, request.file_path)
        return ResponseModel(data=FileOperationResponse(success=True, content=content))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/upload-file", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def upload_file(
    sandbox_id: str = Form(...),
    file_path: str = Form(...),
    file: UploadFile = File(...),
    controller=Depends(get_sandbox_service)
):
    """Upload a file to a sandbox."""
    try:
        content = await file.read()
        success = await controller.write_file(sandbox_id, file_path, content)
        return ResponseModel(data=FileOperationResponse(success=success, message=f"File uploaded to {file_path}"))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/upload-file-from-url", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def upload_file_from_url(request: UploadFileFromUrlRequest, controller=Depends(get_sandbox_service)):
    """Upload file from URL."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.url)
            response.raise_for_status()
            content = response.content
        success = await controller.write_file(request.sandbox_id, request.file_path, content)
        return ResponseModel(data=FileOperationResponse(success=success, message=f"File downloaded from URL and uploaded to {request.file_path}"))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/download-to-presigned-url", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def download_to_presigned_url(request: DownloadToPresignedUrlRequest, controller=Depends(get_sandbox_service)):
    """Download to presigned URL."""
    try:
        content = await controller.download_file(request.sandbox_id, request.sandbox_path, request.format)
        content_type = "application/octet-stream"
        if request.format == "text":
            content_type = "text/plain"
        async with httpx.AsyncClient() as client:
            await client.put(request.presigned_url, content=content, headers={"Content-Type": content_type})
        return ResponseModel(data=FileOperationResponse(success=True, message="File uploaded to presigned URL"))
    except Exception as e:
        handle_sandbox_exception(e)

@router.post("/create-directory", response_model=ResponseModel[FileOperationResponse], dependencies=[Depends(DependsJwtAuth)])
async def create_directory(sandbox_id: str, directory_path: str, exist_ok: bool = False, controller=Depends(get_sandbox_service)):
    """Create directory."""
    try:
        success = await controller.create_directory(sandbox_id, directory_path, exist_ok)
        return ResponseModel(data=FileOperationResponse(success=success, message=f"Directory created at {directory_path}"))
    except Exception as e:
        handle_sandbox_exception(e)
