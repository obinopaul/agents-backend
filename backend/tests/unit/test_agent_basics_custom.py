
import pytest
from unittest.mock import MagicMock, patch
import sys

# Import the agent module
try:
    from backend.src.agents.agents import create_agent
    from langchain_core.tools import tool
except ImportError:
    # Fallback if environment is missing dependencies, but based on logs they exist.
    pytest.skip("Required dependencies not found", allow_module_level=True)

# --- Mock Dependencies ---

@pytest.fixture
def mock_dependencies():
    """Mock external dependencies: LLM, Prompt Template, Settings."""
    with patch("backend.src.agents.agents.get_llm") as mock_get_llm, \
         patch("backend.src.agents.agents.get_prompt_template") as mock_get_prompt, \
         patch("backend.src.agents.agents.langchain_create_agent") as mock_lc_create, \
         patch("backend.src.agents.agents.settings") as mock_settings:
        
        # Setup mocks
        mock_get_llm.return_value = MagicMock(name="MockLLM")
        mock_get_prompt.return_value = "System Prompt: You are a test agent."
        
        # Mock settings defaults (MUST set concrete values for math operations)
        mock_settings.MIDDLEWARE_ENABLE_SUMMARIZATION = False
        mock_settings.MIDDLEWARE_ENABLE_MODEL_RETRY = False
        mock_settings.MIDDLEWARE_ENABLE_TOOL_RETRY = False
        mock_settings.MIDDLEWARE_ENABLE_MODEL_CALL_LIMIT = False
        mock_settings.MIDDLEWARE_ENABLE_TOOL_CALL_LIMIT = False
        mock_settings.MIDDLEWARE_ENABLE_MODEL_FALLBACK = False

        # Numeric settings for middleware
        mock_settings.MIDDLEWARE_SUMMARIZATION_TRIGGER_TOKENS = 1000
        mock_settings.MIDDLEWARE_SUMMARIZATION_KEEP_MESSAGES = 10
        mock_settings.MIDDLEWARE_MODEL_MAX_RETRIES = 3
        mock_settings.MIDDLEWARE_MODEL_BACKOFF_FACTOR = 2.0
        mock_settings.MIDDLEWARE_MODEL_INITIAL_DELAY = 1.0
        mock_settings.MIDDLEWARE_TOOL_MAX_RETRIES = 3
        mock_settings.MIDDLEWARE_TOOL_BACKOFF_FACTOR = 2.0
        mock_settings.MIDDLEWARE_TOOL_INITIAL_DELAY = 1.0
        mock_settings.MIDDLEWARE_MODEL_CALL_THREAD_LIMIT = 50
        mock_settings.MIDDLEWARE_MODEL_CALL_RUN_LIMIT = 25
        mock_settings.MIDDLEWARE_TOOL_CALL_THREAD_LIMIT = 100
        mock_settings.MIDDLEWARE_TOOL_CALL_RUN_LIMIT = 50
        
        yield {
            "get_llm": mock_get_llm,
            "get_prompt": mock_get_prompt,
            "create_agent": mock_lc_create,
            "settings": mock_settings
        }

# --- Tools ---

@tool
def add_tool(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@tool
def multiply_tool(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# --- Tests ---

def test_create_agent_minimal(mock_dependencies):
    """Test creating an agent with minimal configuration."""
    tools = [add_tool]
    
    agent = create_agent(
        agent_name="TestAgent_Minimal",
        agent_type="tester",
        tools=tools,
        prompt_template="test_template",
        use_default_middleware=False
    )
    
    # Verification
    mock_dependencies["create_agent"].assert_called_once()
    call_kwargs = mock_dependencies["create_agent"].call_args[1]
    
    assert call_kwargs["name"] == "TestAgent_Minimal"
    assert call_kwargs["tools"] == tools
    assert call_kwargs["system_prompt"] == "System Prompt: You are a test agent."
    assert call_kwargs["middleware"] == ()

def test_create_agent_with_middleware(mock_dependencies):
    """Test creating an agent with default middleware configuration."""
    
    # Configure specific middleware via config dict
    mw_config = {
        "enable_model_retry": True,
        "model_max_retries": 5,
        "enable_tool_retry": True
    }
    
    agent = create_agent(
        agent_name="TestAgent_WithMW",
        agent_type="tester",
        tools=[add_tool, multiply_tool],
        prompt_template="test_template",
        use_default_middleware=True,
        middleware_config=mw_config
    )
    
    # Verification
    args, kwargs = mock_dependencies["create_agent"].call_args
    middleware_list = kwargs["middleware"]
    
    # We expect ModelRetryMiddleware and ToolRetryMiddleware to be added
    # Note: We rely on the fact that build_default_middleware logic works.
    assert len(middleware_list) >= 2 

def test_create_agent_with_interrupts(mock_dependencies):
    """Test agent creation with tool interrupts."""
    interrupt_tools = ["add_tool"]
    
    with patch("backend.src.agents.agents.wrap_tools_with_interceptor") as mock_wrap:
        mock_wrap.return_value = ["wrapped_add_tool", multiply_tool]
        
        agent = create_agent(
            agent_name="TestAgent_Interrupt",
            agent_type="tester",
            tools=[add_tool, multiply_tool],
            prompt_template="test_template",
            interrupt_before_tools=interrupt_tools,
            use_default_middleware=False
        )
        
        mock_wrap.assert_called_once()
        assert mock_wrap.call_args[0][1] == interrupt_tools
        
        # Verify passed tools are the wrapped ones
        call_kwargs = mock_dependencies["create_agent"].call_args[1]
        assert call_kwargs["tools"] == ["wrapped_add_tool", multiply_tool]

if __name__ == "__main__":
    # Allow running directly with python
    sys.exit(pytest.main(["-v", __file__]))
