
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import ToolMessage

from backend.app.agent.api.v1.chat import _process_message_chunk
from backend.app.agent.event_adapter import IIAgentSSEAdapter

@pytest.mark.asyncio
async def test_process_message_chunk_uploads_large_image():
    # Setup
    thread_id = "test-thread"
    user_id = "test-user"
    tool_call_id = "call_123"
    
    # Large base64 image mock
    base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNiAAAABgDNjd8qAAAAAElFTkSuQmCC" # 1x1 pixel dot
    mime_type = "image/png"
    
    # Create ToolMessage with base64 content
    message_chunk = ToolMessage(
        content=[
            {"type": "text", "text": "Here is the image:"},
            {
                "type": "image", 
                "source": {
                    "type": "base64", 
                    "media_type": mime_type, 
                    "data": base64_data
                }
            }
        ],
        tool_call_id=tool_call_id,
        name="generate_image",
    )
    
    message_metadata = {}
    agent = ("agent_node",)
    reasoning_state = MagicMock()
    adapter = IIAgentSSEAdapter(session_id=thread_id)
    db = AsyncMock() # Mock DB session
    
    # Mock asset service
    with patch("backend.app.agent.api.v1.chat.process_and_stage_asset", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = ("http://s3.fake/image.png", None)
        
        # Execute
        events = []
        async for event in _process_message_chunk(
            message_chunk, 
            message_metadata, 
            thread_id, 
            agent, 
            reasoning_state, 
            adapter, 
            user_id, 
            db
        ):
            events.append(event)
            
        # Verify
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args.kwargs['user_id'] == user_id
        assert call_args.kwargs['thread_id'] == thread_id
        assert call_args.kwargs['mime_type'] == mime_type
        
        # Verify message content was modified in place (or at least in the events)
        # Note: _process_message_chunk modifies message_chunk.content in reference implementation
        
        # Check event structure
        # We expect a tool_result event
        tool_result_events = [e for e in events if "tool_result" in e]
        assert len(tool_result_events) >= 1
        
        # Find the event that carries the content
        # It's usually the legacy "tool_result" event or adapter output
        
        # Check that content block is now URL
        found_url_block = False
        for block in message_chunk.content:
            if block["type"] == "image" and block["source"]["type"] == "url":
                if block["source"]["url"] == "http://s3.fake/image.png":
                    found_url_block = True
                    
        assert found_url_block, "Message content should contain replaced URL block"

@pytest.mark.asyncio
async def test_process_message_chunk_skips_upload_without_db_or_userid():
     # Setup
    thread_id = "test-thread"
    tool_call_id = "call_123"
    
    base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNiAAAABgDNjd8qAAAAAElFTkSuQmCC"
    
    message_chunk = ToolMessage(
        content=[
            {
                "type": "image", 
                "source": {
                    "type": "base64", 
                    "media_type": "image/png", 
                    "data": base64_data
                }
            }
        ],
        tool_call_id=tool_call_id,
        name="generate_image",
    )
    
    message_metadata = {}
    agent = ("agent_node",)
    reasoning_state = MagicMock()
    adapter = IIAgentSSEAdapter(session_id=thread_id)
    
    # Execute WITHOUT user_id and db
    with patch("backend.app.agent.api.v1.chat.process_and_stage_asset", new_callable=AsyncMock) as mock_upload:
        events = []
        async for event in _process_message_chunk(
            message_chunk, 
            message_metadata, 
            thread_id, 
            agent, 
            reasoning_state, 
            adapter
            # Missing user_id and db
        ):
            events.append(event)
            
        mock_upload.assert_not_called()
        
        # Content should remain base64
        assert message_chunk.content[0]["source"]["type"] == "base64"
