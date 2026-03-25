# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Text-to-Speech (TTS) API endpoints.

This module provides TTS synthesis using the Volcengine TTS service.
"""

import base64
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.src.tools import VolcengineTTS

logger = logging.getLogger(__name__)

router = APIRouter()


class TTSRequest(BaseModel):
    """Request model for text-to-speech synthesis."""

    text: str = Field(..., max_length=1024, description="Text to synthesize (max 1024 characters)")
    encoding: str = Field(default="mp3", description="Audio encoding format: 'mp3' or 'wav'")
    speed_ratio: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed ratio")
    volume_ratio: float = Field(default=1.0, ge=0.5, le=2.0, description="Volume ratio")
    pitch_ratio: float = Field(default=1.0, ge=0.5, le=2.0, description="Pitch ratio")
    text_type: str = Field(default="plain", description="Text type: 'plain' or 'ssml'")
    with_frontend: int = Field(default=1, description="Use frontend processing: 0 or 1")
    frontend_type: str = Field(default="unitTson", description="Frontend processing type")


@router.post(
    '/tts',
    summary="Convert text to speech",
    description="Synthesize text into speech audio using Volcengine TTS service.",
    response_class=Response,
    responses={
        200: {
            "description": "Audio file in requested encoding",
            "content": {
                "audio/mp3": {},
                "audio/wav": {},
            },
        },
        400: {"description": "Bad request - missing TTS configuration"},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech audio.

    This endpoint uses the Volcengine TTS service to synthesize speech from text.
    Requires VOLCENGINE_TTS_APPID and VOLCENGINE_TTS_ACCESS_TOKEN to be configured.

    Returns an audio file in the requested encoding format.
    """
    # Validate TTS configuration
    app_id = settings.VOLCENGINE_TTS_APPID
    if not app_id:
        raise HTTPException(
            status_code=400,
            detail="VOLCENGINE_TTS_APPID is not configured. Please set it in the environment.",
        )

    access_token = settings.VOLCENGINE_TTS_ACCESS_TOKEN
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="VOLCENGINE_TTS_ACCESS_TOKEN is not configured. Please set it in the environment.",
        )

    try:
        cluster = settings.VOLCENGINE_TTS_CLUSTER
        voice_type = settings.VOLCENGINE_TTS_VOICE_TYPE

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )

        # Call the TTS API (text is already limited to 1024 chars by pydantic)
        result = tts_client.text_to_speech(
            text=request.text,
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={
                "Content-Disposition": f"attachment; filename=tts_output.{request.encoding}",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
