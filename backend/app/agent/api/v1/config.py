# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent Config API endpoints.

This module provides endpoints for agent system configuration and LLM model information.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.src.llms.llm import get_configured_llm_models

logger = logging.getLogger(__name__)

router = APIRouter()


class RAGConfigInfo(BaseModel):
    """RAG configuration information."""

    provider: str = Field(..., description="Active RAG provider")


class LLMModelInfo(BaseModel):
    """LLM model information."""

    name: str = Field(..., description="Model name")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    model_id: str = Field(..., description="Model identifier")
    is_default: bool = Field(default=False, description="Whether this is the default model")


class AgentConfigResponse(BaseModel):
    """Response model for agent configuration."""

    rag: RAGConfigInfo = Field(..., description="RAG configuration")
    models: List[LLMModelInfo] = Field(default_factory=list, description="Available LLM models")
    recursion_limit: int = Field(..., description="Agent recursion limit")
    mcp_enabled: bool = Field(..., description="Whether MCP is enabled")
    deep_thinking_enabled: bool = Field(..., description="Whether deep thinking is enabled")
    clarification_enabled: bool = Field(..., description="Whether clarification is enabled")
    default_report_style: str = Field(..., description="Default report style")


@router.get(
    '',
    summary="Get agent configuration",
    description="Get the complete agent system configuration including RAG, models, and workflow settings.",
    response_model=AgentConfigResponse,
    responses={
        200: {"description": "Agent configuration"},
        401: {"description": "Unauthorized"},
    },
    dependencies=[DependsJwtAuth],
)
async def get_config():
    """
    Get the complete agent system configuration.

    Returns:
    - RAG provider configuration
    - Available LLM models
    - Workflow settings (recursion limit, MCP, deep thinking, etc.)
    - Default report style
    """
    # Get configured LLM models
    raw_models = get_configured_llm_models()
    models = []
    for model in raw_models:
        if isinstance(model, dict):
            models.append(LLMModelInfo(
                name=model.get('name', 'Unknown'),
                provider=model.get('provider', 'Unknown'),
                model_id=model.get('model_id', model.get('name', 'Unknown')),
                is_default=model.get('is_default', False),
            ))

    return AgentConfigResponse(
        rag=RAGConfigInfo(provider=settings.AGENT_RAG_PROVIDER),
        models=models,
        recursion_limit=settings.AGENT_RECURSION_LIMIT,
        mcp_enabled=settings.AGENT_MCP_ENABLED,
        deep_thinking_enabled=settings.AGENT_ENABLE_DEEP_THINKING,
        clarification_enabled=settings.AGENT_ENABLE_CLARIFICATION,
        default_report_style=settings.AGENT_DEFAULT_REPORT_STYLE,
    )
