# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent RAG (Retrieval Augmented Generation) API endpoints.

This module provides endpoints for managing RAG resources and configuration.
"""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.src.rag.builder import build_retriever
from backend.src.rag.retriever import Resource

logger = logging.getLogger(__name__)

router = APIRouter()


class RAGResourceRequest(BaseModel):
    """Request model for RAG resource query."""

    query: Optional[str] = Field(None, description="Search query for filtering resources")


class RAGResourcesResponse(BaseModel):
    """Response model for RAG resources."""

    resources: List[Resource] = Field(default_factory=list, description="Available RAG resources")


class RAGConfigResponse(BaseModel):
    """Response model for RAG configuration."""

    provider: str = Field(..., description="Active RAG provider: 'milvus', 'qdrant', or empty")


@router.get(
    '/config',
    summary="Get RAG configuration",
    description="Get the current RAG provider configuration.",
    response_model=RAGConfigResponse,
    responses={
        200: {"description": "RAG configuration"},
        401: {"description": "Unauthorized"},
    },
    dependencies=[DependsJwtAuth],
)
async def rag_config():
    """
    Get the current RAG configuration.

    Returns the active RAG provider name (e.g., 'milvus', 'qdrant')
    or an empty string if no RAG provider is configured.
    """
    return RAGConfigResponse(provider=settings.AGENT_RAG_PROVIDER)


@router.get(
    '/resources',
    summary="List RAG resources",
    description="List available resources in the RAG system.",
    response_model=RAGResourcesResponse,
    responses={
        200: {"description": "List of RAG resources"},
        401: {"description": "Unauthorized"},
    },
    dependencies=[DependsJwtAuth],
)
async def rag_resources(query: Annotated[Optional[str], Query(description="Search query")] = None):
    """
    List available RAG resources.

    Optionally filter resources by a search query.
    Returns an empty list if no RAG provider is configured.
    """
    retriever = build_retriever()
    if retriever:
        resources = retriever.list_resources(query)
        return RAGResourcesResponse(resources=resources)
    return RAGResourcesResponse(resources=[])
