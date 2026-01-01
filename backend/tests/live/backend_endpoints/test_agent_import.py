#!/usr/bin/env python3
# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Backend Agent Direct Import Test

This script tests the agent by directly importing and invoking the graph,
bypassing the HTTP endpoint. This is useful for:

1. Testing graph logic in isolation
2. Debugging without HTTP overhead
3. Verifying tool bindings work correctly
4. Testing specific modules (general, research, etc.)

Unlike test_agent_lifecycle.py which tests via HTTP endpoints, this script
directly invokes the LangGraph workflow.

Prerequisites:
    1. Backend dependencies installed
    2. Database configured (PostgreSQL)
    3. E2B_API_KEY configured for sandbox tests
    4. LLM provider configured (OPENAI_API_KEY, etc.)

Usage:
    python backend/tests/live/backend_endpoints/test_agent_import.py
    python backend/tests/live/backend_endpoints/test_agent_import.py --module research
    python backend/tests/live/backend_endpoints/test_agent_import.py --no-sandbox
"""

import asyncio
import argparse
import sys
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, "backend", ".env"))


# =============================================================================
# Imports (after path setup)
# =============================================================================

from langchain_core.messages import HumanMessage, AIMessage


# =============================================================================
# Test Runner
# =============================================================================

class AgentImportTester:
    """
    Tests the agent graph by direct import.
    
    This bypasses HTTP and directly invokes:
    1. ModuleRegistry.get_graph() to get the compiled graph
    2. graph.astream() to run the workflow
    """
    
    def __init__(
        self,
        module: str = "general",
        use_sandbox: bool = False,
        verbose: bool = False
    ):
        self.module = module
        self.use_sandbox = use_sandbox
        self.verbose = verbose
        self.start_time = time.time()
    
    def log(self, message: str, level: str = "info"):
        """Log with timestamp."""
        if level == "verbose" and not self.verbose:
            return
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:6.1f}s] {message}")
    
    async def test_graph_basic(self, prompt: str = "What is 2 + 2?") -> bool:
        """
        Test basic graph invocation without sandbox.
        
        This tests:
        - Graph compilation
        - LLM binding
        - Basic tool usage (if available)
        """
        self.log("=" * 70)
        self.log("🧪 Agent Import Test (Direct Graph)")
        self.log(f"   Module: {self.module}")
        self.log(f"   Sandbox: {'enabled' if self.use_sandbox else 'disabled'}")
        self.log("=" * 70)
        
        try:
            # Import registry and get graph
            self.log("\n📋 Step 1: Loading module graph...")
            from backend.app.agent.api.v1.agent import ModuleRegistry
            
            try:
                graph = ModuleRegistry.get_graph(self.module)
                self.log(f"   ✅ Loaded '{self.module}' graph")
            except NotImplementedError as e:
                self.log(f"   ❌ Module not implemented: {e}")
                return False
            except Exception as e:
                self.log(f"   ❌ Failed to load graph: {e}")
                return False
            
            # Prepare input
            self.log("\n📋 Step 2: Preparing input...")
            thread_id = f"import-test-{uuid4().hex[:8]}"
            
            input_state = {
                "messages": [HumanMessage(content=prompt)],
                "locale": "en-US",
                "auto_accepted_plan": True,
                "enable_background_investigation": False,
            }
            
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "enable_web_search": False,
                    "max_search_results": 3,
                    "max_plan_iterations": 1,
                    "max_step_num": 2,
                    "enable_deep_thinking": False,
                },
                "recursion_limit": 25,
            }
            
            # Add sandbox config if enabled
            if self.use_sandbox:
                self.log("   ⚠️ Sandbox mode requires MCP URL - skipping for import test")
                # Note: For full sandbox test, use test_agent_lifecycle.py instead
            
            self.log(f"   Thread ID: {thread_id}")
            self.log(f"   Prompt: {prompt[:80]}...")
            
            # Run graph
            self.log("\n📋 Step 3: Running graph...")
            
            messages_received = []
            tool_calls = []
            
            async for event in graph.astream(input_state, config):
                # Process events
                for node_name, node_output in event.items():
                    if node_name == "__end__":
                        continue
                    
                    self.log(f"   📍 Node: {node_name}", "verbose")
                    
                    # Extract messages
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            if hasattr(msg, "content") and msg.content:
                                content_preview = str(msg.content)[:100]
                                self.log(f"      Message: {content_preview}...", "verbose")
                                messages_received.append(msg)
                            
                            # Track tool calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tool_name = tc.get("name", "unknown")
                                    tool_calls.append(tool_name)
                                    self.log(f"      🔧 Tool call: {tool_name}")
            
            # Summarize results
            self.log("\n📊 RESULTS")
            self.log("-" * 50)
            
            if messages_received:
                last_msg = messages_received[-1]
                if hasattr(last_msg, "content"):
                    response = str(last_msg.content)
                    self.log(f"📝 Response ({len(response)} chars):")
                    print(response[:500] + ("..." if len(response) > 500 else ""))
                    self.log("-" * 50)
            
            self.log(f"   Messages received: {len(messages_received)}")
            self.log(f"   Tool calls: {len(tool_calls)} ({', '.join(tool_calls) if tool_calls else 'none'})")
            
            # Determine success
            success = len(messages_received) > 0
            
            self.log("\n" + "=" * 70)
            if success:
                self.log("✅ TEST PASSED")
            else:
                self.log("❌ TEST FAILED - No messages received")
            self.log(f"   Duration: {time.time() - self.start_time:.1f}s")
            self.log("=" * 70)
            
            return success
            
        except Exception as e:
            import traceback
            self.log(f"\n❌ ERROR: {e}")
            if self.verbose:
                traceback.print_exc()
            return False
    
    async def test_graph_with_tools(self) -> bool:
        """
        Test graph with a prompt that should trigger tool usage.
        """
        prompt = "Calculate the fibonacci sequence up to 10 terms and show the result."
        return await self.test_graph_basic(prompt)


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test agent by direct import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests the agent graph directly without HTTP.
For full lifecycle testing with sandbox, use test_agent_lifecycle.py.

Examples:
  python test_agent_import.py
  python test_agent_import.py --module research
  python test_agent_import.py --prompt "Write a haiku about coding"
  python test_agent_import.py --verbose
        """
    )
    parser.add_argument("--module", default="general", 
                       help="Agent module to test (general, research)")
    parser.add_argument("--prompt", type=str,
                       default="What is the capital of France? Answer in one sentence.",
                       help="Prompt to send to agent")
    parser.add_argument("--with-tools", action="store_true",
                       help="Use a prompt that triggers tool usage")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    tester = AgentImportTester(
        module=args.module,
        use_sandbox=False,  # Import test doesn't support sandbox directly
        verbose=args.verbose
    )
    
    if args.with_tools:
        success = await tester.test_graph_with_tools()
    else:
        success = await tester.test_graph_basic(args.prompt)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(1)
