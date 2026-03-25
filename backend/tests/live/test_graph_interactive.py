#!/usr/bin/env python3
"""
Interactive Graph Test - Tests the agent graph directly without the API.

Usage:
    python backend/tests/live/test_graph_interactive.py

This script:
1. Shows all tools that the agent will use (same logic as base_node)
2. Allows interactive input from terminal
3. Streams the graph execution with full tool visibility
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
env_file = project_root / "backend" / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")


def build_tools_list(enable_web_search=False, enable_feedback_tool=False, enable_added_tools=True):
    """Build the same tools list that base_node uses."""
    # Same imports as nodes.py
    from backend.src.tools import (
        people_search_tool,
        company_search_tool,
        paper_search_tool,
        get_paper_details_tool,
        search_authors_tool,
        get_author_details_tool,
        get_author_papers_tool,
        semantic_scholar_search_tool,
        arxiv_search_tool,
        pubmed_central_tool,
        create_view_image_tool,
        human_feedback_tool,
        crawl_tool,
        get_web_search_tool,
    )
    
    tools = []
    
    # Same logic as base_node (lines 731-760 in nodes.py)
    if enable_feedback_tool:
        tools.append(human_feedback_tool)
    
    if enable_added_tools:
        tools.extend([
            people_search_tool,
            company_search_tool,
            paper_search_tool,
            get_paper_details_tool,
            search_authors_tool,
            get_author_details_tool,
            get_author_papers_tool,
            semantic_scholar_search_tool,
            arxiv_search_tool,
            pubmed_central_tool,
            create_view_image_tool,
        ])
    
    if enable_web_search:
        tools.extend([get_web_search_tool(max_results=3), crawl_tool])
    
    return tools


def print_tools(tools):
    """Print all tools with their names and descriptions."""
    print("\n" + "=" * 60)
    print("📦 AGENT TOOLS (same as base_node)")
    print("=" * 60)
    
    for i, tool in enumerate(tools, 1):
        name = getattr(tool, 'name', str(type(tool).__name__))
        desc = getattr(tool, 'description', 'No description')
        # Truncate description
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  {i:2}. {name}")
        print(f"      └─ {desc}")
    
    print(f"\n📊 Total: {len(tools)} tools")
    print("=" * 60)


async def run_interactive_test():
    """Run interactive graph test with full streaming visibility."""
    from backend.src.graph.builder import build_graph
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
    
    # Build and show tools first (same config as we'll use)
    tools = build_tools_list(
        enable_web_search=False,
        enable_feedback_tool=False,
        enable_added_tools=True,
    )
    print_tools(tools)
    
    print("\n" + "=" * 60)
    print("INTERACTIVE GRAPH TEST")
    print("=" * 60)
    print("Type 'quit' or 'exit' to stop.\n")
    
    # Build the graph
    print("Building graph...")
    graph = build_graph()
    print(f"✅ Graph built: {type(graph).__name__}")
    print(f"   Nodes: {list(graph.nodes.keys())}\n")
    
    # Conversation history
    messages = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye!")
                break
            
            messages.append(HumanMessage(content=user_input))
            
            test_state = {
                "messages": messages,
                "enable_background_investigation": False,
                "resources": [],
            }
            
            config = RunnableConfig(configurable={
                "enable_web_search": False,
                "enable_background_investigation": False,
                "enable_feedback_tool": False,
                "enable_added_tools": True,
            })
            
            print("\n🤖 Agent:\n")
            
            response_messages = []
            
            try:
                # Stream with events for tool visibility
                async for event in graph.astream_events(
                    test_state,
                    config=config,
                    version="v2",
                ):
                    event_type = event.get("event")
                    
                    # Tool call started
                    if event_type == "on_tool_start":
                        name = event.get("name", "unknown")
                        data = event.get("data", {})
                        inp = data.get("input", {})
                        print(f"\n  📤 TOOL CALL: {name}")
                        print(f"     Args: {str(inp)[:400]}")
                    
                    # Tool call finished
                    elif event_type == "on_tool_end":
                        name = event.get("name", "unknown")
                        data = event.get("data", {})
                        out = str(data.get("output", ""))[:600]
                        print(f"  📥 RESULT [{name}]: {out}")
                        print()
                    
                    # LLM streaming tokens
                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            print(chunk.content, end="", flush=True)
                    
                    # Capture final messages
                    elif event_type == "on_chain_end":
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            response_messages = output["messages"]
                
                # Update history
                if response_messages:
                    messages = response_messages
                    
            except Exception as e:
                print(f"\n❌ Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def main():
    print("\n" + "=" * 60)
    print("Starting Interactive Graph Test")
    print("=" * 60)
    
    try:
        asyncio.run(run_interactive_test())
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
