
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import json

from backend.app.agent.api.v1.agent import _agent_stream_generator
from backend.src.services.session_sandbox_manager import SessionSandboxManager

@pytest.mark.asyncio
async def test_agent_stream_generator_uploads_large_tool_image():
    # Setup
    thread_id = "test-thread-agent"
    user_id = "test-user-agent"
    module_name = "general"
    
    # Large base64 image mock
    base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNiAAAABgDNjd8qAAAAAElFTkSuQmCC" # 1x1 pixel dot
    mime_type = "image/png"
    
    # Mock Event from Graph
    tool_output_list = [
        {"type": "text", "text": "Here is the image:"},
        {
            "type": "image", 
            "source": {
                "type": "base64", 
                "media_type": mime_type, 
                "data": base64_data
            }
        }
    ]
    
    mock_event = {
        "event": "on_tool_end",
        "name": "generate_image",
        "run_id": "call_456",
        "data": {
            "output": tool_output_list,
            "input": {"prompt": "draw a dot"}
        }
    }
    
    # Mocks
    graph = MagicMock()
    # Mock astream_events to yield the mock_event
    async def event_generator(*args, **kwargs):
        yield mock_event
    
    # Configure graph mocking
    mock_compiled_graph = MagicMock()
    mock_compiled_graph.astream_events = event_generator
    
    # Mock checkpointer manager context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_compiled_graph
    
    with patch("backend.src.graph.checkpointer.checkpointer_manager.get_graph_with_checkpointer", return_value=mock_cm), \
         patch("backend.src.graph.checkpointer.checkpointer_manager.warm_up_connection", return_value=True), \
         patch("backend.app.agent.api.v1.agent.process_and_stage_asset", new_callable=AsyncMock) as mock_upload, \
         patch("backend.app.agent.api.v1.agent.create_sse_adapter") as mock_adapter_factory, \
         patch("backend.app.agent.api.v1.agent.SessionSandboxManager") as MockSandboxManager:
         
        # Setup specific mocks
        mock_upload.return_value = ("http://s3.fake/agent_image.png", None)
        
        sandbox_manager = MockSandboxManager.return_value
        sandbox_manager.get_sandbox = AsyncMock(return_value=(MagicMock(sandbox_id="sandbox_1"), True))
        
        mock_adapter = MagicMock()
        mock_adapter_factory.return_value = mock_adapter
        mock_adapter.session_event.return_value = "event: session\ndata: {}\n\n"
        mock_adapter.status_update.return_value = "event: status\ndata: {}\n\n"
        # We care about tool_result
        mock_adapter.tool_result = MagicMock(return_value="event: tool_result_adapter\n\n")
        
        # Execute generator
        events = []
        async for event in _agent_stream_generator(
            graph=graph,
            module_name=module_name,
            messages=[],
            thread_id=thread_id,
            sandbox_manager=sandbox_manager,
            resources=[],
            max_plan_iterations=1,
            max_step_num=1,
            max_search_results=1,
            auto_accepted_plan=True,
            interrupt_feedback=None,
            enable_background_investigation=False,
            enable_web_search=False,
            locale="en-US",
            db_session=AsyncMock(), # Mock DB
            user_api_key="token",
            user_id=user_id
        ):
            events.append(event)
            
        # Verify Upload
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args.kwargs['user_id'] == user_id
        assert call_args.kwargs['thread_id'] == thread_id
        
        # Verify Event Output
        # The generator processes on_tool_end and yields 4 events:
        # 1. adapter.tool_call_stop
        # 2. tool_call_end (AG-UI)
        # 3. adapter.tool_result
        # 4. tool_result (AG-UI)
        
        # We need to find the raw "tool_result" event (AG-UI format) or check the modified output passed to adapter
        
        # Check adapter call
        mock_adapter.tool_result.assert_called_once()
        args, _ = mock_adapter.tool_result.call_args
        # args[2] is output
        msg_output = args[2]
        
        # Verify the output passed to adapter has URL
        found_url = False
        if isinstance(msg_output, list):
            for block in msg_output:
                if block.get("type") == "image" and block.get("source", {}).get("type") == "url":
                    if block["source"]["url"] == "http://s3.fake/agent_image.png":
                        found_url = True
        
        assert found_url, "Adapter should receive tool output with S3 URL"
