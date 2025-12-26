# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Generation API endpoints.

This module provides endpoints for AI-powered content generation:
- Podcast generation from reports
- Presentation (PPT) generation
- Prose writing assistance
- Prompt enhancement
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth
from backend.src.config.report_style import ReportStyle
from backend.src.module.podcast.graph.builder import build_graph as build_podcast_graph
from backend.src.module.ppt.graph.builder import build_graph as build_ppt_graph
from backend.src.module.prompt_enhancer.graph.builder import build_graph as build_prompt_enhancer_graph
from backend.src.module.prose.graph.builder import build_graph as build_prose_graph

logger = logging.getLogger(__name__)

router = APIRouter()

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"


class GeneratePodcastRequest(BaseModel):
    """Request model for podcast generation."""

    content: str = Field(..., description="The report content to convert to podcast")


class GeneratePPTRequest(BaseModel):
    """Request model for presentation generation."""

    content: str = Field(..., description="The report content to convert to presentation")
    locale: str = Field(default="en-US", description="Language locale for the presentation")


class GenerateProseRequest(BaseModel):
    """Request model for prose generation."""

    prompt: str = Field(..., description="The text prompt to process")
    option: str = Field(
        ...,
        description="Processing option: 'continue', 'improve', 'fix', 'shorter', 'longer', 'zap'"
    )
    command: str = Field(default="", description="Optional command for custom instructions")


class EnhancePromptRequest(BaseModel):
    """Request model for prompt enhancement."""

    prompt: str = Field(..., description="The prompt to enhance")
    context: str = Field(default="", description="Additional context for enhancement")
    report_style: str = Field(
        default="ACADEMIC",
        description="Report style: ACADEMIC, POPULAR_SCIENCE, NEWS, SOCIAL_MEDIA, STRATEGIC_INVESTMENT"
    )


class EnhancePromptResponse(BaseModel):
    """Response model for prompt enhancement."""

    result: str = Field(..., description="The enhanced prompt")


@router.post(
    '/podcast/generate',
    summary="Generate podcast from report",
    description="Convert a text report into an AI-generated podcast audio file.",
    response_class=Response,
    responses={
        200: {
            "description": "MP3 audio file",
            "content": {"audio/mp3": {}},
        },
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def generate_podcast(request: GeneratePodcastRequest):
    """
    Generate a podcast from report content.

    This endpoint uses AI to:
    1. Analyze the report content
    2. Generate a conversational script
    3. Synthesize audio using TTS
    4. Mix the audio into a final podcast

    Returns an MP3 audio file.
    """
    try:
        report_content = request.content
        logger.info(f"Generating podcast from content of length {len(report_content)}")

        workflow = build_podcast_graph()
        final_state = workflow.invoke({"input": report_content})
        audio_bytes = final_state["output"]

        return Response(
            content=audio_bytes,
            media_type="audio/mp3",
            headers={
                "Content-Disposition": "attachment; filename=podcast.mp3",
            },
        )
    except Exception as e:
        logger.exception(f"Error occurred during podcast generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@router.post(
    '/ppt/generate',
    summary="Generate presentation from report",
    description="Convert a text report into a PowerPoint presentation.",
    response_class=Response,
    responses={
        200: {
            "description": "PowerPoint file",
            "content": {"application/vnd.openxmlformats-officedocument.presentationml.presentation": {}},
        },
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def generate_ppt(request: GeneratePPTRequest):
    """
    Generate a presentation from report content.

    This endpoint uses AI to:
    1. Analyze and structure the report content
    2. Generate slide layouts and content
    3. Create a PowerPoint file

    Returns a PPTX file.
    """
    try:
        report_content = request.content
        logger.info(f"Generating PPT from content of length {len(report_content)}")

        workflow = build_ppt_graph()
        final_state = workflow.invoke({
            "input": report_content,
            "locale": request.locale,
        })
        generated_file_path = final_state["generated_file_path"]

        with open(generated_file_path, "rb") as f:
            ppt_bytes = f.read()

        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": "attachment; filename=presentation.pptx",
            },
        )
    except Exception as e:
        logger.exception(f"Error occurred during ppt generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@router.post(
    '/prose/generate',
    summary="Generate prose content",
    description="Process text with AI for continuation, improvement, or other transformations.",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming SSE response with generated prose",
            "content": {"text/event-stream": {}},
        },
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def generate_prose(request: GenerateProseRequest):
    """
    Generate or transform prose content.

    Available options:
    - continue: Continue writing from the given text
    - improve: Improve the writing quality
    - fix: Fix grammar and spelling errors
    - shorter: Make the text more concise
    - longer: Expand the text with more detail
    - zap: Rewrite the text entirely

    Returns a streaming response with generated content.
    """
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Generating prose for prompt: {sanitized_prompt[:100]}...")

        workflow = build_prose_graph()
        events = workflow.astream(
            {
                "content": request.prompt,
                "option": request.option,
                "command": request.command,
            },
            stream_mode="messages",
            subgraphs=True,
        )

        async def generate():
            async for _, event in events:
                yield f"data: {event[0].content}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        logger.exception(f"Error occurred during prose generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@router.post(
    '/prompt/enhance',
    summary="Enhance a prompt",
    description="Use AI to improve and enhance a user prompt for better results.",
    response_model=EnhancePromptResponse,
    responses={
        200: {"description": "Enhanced prompt response"},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    dependencies=[DependsJwtAuth],
)
async def enhance_prompt(request: EnhancePromptRequest):
    """
    Enhance a prompt using AI.

    This endpoint analyzes the input prompt and generates an improved version
    that is more detailed, specific, and likely to produce better results.

    The report_style parameter influences the enhancement approach.
    """
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Enhancing prompt: {sanitized_prompt[:100]}...")

        # Convert string report_style to ReportStyle enum
        style_mapping = {
            "ACADEMIC": ReportStyle.ACADEMIC,
            "POPULAR_SCIENCE": ReportStyle.POPULAR_SCIENCE,
            "NEWS": ReportStyle.NEWS,
            "SOCIAL_MEDIA": ReportStyle.SOCIAL_MEDIA,
            "STRATEGIC_INVESTMENT": ReportStyle.STRATEGIC_INVESTMENT,
        }
        report_style = style_mapping.get(
            request.report_style.upper(), ReportStyle.ACADEMIC
        )

        workflow = build_prompt_enhancer_graph()
        final_state = workflow.invoke({
            "prompt": request.prompt,
            "context": request.context,
            "report_style": report_style,
        })

        return EnhancePromptResponse(result=final_state["output"])
    except Exception as e:
        logger.exception(f"Error occurred during prompt enhancement: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)
