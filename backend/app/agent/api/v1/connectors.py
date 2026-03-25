# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Connectors API endpoints for external service integrations.

Provides full OAuth integration for external services like Google Drive:
- OAuth flow initialization and callback handling
- Token management with automatic refresh
- File picker configuration
- File download with folder support
- Connection status and disconnection

Requires environment variables:
- OAUTH2_GOOGLE_CLIENT_ID: Google OAuth client ID
- OAUTH2_GOOGLE_CLIENT_SECRET: Google OAuth client secret
- OAUTH2_GOOGLE_REDIRECT_URI: OAuth callback URL
- TOKEN_SECRET_KEY: Secret for state serialization
"""

import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import select
from itsdangerous import URLSafeSerializer

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.core.conf import settings
from backend.app.agent.model.connector import Connector, ConnectorType


logger = logging.getLogger(__name__)

router = APIRouter(prefix='/connectors', tags=['Connectors'])


# =============================================================================
# Google Drive OAuth Scopes
# =============================================================================

GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


# =============================================================================
# Helper Functions
# =============================================================================

def _normalize_expiry(expiry: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime values include timezone info for comparisons."""
    if expiry is None:
        return None
    if expiry.tzinfo is None:
        return expiry.replace(tzinfo=timezone.utc)
    return expiry


def _is_google_drive_configured() -> bool:
    """Check if Google Drive integration is properly configured."""
    return bool(
        settings.OAUTH2_GOOGLE_CLIENT_ID and
        settings.OAUTH2_GOOGLE_CLIENT_SECRET
    )


def _get_google_redirect_uri() -> str:
    """Get the Google Drive OAuth redirect URI.

    Uses OAUTH2_GOOGLE_DRIVE_REDIRECT_URI for the Google Drive connector OAuth flow.
    This is separate from OAUTH2_GOOGLE_REDIRECT_URI used for login, because:
    1. Different scopes (drive.file vs just profile/email)
    2. Different callback handling (frontend captures and posts vs backend redirect)
    """
    # Prefer the Google Drive specific setting, fall back to general Google OAuth setting
    if hasattr(settings, 'OAUTH2_GOOGLE_DRIVE_REDIRECT_URI') and settings.OAUTH2_GOOGLE_DRIVE_REDIRECT_URI:
        return settings.OAUTH2_GOOGLE_DRIVE_REDIRECT_URI
    return settings.OAUTH2_GOOGLE_REDIRECT_URI or 'http://localhost:1420/google-drive-callback'


# =============================================================================
# Response Schemas
# =============================================================================

class ConnectorStatusResponse(BaseModel):
    """Connector status response."""
    is_connected: bool = False
    connector_type: str
    metadata: Optional[dict] = None
    access_token: Optional[str] = None


class ConnectorAuthUrlResponse(BaseModel):
    """OAuth auth URL response."""
    auth_url: str
    state: str


class GoogleDrivePickerConfigResponse(BaseModel):
    """Google Drive picker configuration."""
    is_connected: bool = False
    access_token: Optional[str] = None
    developer_key: Optional[str] = None
    app_id: Optional[str] = None


class GoogleDriveFileInfo(BaseModel):
    """Information about a downloaded file."""
    id: str
    name: str
    size: int
    mime_type: Optional[str] = None
    file_url: Optional[str] = None
    is_folder: bool = False
    file_ids: Optional[List[str]] = None
    file_count: Optional[int] = None


class GoogleDriveFilesResponse(BaseModel):
    """Google Drive files download response."""
    success: bool = False
    files: List[GoogleDriveFileInfo] = []


class CallbackRequest(BaseModel):
    """OAuth callback request."""
    code: str
    state: str


class FileDownloadRequest(BaseModel):
    """File download request."""
    file_ids: List[str]


# =============================================================================
# Google Drive Connector Endpoints
# =============================================================================

@router.get(
    '/google-drive/status',
    summary='Get Google Drive connection status',
    response_model=ConnectorStatusResponse,
    dependencies=[DependsJwtAuth]
)
async def get_google_drive_status(
    request: Request,
    db: CurrentSession,
):
    """
    Check if user has connected Google Drive.

    If connected and token is expired, attempts automatic refresh.
    Returns connection status, metadata (email, name), and access token.
    """
    if not _is_google_drive_configured():
        return ConnectorStatusResponse(
            is_connected=False,
            connector_type=ConnectorType.GOOGLE_DRIVE.value,
            metadata=None,
            access_token=None
        )

    user_id = request.user.id

    result = await db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.connector_type == ConnectorType.GOOGLE_DRIVE.value,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        return ConnectorStatusResponse(
            is_connected=False,
            connector_type=ConnectorType.GOOGLE_DRIVE.value,
        )

    # Try to refresh token if expired
    if connector.is_expired and connector.can_refresh:
        try:
            await _refresh_google_token(connector, db)
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")

    return ConnectorStatusResponse(
        is_connected=True,
        connector_type=ConnectorType.GOOGLE_DRIVE.value,
        metadata=connector.connector_metadata,
        access_token=connector.access_token,
    )


@router.get(
    '/google-drive/auth-url',
    summary='Get Google Drive OAuth URL',
    response_model=ConnectorAuthUrlResponse,
    dependencies=[DependsJwtAuth]
)
async def get_google_drive_auth_url(
    request: Request,
    frontend_url: Optional[str] = Query(None, description="Frontend URL for redirect after OAuth")
):
    """
    Generate Google Drive OAuth authorization URL.

    The state parameter includes user_id and optional frontend_url for
    secure callback verification and proper redirect after authentication.
    """
    if not _is_google_drive_configured():
        raise HTTPException(
            status_code=501,
            detail="Google Drive integration is not configured. Please set OAUTH2_GOOGLE_CLIENT_ID and OAUTH2_GOOGLE_CLIENT_SECRET."
        )

    user_id = request.user.id

    # Import Google OAuth library
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth library not installed. Install with: pip install google-auth-oauthlib google-api-python-client"
        )

    # Create state with user_id for verification
    serializer = URLSafeSerializer(settings.TOKEN_SECRET_KEY)
    state_data = {
        "user_id": user_id,
        "connector": "google_drive"
    }
    if frontend_url:
        state_data["frontend_url"] = frontend_url
    state = serializer.dumps(state_data)

    # Create OAuth flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.OAUTH2_GOOGLE_CLIENT_ID,
                "client_secret": settings.OAUTH2_GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [_get_google_redirect_uri()],
            }
        },
        scopes=GOOGLE_DRIVE_SCOPES,
        redirect_uri=_get_google_redirect_uri(),
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",  # Force consent to always get refresh_token
    )

    return ConnectorAuthUrlResponse(auth_url=authorization_url, state=state)


@router.post(
    '/google-drive/callback',
    summary='Handle Google Drive OAuth callback',
    dependencies=[DependsJwtAuth]
)
async def handle_google_drive_callback(
    request: Request,
    callback_data: CallbackRequest,
    db: CurrentSession,
):
    """
    Handle the OAuth callback from Google Drive.

    Verifies state, exchanges authorization code for tokens,
    fetches user info, and stores credentials in the database.
    """
    if not _is_google_drive_configured():
        raise HTTPException(
            status_code=501,
            detail="Google Drive integration is not configured."
        )

    user_id = request.user.id

    # Verify state
    serializer = URLSafeSerializer(settings.TOKEN_SECRET_KEY)
    try:
        state_data = serializer.loads(callback_data.state)
        if state_data.get("user_id") != user_id:
            raise HTTPException(status_code=400, detail="Invalid state parameter - user mismatch")
    except Exception as e:
        logger.error(f"State verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Import Google OAuth library
    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth library not installed."
        )

    # Exchange code for tokens
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.OAUTH2_GOOGLE_CLIENT_ID,
                "client_secret": settings.OAUTH2_GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [_get_google_redirect_uri()],
            }
        },
        scopes=GOOGLE_DRIVE_SCOPES,
        redirect_uri=_get_google_redirect_uri(),
    )

    try:
        flow.fetch_token(code=callback_data.code)
        credentials = flow.credentials

        # Get user info
        user_info_service = build("oauth2", "v2", credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()

        token_expiry = _normalize_expiry(credentials.expiry)

        # Check for existing connector
        result = await db.execute(
            select(Connector).where(
                Connector.user_id == user_id,
                Connector.connector_type == ConnectorType.GOOGLE_DRIVE.value,
            )
        )
        existing_connector = result.scalar_one_or_none()

        metadata = {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "scopes": GOOGLE_DRIVE_SCOPES,
        }

        if existing_connector:
            # Update existing connector
            existing_connector.access_token = credentials.token
            existing_connector.refresh_token = credentials.refresh_token or existing_connector.refresh_token
            existing_connector.token_expiry = token_expiry
            existing_connector.connector_metadata = metadata
        else:
            # Create new connector
            new_connector = Connector(
                user_id=user_id,
                connector_type=ConnectorType.GOOGLE_DRIVE.value,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=token_expiry,
                connector_metadata=metadata,
            )
            db.add(new_connector)

        await db.commit()

        logger.info(f"Google Drive connected successfully for user {user_id}")
        return {"success": True, "message": "Google Drive connected successfully"}

    except Exception as e:
        logger.error(f"Google Drive OAuth callback failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect Google Drive: {str(e)}",
        )


@router.get(
    '/google-drive/picker-config',
    summary='Get Google Drive picker configuration',
    response_model=GoogleDrivePickerConfigResponse,
    dependencies=[DependsJwtAuth]
)
async def get_google_drive_picker_config(
    request: Request,
    db: CurrentSession,
):
    """
    Return configuration required to launch the Google Drive picker.

    Automatically refreshes the access token to ensure it's valid for the picker.
    Returns developer key and app ID if configured.
    """
    user_id = request.user.id

    # Get developer key from environment (optional, but recommended for picker)
    developer_key = getattr(settings, 'GOOGLE_PICKER_DEVELOPER_KEY', None)
    app_id = settings.OAUTH2_GOOGLE_CLIENT_ID.split('-')[0] if settings.OAUTH2_GOOGLE_CLIENT_ID else None

    if not _is_google_drive_configured():
        return GoogleDrivePickerConfigResponse(
            is_connected=False,
            developer_key=developer_key,
            app_id=app_id,
        )

    result = await db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.connector_type == ConnectorType.GOOGLE_DRIVE.value,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        return GoogleDrivePickerConfigResponse(
            is_connected=False,
            developer_key=developer_key,
            app_id=app_id,
        )

    # Always refresh token to ensure it's valid for the picker
    if connector.refresh_token:
        try:
            await _refresh_google_token(connector, db)
        except Exception as e:
            logger.error(f"Failed to refresh token for picker: {e}")

    return GoogleDrivePickerConfigResponse(
        is_connected=True,
        access_token=connector.access_token,
        developer_key=developer_key,
        app_id=app_id,
    )


@router.post(
    '/google-drive/files',
    summary='Download files from Google Drive',
    response_model=GoogleDriveFilesResponse,
    dependencies=[DependsJwtAuth]
)
async def download_google_drive_files(
    request: Request,
    file_request: FileDownloadRequest,
    db: CurrentSession,
):
    """
    Download selected files from Google Drive.

    Supports both individual files and folders (with recursive download).
    Files are stored locally and file metadata is returned.
    """
    if not _is_google_drive_configured():
        raise HTTPException(
            status_code=501,
            detail="Google Drive integration is not configured."
        )

    user_id = request.user.id

    result = await db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.connector_type == ConnectorType.GOOGLE_DRIVE.value,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=400,
            detail="Google Drive is not connected. Please connect first.",
        )

    # Import required libraries
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Google API library not installed."
        )

    # Refresh token if needed
    await _refresh_google_token(connector, db)

    # Create credentials
    credentials = Credentials(
        token=connector.access_token,
        refresh_token=connector.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.OAUTH2_GOOGLE_CLIENT_ID,
        client_secret=settings.OAUTH2_GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_DRIVE_SCOPES,
        expiry=_normalize_expiry(connector.token_expiry),
    )

    try:
        service = build("drive", "v3", credentials=credentials)
        downloaded_files = []

        def list_files_in_folder(folder_id: str) -> list:
            """Recursively list all files in a folder."""
            file_ids = []
            page_token = None

            while True:
                try:
                    results = service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        fields="nextPageToken, files(id, name, mimeType)",
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute()

                    items = results.get("files", [])
                    for item in items:
                        if item.get("mimeType") == "application/vnd.google-apps.folder":
                            # Recursively get files from subfolders
                            file_ids.extend(list_files_in_folder(item["id"]))
                        else:
                            file_ids.append(item["id"])

                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break

                except Exception as e:
                    logger.error(f"Failed to list files in folder {folder_id}: {e}")
                    break

            return file_ids

        # Process each selected item (file or folder)
        folder_file_mapping = {}

        for file_id in file_request.file_ids:
            try:
                logger.info(f"Getting metadata for file ID: {file_id}")
                file_metadata = (
                    service.files()
                    .get(fileId=file_id, fields="id,name,mimeType,size", supportsAllDrives=True)
                    .execute()
                )
                logger.info(f"File metadata: {file_metadata}")

                is_folder = file_metadata.get("mimeType") == "application/vnd.google-apps.folder"

                if is_folder:
                    logger.info(f"Listing files in folder: {file_metadata.get('name')}")
                    folder_file_ids = list_files_in_folder(file_id)
                    logger.info(f"Found {len(folder_file_ids)} files in folder")

                    folder_file_mapping[file_id] = {
                        "folder_name": file_metadata["name"],
                        "folder_id": file_id,
                        "file_ids": folder_file_ids,
                        "file_uploads": []
                    }
                else:
                    folder_file_mapping[file_id] = {
                        "folder_name": None,
                        "folder_id": None,
                        "file_ids": [file_id],
                        "file_uploads": []
                    }

            except Exception as e:
                logger.error(f"Failed to get metadata for file {file_id}: {e}")
                continue

        # Download files and track results
        import os
        from pathlib import Path

        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.FILE_STORAGE_LOCAL_PATH) / "google-drive" / str(user_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        for original_id, folder_info in folder_file_mapping.items():
            for file_id in folder_info["file_ids"]:
                try:
                    file_metadata = (
                        service.files()
                        .get(fileId=file_id, fields="id,name,mimeType,size", supportsAllDrives=True)
                        .execute()
                    )

                    # Skip Google Docs types that need export
                    mime_type = file_metadata.get("mimeType", "")
                    if mime_type.startswith("application/vnd.google-apps."):
                        logger.info(f"Skipping Google Apps file: {file_metadata['name']}")
                        continue

                    request_obj = service.files().get_media(fileId=file_id, supportsAllDrives=True)

                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request_obj)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()

                    # Save file locally
                    file_path = upload_dir / file_id / file_metadata['name']
                    file_path.parent.mkdir(parents=True, exist_ok=True)

                    fh.seek(0)
                    with open(file_path, 'wb') as f:
                        f.write(fh.read())

                    folder_info["file_uploads"].append({
                        "id": file_id,
                        "name": file_metadata["name"],
                        "size": int(file_metadata.get("size", 0)),
                        "mime_type": file_metadata.get("mimeType"),
                        "path": str(file_path),
                    })

                except Exception as e:
                    logger.error(f"Failed to download file {file_id}: {e}")
                    continue

        # Build response
        for original_id, folder_info in folder_file_mapping.items():
            if not folder_info["file_uploads"]:
                continue

            if folder_info["folder_name"]:
                # This is a folder
                downloaded_files.append(GoogleDriveFileInfo(
                    id=",".join(f["id"] for f in folder_info["file_uploads"]),
                    name=folder_info["folder_name"],
                    size=sum(f["size"] for f in folder_info["file_uploads"]),
                    mime_type="application/vnd.google-apps.folder",
                    is_folder=True,
                    file_ids=[f["id"] for f in folder_info["file_uploads"]],
                    file_count=len(folder_info["file_uploads"])
                ))
            else:
                # This is an individual file
                file_info = folder_info["file_uploads"][0]
                downloaded_files.append(GoogleDriveFileInfo(
                    id=file_info["id"],
                    name=file_info["name"],
                    size=file_info["size"],
                    mime_type=file_info["mime_type"],
                    file_url=file_info["path"],
                    is_folder=False,
                ))

        return GoogleDriveFilesResponse(success=True, files=downloaded_files)

    except Exception as e:
        logger.error(f"Failed to download files from Google Drive: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download files: {str(e)}",
        )


@router.delete(
    '/google-drive',
    summary='Disconnect Google Drive',
    dependencies=[DependsJwtAuth]
)
async def disconnect_google_drive(
    request: Request,
    db: CurrentSession,
):
    """
    Disconnect Google Drive and revoke access token.

    Attempts to revoke the token with Google before removing from database.
    """
    user_id = request.user.id

    result = await db.execute(
        select(Connector).where(
            Connector.user_id == user_id,
            Connector.connector_type == ConnectorType.GOOGLE_DRIVE.value,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        return {"success": True, "message": "Google Drive is not connected"}

    # Revoke the access token with Google
    if connector.access_token:
        try:
            import requests as http_requests

            revoke_response = http_requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": connector.access_token},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            if revoke_response.status_code == 200:
                logger.info(f"Successfully revoked Google Drive token for user {user_id}")
            else:
                logger.warning(
                    f"Failed to revoke Google Drive token for user {user_id}: "
                    f"status={revoke_response.status_code}"
                )
        except Exception as e:
            logger.error(f"Error revoking Google Drive token for user {user_id}: {e}")

    await db.delete(connector)
    await db.commit()

    logger.info(f"Google Drive disconnected for user {user_id}")
    return {"success": True, "message": "Google Drive disconnected successfully"}


# =============================================================================
# Internal Helper Functions
# =============================================================================

async def _refresh_google_token(connector: Connector, db: CurrentSession) -> None:
    """
    Refresh the Google OAuth token.

    Updates the connector with the new access token and expiry.
    """
    if not connector.refresh_token:
        return

    try:
        import requests as http_requests
        from google.auth import _helpers

        token_response = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.OAUTH2_GOOGLE_CLIENT_ID,
                "client_secret": settings.OAUTH2_GOOGLE_CLIENT_SECRET,
                "refresh_token": connector.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_data = token_response.json()

        if "access_token" in token_data:
            new_expiry = _helpers.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 3600)
            )

            connector.access_token = token_data["access_token"]
            connector.token_expiry = new_expiry
            await db.commit()

            logger.info(f"Refreshed Google token for user {connector.user_id}")
        else:
            error = token_data.get("error", "Unknown error")
            logger.error(f"Token refresh failed: {error}")

    except Exception as e:
        logger.error(f"Failed to refresh Google token: {e}")
        raise
