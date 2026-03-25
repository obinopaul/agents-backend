# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Agent API Router - v1.

This module consolidates all agent-related API endpoints into a single router
that can be included in the main FastAPI application.

Endpoints include:
- /chat/stream - AI agent chat with streaming responses (simple, no sandbox)
- /agent/stream - AI agent with sandbox support (lazy initialization)
- /chat-sessions/* - Chat session management and history
- /tts - Text-to-speech synthesis
- /mcp/* - MCP server management
- /user-settings/mcp/* - User MCP tool configurations (Codex, Claude Code)
- /user-settings/models/* - User LLM model settings and available models
- /rag/* - RAG resource management
- /config - Agent configuration
- /credits/* - User credit balance and usage
- /sandboxes/* - Sandbox management and slides
- /files/* - File upload and staging for chat attachments
- /wishlist/* - Session wishlist/bookmarking
"""

from fastapi import APIRouter

from backend.app.agent.api.v1.chat import router as chat_router
from backend.app.agent.api.v1.chat_sessions import router as chat_sessions_router
from backend.app.agent.api.v1.config import router as config_router
from backend.app.agent.api.v1.credits import router as credits_router
from backend.app.agent.api.v1.files import (
    router as files_router,
    upload_router, 
    chat_upload_router
)
from backend.app.agent.api.v1.mcp import router as mcp_router
from backend.app.agent.api.v1.mcp_settings import router as mcp_settings_router
from backend.app.agent.api.v1.model_settings import router as model_settings_router
from backend.app.agent.api.v1.rag import router as rag_router
from backend.app.agent.api.v1.tts import router as tts_router
from backend.app.agent.api.v1.sandbox import router as sandbox_router
from backend.app.agent.api.v1.slides import (
    router as slides_router,
    frontend_router as slides_frontend_router
)
from backend.app.agent.api.v1.templates import slide_router as slide_templates_router
from backend.app.agent.api.v1.agent import router as agent_router
from backend.app.agent.api.v1.wishlist import router as wishlist_router
from backend.app.agent.api.v1.connectors import router as connectors_router
from backend.app.agent.api.v1.enhance_prompt import router as enhance_prompt_router

# Create the v1 agent router with the /agent prefix
v1 = APIRouter(prefix='/agent', tags=['Agent'])

# Include sub-routers with appropriate prefixes
v1.include_router(chat_router, prefix='/chat', tags=['Agent Chat'])
v1.include_router(agent_router, prefix='/agent', tags=['Agent Sandbox Chat'])
v1.include_router(chat_sessions_router, tags=['Chat Sessions'])
v1.include_router(config_router, prefix='/config', tags=['Agent Configuration'])
v1.include_router(credits_router, tags=['Agent Credits'])
v1.include_router(files_router, prefix='/files', tags=['Agent Files'])
v1.include_router(mcp_router, prefix='/mcp', tags=['Agent MCP'])
v1.include_router(mcp_settings_router, tags=['User MCP Settings'])
v1.include_router(model_settings_router, tags=['User Model Settings'])
v1.include_router(rag_router, prefix='/rag', tags=['Agent RAG'])
v1.include_router(tts_router, prefix='/tts', tags=['Agent TTS'])
v1.include_router(sandbox_router, prefix='/sandboxes', tags=['Agent Sandbox Management'])
v1.include_router(slides_router, prefix='/sandboxes', tags=['Agent Slides'])
v1.include_router(slides_frontend_router, prefix='/slides', tags=['Frontend Slides'])
v1.include_router(upload_router, prefix='/upload', tags=['Agent Uploads'])
v1.include_router(chat_upload_router, prefix='/chat', tags=['Chat Uploads']) # Merges with /chat prefix
v1.include_router(slide_templates_router, prefix='/slide-templates', tags=['Slide Templates']) # Distinctly slide templates
v1.include_router(wishlist_router, tags=['Wishlist'])  # Session wishlist/bookmarks
v1.include_router(connectors_router, tags=['Connectors'])  # External service connectors (Google Drive, etc.)
v1.include_router(enhance_prompt_router, tags=['Prompt Enhancement'])  # LLM-powered prompt enhancement

__all__ = ['v1']


