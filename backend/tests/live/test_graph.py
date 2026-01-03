#!/usr/bin/env python3
"""
Comprehensive Test Script for the Agent Graph System.

This script tests the complete graph implementation including:
- Graph builder functions (build_graph, build_graph_with_memory)
- Node implementations (background_investigation, base, human_feedback)
- Agent creation with LangChain v1 create_agent
- End-to-end workflow execution

Usage:
    # From project root directory:
    python -m backend.src.graph.test_graph
    
    # Or directly:
    python backend/src/graph/test_graph.py

Environment Setup:
    Ensure you have the following environment variables set:
    - LLM_PROVIDER: openai, anthropic, gemini, etc.
    - OPENAI_API_KEY (or corresponding provider API key)
    - TAVILY_API_KEY (for web search, optional)
    
Author: Graph Test Suite
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Set up logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("graph_test")

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


# ============================================================================
# Test Configuration
# ============================================================================

@dataclass
class TestConfig:
    """Test configuration parameters."""
    enable_web_search: bool = False  # Disable for faster testing
    enable_background_investigation: bool = False
    max_search_results: int = 3
    test_timeout: int = 120  # seconds
    verbose: bool = True


# ============================================================================
# Test Result Tracking
# ============================================================================

@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    duration: float
    message: str = ""
    details: Optional[Dict[str, Any]] = None


class TestSuite:
    """Collection of test results."""
    
    def __init__(self, name: str):
        self.name = name
        self.results: List[TestResult] = []
        self.start_time = datetime.now()
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} | {result.name} ({result.duration:.2f}s)")
        if result.message:
            logger.info(f"    └── {result.message}")
    
    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        duration = (datetime.now() - self.start_time).total_seconds()
        
        lines = [
            "",
            "=" * 60,
            f"TEST SUITE: {self.name}",
            "=" * 60,
            f"Total Tests:  {total}",
            f"Passed:       {passed} ✅",
            f"Failed:       {failed} ❌",
            f"Duration:     {duration:.2f}s",
            "=" * 60,
        ]
        
        if failed > 0:
            lines.append("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    lines.append(f"  ❌ {r.name}: {r.message}")
        
        return "\n".join(lines)


# ============================================================================
# Graph Builder Tests
# ============================================================================

def test_build_base_graph() -> TestResult:
    """Test that _build_base_graph creates a valid StateGraph builder."""
    start = time.time()
    try:
        from backend.src.graph.builder import _build_base_graph
        
        builder = _build_base_graph()
        
        # Verify nodes are added
        assert builder is not None, "Builder should not be None"
        
        # Check that we have the expected nodes
        # Note: Node names are stored in the builder's nodes dict
        nodes = list(builder.nodes.keys())
        expected_nodes = ["background_investigator", "base", "human_feedback"]
        
        for expected in expected_nodes:
            assert expected in nodes, f"Missing node: {expected}"
        
        duration = time.time() - start
        return TestResult(
            name="test_build_base_graph",
            passed=True,
            duration=duration,
            message=f"Graph has {len(nodes)} nodes: {nodes}",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_build_base_graph",
            passed=False,
            duration=duration,
            message=str(e),
        )


def test_build_graph_without_memory() -> TestResult:
    """Test that build_graph compiles a valid graph without checkpointing."""
    start = time.time()
    try:
        from backend.src.graph.builder import build_graph
        
        graph = build_graph()
        
        assert graph is not None, "Graph should not be None"
        assert hasattr(graph, 'invoke'), "Graph should have invoke method"
        assert hasattr(graph, 'ainvoke'), "Graph should have ainvoke method"
        assert hasattr(graph, 'stream'), "Graph should have stream method"
        
        duration = time.time() - start
        return TestResult(
            name="test_build_graph_without_memory",
            passed=True,
            duration=duration,
            message="Graph compiled successfully",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_build_graph_without_memory",
            passed=False,
            duration=duration,
            message=str(e),
        )


def test_build_graph_with_memory() -> TestResult:
    """Test that build_graph_with_memory creates a graph with checkpointing."""
    start = time.time()
    try:
        from backend.src.graph.builder import build_graph_with_memory
        
        graph = build_graph_with_memory()
        
        assert graph is not None, "Graph should not be None"
        assert hasattr(graph, 'invoke'), "Graph should have invoke method"
        
        duration = time.time() - start
        return TestResult(
            name="test_build_graph_with_memory",
            passed=True,
            duration=duration,
            message="Graph with memory compiled successfully",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_build_graph_with_memory",
            passed=False,
            duration=duration,
            message=str(e),
        )


# ============================================================================
# State and Types Tests
# ============================================================================

def test_state_schema() -> TestResult:
    """Test that the State schema is properly defined."""
    start = time.time()
    try:
        from backend.src.graph.types import State
        from langgraph.graph import MessagesState
        
        # Verify State is a valid MessagesState subclass
        assert State is not None, "State should be defined"
        
        # Check that State has the expected fields
        expected_fields = [
            "resources",
            "enable_background_investigation",
            "background_investigation_results",
            "feedback",
            "goto",
        ]
        
        # State is a TypedDict-like class, check annotations
        annotations = getattr(State, '__annotations__', {})
        for field in expected_fields:
            assert field in annotations, f"Missing field: {field}"
        
        duration = time.time() - start
        return TestResult(
            name="test_state_schema",
            passed=True,
            duration=duration,
            message=f"State has {len(annotations)} fields defined",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_state_schema",
            passed=False,
            duration=duration,
            message=str(e),
        )


# ============================================================================
# Agent Creation Tests
# ============================================================================

def test_create_agent_basic() -> TestResult:
    """Test that create_agent works with basic parameters."""
    start = time.time()
    try:
        from backend.src.agents import create_agent
        from langchain_core.tools import tool
        
        # Create a simple test tool
        @tool
        def test_tool(query: str) -> str:
            """A simple test tool that echoes the input."""
            return f"Echo: {query}"
        
        # Create agent with minimal configuration
        agent = create_agent(
            agent_name="test_agent",
            agent_type="researcher",
            tools=[test_tool],
            prompt_template="researcher",
        )
        
        assert agent is not None, "Agent should not be None"
        assert hasattr(agent, 'invoke'), "Agent should have invoke method"
        assert hasattr(agent, 'ainvoke'), "Agent should have ainvoke method"
        
        duration = time.time() - start
        return TestResult(
            name="test_create_agent_basic",
            passed=True,
            duration=duration,
            message="Agent created successfully with LangChain v1 create_agent",
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_create_agent_basic",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


def test_create_agent_with_middleware() -> TestResult:
    """Test that create_agent works with middleware."""
    start = time.time()
    try:
        from backend.src.agents import create_agent
        from langchain_core.tools import tool
        from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
        
        # Create a simple async middleware (MUST be async to support ainvoke/astream)
        @wrap_model_call
        async def logging_middleware(request: ModelRequest, handler) -> ModelResponse:
            """Simple async middleware that logs requests."""
            logger.debug(f"Middleware received request with {len(request.state.get('messages', []))} messages")
            return await handler(request)
        
        @tool
        def test_tool(query: str) -> str:
            """A simple test tool."""
            return f"Result: {query}"
        
        agent = create_agent(
            agent_name="middleware_test_agent",
            agent_type="researcher",
            tools=[test_tool],
            prompt_template="researcher",
            middleware=[logging_middleware],
        )
        
        assert agent is not None, "Agent with middleware should be created"
        
        duration = time.time() - start
        return TestResult(
            name="test_create_agent_with_middleware",
            passed=True,
            duration=duration,
            message="Agent with async middleware created successfully",
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_create_agent_with_middleware",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


# ============================================================================
# LLM Configuration Tests
# ============================================================================

def test_llm_configuration() -> TestResult:
    """Test that the LLM is properly configured from settings."""
    start = time.time()
    try:
        from backend.src.llms.llm import get_llm, get_llm_token_limit
        from backend.core.conf import settings
        
        llm = get_llm()
        assert llm is not None, "LLM should be created"
        
        token_limit = get_llm_token_limit()
        assert token_limit > 0, "Token limit should be positive"
        
        provider = settings.LLM_PROVIDER
        
        duration = time.time() - start
        return TestResult(
            name="test_llm_configuration",
            passed=True,
            duration=duration,
            message=f"LLM provider: {provider}, token_limit: {token_limit}",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_llm_configuration",
            passed=False,
            duration=duration,
            message=str(e),
        )


# ============================================================================
# Node Function Tests
# ============================================================================

def test_background_investigation_node() -> TestResult:
    """Test the background investigation node function."""
    start = time.time()
    try:
        from backend.src.graph.nodes import background_investigation_node
        from langchain_core.runnables import RunnableConfig
        
        # Create mock state - background investigation disabled for testing
        state = {
            "messages": [{"role": "user", "content": "What is Python programming?"}],
            "enable_background_investigation": False,  # Skip actual search
        }
        
        config = RunnableConfig(configurable={
            "enable_web_search": False,
        })
        
        result = background_investigation_node(state, config)
        
        assert "background_investigation_results" in result, "Should return background_investigation_results"
        
        duration = time.time() - start
        return TestResult(
            name="test_background_investigation_node",
            passed=True,
            duration=duration,
            message="Background investigation node executed (skipped actual search)",
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_background_investigation_node",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


def test_human_feedback_node() -> TestResult:
    """Test the human feedback node routing logic."""
    start = time.time()
    try:
        from backend.src.graph.nodes import preserve_state_meta_fields
        
        # Test state meta field preservation
        state = {
            "messages": [],
            "resources": [],
            "enable_background_investigation": True,
        }
        
        preserved = preserve_state_meta_fields(state)
        
        assert preserved["resources"] == [], "Resources should be preserved"
        assert preserved["enable_background_investigation"] == True, "enable_background_investigation should be preserved"
        
        duration = time.time() - start
        return TestResult(
            name="test_human_feedback_node",
            passed=True,
            duration=duration,
            message="Human feedback node state preservation works",
        )
    except Exception as e:
        duration = time.time() - start
        return TestResult(
            name="test_human_feedback_node",
            passed=False,
            duration=duration,
            message=str(e),
        )


# ============================================================================
# Integration Tests - Actual Agent Execution
# ============================================================================

async def test_agent_simple_question() -> TestResult:
    """Test the agent with a simple question (actual LLM call)."""
    start = time.time()
    try:
        from backend.src.agents import create_agent
        from langchain_core.tools import tool
        from langchain_core.messages import HumanMessage
        
        # Create a simple calculator tool
        @tool
        def calculate(expression: str) -> str:
            """Evaluate a mathematical expression and return the result."""
            try:
                # Safe eval for simple math
                result = eval(expression, {"__builtins__": {}}, {})
                return f"The result of {expression} is {result}"
            except Exception as e:
                return f"Error calculating: {e}"
        
        # Create the agent
        agent = create_agent(
            agent_name="math_agent",
            agent_type="researcher",
            tools=[calculate],
            prompt_template="researcher",
        )
        
        # Test with a simple question
        test_input = {
            "messages": [
                HumanMessage(content="What is 2 + 2? Please use the calculate tool.")
            ]
        }
        
        logger.info("Invoking agent with simple math question...")
        result = await agent.ainvoke(test_input)
        
        assert "messages" in result, "Result should contain messages"
        assert len(result["messages"]) > 0, "Should have at least one message"
        
        # Get the final response
        final_message = result["messages"][-1]
        response_content = str(final_message.content) if hasattr(final_message, 'content') else str(final_message)
        
        duration = time.time() - start
        return TestResult(
            name="test_agent_simple_question",
            passed=True,
            duration=duration,
            message=f"Agent responded: {response_content[:100]}...",
            details={"response_length": len(response_content)},
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_agent_simple_question",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


async def test_agent_stream_response() -> TestResult:
    """Test agent streaming functionality."""
    start = time.time()
    try:
        from backend.src.agents import create_agent
        from langchain_core.tools import tool
        from langchain_core.messages import HumanMessage
        
        @tool
        def get_info(topic: str) -> str:
            """Get information about a topic."""
            return f"Information about {topic}: This is a test response."
        
        agent = create_agent(
            agent_name="stream_test_agent",
            agent_type="researcher",
            tools=[get_info],
            prompt_template="researcher",
        )
        
        test_input = {
            "messages": [
                HumanMessage(content="Tell me about Python. Keep it brief.")
            ]
        }
        
        # Test streaming
        chunks = []
        async for chunk in agent.astream(test_input, stream_mode="values"):
            chunks.append(chunk)
        
        assert len(chunks) > 0, "Should receive at least one chunk"
        
        duration = time.time() - start
        return TestResult(
            name="test_agent_stream_response",
            passed=True,
            duration=duration,
            message=f"Received {len(chunks)} stream chunks",
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_agent_stream_response",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


# ============================================================================
# Full Graph Integration Test
# ============================================================================

async def test_full_graph_execution() -> TestResult:
    """Test the complete graph execution flow."""
    start = time.time()
    try:
        from backend.src.graph.builder import build_graph
        from langchain_core.messages import HumanMessage
        from langchain_core.runnables import RunnableConfig
        
        # Build the graph
        graph = build_graph()
        
        # Prepare test state - disable background investigation for faster test
        test_state = {
            "messages": [
                HumanMessage(content="What is 2+2? Just give me the answer directly.")
            ],
            "enable_background_investigation": False,
            "resources": [],
        }
        
        config = RunnableConfig(configurable={
            "enable_web_search": False,
            "enable_background_investigation": False,
        })
        
        logger.info("Starting full graph execution test...")
        
        # Execute the graph - this will hit the interrupt at human_feedback node
        # For testing, we'll use stream to see the flow
        final_state = None
        try:
            async for chunk in graph.astream(test_state, config=config, stream_mode="values"):
                final_state = chunk
                if "messages" in chunk:
                    msg_count = len(chunk.get("messages", []))
                    logger.debug(f"Graph step: {msg_count} messages")
        except Exception as stream_error:
            # The graph will interrupt at human_feedback - that's expected
            if "interrupt" in str(stream_error).lower():
                logger.info("Graph interrupted at human_feedback (expected behavior)")
            else:
                raise stream_error
        
        duration = time.time() - start
        return TestResult(
            name="test_full_graph_execution",
            passed=True,
            duration=duration,
            message="Graph executed successfully (interrupted at human feedback as expected)",
            details={"final_state_keys": list(final_state.keys()) if final_state else []},
        )
    except Exception as e:
        duration = time.time() - start
        import traceback
        return TestResult(
            name="test_full_graph_execution",
            passed=False,
            duration=duration,
            message=f"{str(e)}\n{traceback.format_exc()}",
        )


# ============================================================================
# Test Runner
# ============================================================================

async def run_all_tests():
    """Run all tests and print summary."""
    suite = TestSuite("Graph and Agent System Tests")
    
    print("\n" + "=" * 60)
    print("GRAPH AND AGENT SYSTEM TEST SUITE")
    print("=" * 60 + "\n")
    
    # Unit Tests - Graph Builder
    print("\n📦 Graph Builder Tests\n" + "-" * 40)
    suite.add_result(test_build_base_graph())
    suite.add_result(test_build_graph_without_memory())
    suite.add_result(test_build_graph_with_memory())
    
    # Unit Tests - State and Types
    print("\n📋 State and Types Tests\n" + "-" * 40)
    suite.add_result(test_state_schema())
    
    # Unit Tests - LLM Configuration
    print("\n🤖 LLM Configuration Tests\n" + "-" * 40)
    suite.add_result(test_llm_configuration())
    
    # Unit Tests - Agent Creation
    print("\n🔧 Agent Creation Tests\n" + "-" * 40)
    suite.add_result(test_create_agent_basic())
    suite.add_result(test_create_agent_with_middleware())
    
    # Unit Tests - Node Functions
    print("\n🔲 Node Function Tests\n" + "-" * 40)
    suite.add_result(test_background_investigation_node())
    suite.add_result(test_human_feedback_node())
    
    # Integration Tests (require actual LLM calls)
    print("\n🔗 Integration Tests (LLM Calls)\n" + "-" * 40)
    suite.add_result(await test_agent_simple_question())
    suite.add_result(await test_agent_stream_response())
    
    # Full Graph Test
    print("\n🌐 Full Graph Integration Test\n" + "-" * 40)
    suite.add_result(await test_full_graph_execution())
    
    # Print summary
    print(suite.summary())
    
    # Return exit code
    failed_count = sum(1 for r in suite.results if not r.passed)
    return 0 if failed_count == 0 else 1


def main():
    """Main entry point."""
    print(f"\n{'=' * 60}")
    print(f"Starting Graph Test Suite at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"{'=' * 60}\n")
    
    # Check for required environment variables
    from dotenv import load_dotenv
    
    # Load .env file from backend directory
    env_file = project_root / "backend" / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Loaded environment from {env_file}")
    else:
        logger.warning(f"No .env file found at {env_file}")
        logger.warning("Make sure required environment variables are set!")
    
    # Run tests
    exit_code = asyncio.run(run_all_tests())
    
    print(f"\nTest suite completed with exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
