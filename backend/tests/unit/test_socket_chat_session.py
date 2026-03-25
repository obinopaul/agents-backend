
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.agent.model.chat_session import AgentType
from backend.common.socketio.command.query_handler import QueryHandler

# =============================================================================
# AgentType Tests
# =============================================================================

def test_agent_type_enum():
    """Verify AgentType enum values and properties."""
    # Verify all enum values exist
    assert AgentType.CHAT == "chat"
    assert AgentType.GENERAL == "general"
    assert AgentType.DEEP_RESEARCH == "deep_research"
    assert AgentType.ACADEMIC == "academic"
    assert AgentType.DESIGN == "design"
    assert AgentType.DEV == "dev"
    assert AgentType.DATA_SCIENTIST == "data_scientist"
    assert AgentType.SLIDES == "slides"
    assert AgentType.DOCUMENTS == "documents"
    assert AgentType.QUANT == "quant"
    assert AgentType.EXCALIDRAW == "excalidraw"

def test_agent_type_requires_sandbox():
    """Verify requires_sandbox property logic."""
    # CHAT should NOT require sandbox
    assert AgentType.CHAT.requires_sandbox is False
    
    # All other types MUST require sandbox
    assert AgentType.GENERAL.requires_sandbox is True
    assert AgentType.DEEP_RESEARCH.requires_sandbox is True
    assert AgentType.DEV.requires_sandbox is True
    assert AgentType.EXCALIDRAW.requires_sandbox is True

def test_agent_type_helpers():
    """Verify helper methods."""
    no_sandbox = AgentType.get_no_sandbox_types()
    assert AgentType.CHAT in no_sandbox
    assert len(no_sandbox) == 1
    
    sandbox_types = AgentType.get_sandbox_types()
    assert AgentType.GENERAL in sandbox_types
    assert AgentType.CHAT not in sandbox_types
    assert len(sandbox_types) == 10

# =============================================================================
# QueryHandler Tests
# =============================================================================

@pytest.mark.asyncio
async def test_get_agent_category_mapping():
    """Verify _get_agent_category maps all 11 types to valid 3 categories."""
    handler = QueryHandler(sio=AsyncMock())
    
    # Test all mappings
    # General group
    assert handler._get_agent_category(AgentType.CHAT) == "general"
    assert handler._get_agent_category(AgentType.GENERAL) == "general"
    assert handler._get_agent_category(AgentType.DEV) == "general"
    assert handler._get_agent_category(AgentType.DESIGN) == "general"
    assert handler._get_agent_category(AgentType.EXCALIDRAW) == "general"
    
    # Scientific group
    assert handler._get_agent_category(AgentType.DEEP_RESEARCH) == "scientific"
    assert handler._get_agent_category(AgentType.DATA_SCIENTIST) == "scientific"
    assert handler._get_agent_category(AgentType.QUANT) == "scientific"
    
    # Academic group
    assert handler._get_agent_category(AgentType.ACADEMIC) == "academic"
    assert handler._get_agent_category(AgentType.SLIDES) == "academic"
    assert handler._get_agent_category(AgentType.DOCUMENTS) == "academic"

@pytest.mark.asyncio
async def test_handle_routing_chat_no_sandbox():
    """Verify routing to _run_chat_without_sandbox for CHAT type."""
    # Setup mocks
    mock_sio = AsyncMock()
    handler = QueryHandler(sio=mock_sio)
    
    # Mock internal methods to verify routing
    handler._run_chat_without_sandbox = AsyncMock()
    handler._run_agent_with_sandbox = AsyncMock()
    handler.send_status_update = AsyncMock()
    handler.broadcast_to_session = AsyncMock()
    
    # Mock database session
    mock_db_session = AsyncMock()
    mock_session_obj = MagicMock()
    mock_session_obj.id = 1
    mock_session_obj.agent_type = "chat"
    
    with patch("backend.common.socketio.command.query_handler.async_db_session", return_value=mock_db_session):
        with patch("backend.common.socketio.command.query_handler.chat_session_dao.get_by_uuid", return_value=mock_session_obj):
            with patch("backend.common.socketio.command.query_handler.chat_event_dao.create_user_message", new=AsyncMock()):
                
                # Execute handle with CHAT type
                await handler.handle(
                    content={"message": "hello", "agent_type": "chat"},
                    session_uuid="uuid-123",
                    user_id=1,
                    sid="sid-456"
                )
    
    # Verify routing
    handler._run_chat_without_sandbox.assert_called_once()
    handler._run_agent_with_sandbox.assert_not_called()

@pytest.mark.asyncio
async def test_handle_routing_general_sandbox():
    """Verify routing to _run_agent_with_sandbox for GENERAL type."""
    # Setup mocks
    mock_sio = AsyncMock()
    handler = QueryHandler(sio=mock_sio)
    
    # Mock internal methods
    handler._run_chat_without_sandbox = AsyncMock()
    handler._run_agent_with_sandbox = AsyncMock()
    handler.send_status_update = AsyncMock()
    handler.broadcast_to_session = AsyncMock()
    
    # Mock database session
    mock_db_session = AsyncMock()
    mock_session_obj = MagicMock()
    mock_session_obj.id = 1
    mock_session_obj.agent_type = "general"
    
    with patch("backend.common.socketio.command.query_handler.async_db_session", return_value=mock_db_session):
        with patch("backend.common.socketio.command.query_handler.chat_session_dao.get_by_uuid", return_value=mock_session_obj):
            with patch("backend.common.socketio.command.query_handler.chat_event_dao.create_user_message", new=AsyncMock()):
                
                # Execute handle with GENERAL type
                await handler.handle(
                    content={"message": "run code", "agent_type": "general"},
                    session_uuid="uuid-123",
                    user_id=1,
                    sid="sid-456"
                )
    
    # Verify routing
    handler._run_agent_with_sandbox.assert_called_once()
    handler._run_chat_without_sandbox.assert_not_called()

if __name__ == "__main__":
    import asyncio
    # Simple runner for manual testing if needed
    pass
