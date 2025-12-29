# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent API Router - v1.

This module consolidates all agent-related API endpoints into a single router
that can be included in the main FastAPI application.

Endpoints include:
- /chat/stream - AI agent chat with streaming responses
- /agent/stream - AI agent with sandbox support (lazy initialization)
- /generation/* - Content generation (podcast, PPT, prose, prompt enhancement)
- /tts - Text-to-speech synthesis
- /mcp/* - MCP server management
- /user-settings/mcp/* - User MCP tool configurations (Codex, Claude Code)
- /rag/* - RAG resource management
- /config - Agent configuration
- /credits/* - User credit balance and usage
- /sandboxes/* - Sandbox management and slides
"""

from fastapi import APIRouter

from backend.app.agent.api.v1.chat import router as chat_router
from backend.app.agent.api.v1.config import router as config_router
from backend.app.agent.api.v1.credits import router as credits_router
from backend.app.agent.api.v1.generation import router as generation_router
from backend.app.agent.api.v1.mcp import router as mcp_router
from backend.app.agent.api.v1.mcp_settings import router as mcp_settings_router
from backend.app.agent.api.v1.rag import router as rag_router
from backend.app.agent.api.v1.tts import router as tts_router
from backend.app.agent.api.v1.sandbox import router as sandbox_router
from backend.app.agent.api.v1.slides import router as slides_router
from backend.app.agent.api.v1.agent import router as agent_router

# Create the v1 agent router with the /agent prefix
v1 = APIRouter(prefix='/agent', tags=['Agent'])

# Include sub-routers with appropriate prefixes
v1.include_router(chat_router, prefix='/chat', tags=['Agent Chat'])
v1.include_router(agent_router, prefix='/agent', tags=['Agent Sandbox'])
v1.include_router(config_router, prefix='/config', tags=['Agent Configuration'])
v1.include_router(credits_router, tags=['Agent Credits'])
v1.include_router(generation_router, prefix='/generation', tags=['Agent Generation'])
v1.include_router(mcp_router, prefix='/mcp', tags=['Agent MCP'])
v1.include_router(mcp_settings_router, tags=['User MCP Settings'])
v1.include_router(rag_router, prefix='/rag', tags=['Agent RAG'])
v1.include_router(tts_router, prefix='/tts', tags=['Agent TTS'])
v1.include_router(sandbox_router, prefix='/sandboxes', tags=['Agent Sandbox Management'])
v1.include_router(slides_router, prefix='/sandboxes', tags=['Agent Slides'])

__all__ = ['v1']
