#!/usr/bin/env python3
"""Robust LangGraph Agent with PTC Integration - Interactive CLI.

A production-ready interactive CLI agent that uses the PTC (Programmatic Tool Calling)
pattern with proper agentic loops and persistent sandbox sessions.

Key Features:
- Interactive CLI: Continue conversation in the same session
- Persistent Sandbox: Keep building, the sandbox persists your work
- Web Preview Link: See what the agent is building in your browser
- Full Toolkit: bash, file operations, glob, grep, code execution
- ReAct Pattern: Agent observes, thinks, acts, repeats until done

Usage:
    cd backend
    python -m src.ptc.examples.langgraph_robust_agent

    Then interact:
    > Create a Next.js app with shadcn/ui
    > Add a dark mode toggle
    > Show me the preview link
    > exit (to quit)

Environment Variables:
    OPENAI_API_KEY: Your OpenAI API key
    DAYTONA_API_KEY: Your Daytona API key
"""

import asyncio
import os
import sys
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
load_dotenv()


# =============================================================================
# Step 1: Import PTC Module and Tools
# =============================================================================

from backend.src.ptc import PTCSandbox, MCPRegistry
from backend.src.config.core import (
    CoreConfig,
    DaytonaConfig,
    FilesystemConfig,
    LoggingConfig,
    MCPConfig,
    SecurityConfig,
)

# Import tool factories
from backend.src.tools.bash import create_execute_bash_tool
from backend.src.tools.file_ops import create_filesystem_tools
from backend.src.tools.glob import create_glob_tool
from backend.src.tools.grep import create_grep_tool
from backend.src.tools.code_execution import create_execute_code_tool


# =============================================================================
# Step 2: System Prompt for PTC Agent
# =============================================================================

SYSTEM_PROMPT = """You are an expert software engineer with access to a Daytona cloud sandbox.

## Your Capabilities

You can execute code and commands in a secure, persistent sandbox environment:
- **execute_code**: Run Python code (for complex operations, data processing, MCP tools)
- **Bash**: Run shell commands (git, npm, npx, docker, system commands)
- **read_file**: Read file contents with line numbers
- **write_file**: Create or overwrite files
- **edit_file**: Make targeted edits to existing files
- **glob**: Find files matching patterns (e.g., "**/*.py")
- **grep**: Search file contents with regex

## Working Directory

Your sandbox working directory is `/home/daytona`. All files persist across conversations.

## Best Practices

1. **Iterate and verify**: After changes, check they work
2. **Use appropriate tools**: 
   - Use `write_file` for new files
   - Use `edit_file` for modifications
   - Use `Bash` for git, npm, npx, and system commands
   - Use `execute_code` for Python with MCP tools
3. **Handle errors**: If something fails, fix it
4. **Show results**: Print outputs, summarize what you did
5. **Complete tasks**: Keep working until fully done

## Web Applications

When building web applications:
1. Create the project with npx/npm (e.g., `npx create-next-app@latest`)
2. Install dependencies with npm
3. Start dev server (e.g., `npm run dev` in background)
4. The sandbox provides a web preview URL

## Important Commands

- Start a dev server in background: Use `run_in_background=True`
- View running processes: `ps aux | grep node`
- Kill process: `kill -9 <pid>`

Remember: You have full control. Build complex applications iteratively!
"""


# =============================================================================
# Step 3: Create All Sandbox Tools
# =============================================================================

def create_all_tools(sandbox: PTCSandbox, mcp_registry: MCPRegistry | None) -> list[BaseTool]:
    """Create all sandbox tools."""
    tools: list[BaseTool] = []
    
    if mcp_registry:
        tools.append(create_execute_code_tool(sandbox, mcp_registry))
    
    tools.append(create_execute_bash_tool(sandbox))
    
    read_file, write_file, edit_file = create_filesystem_tools(sandbox)
    tools.extend([read_file, write_file, edit_file])
    
    tools.append(create_glob_tool(sandbox))
    tools.append(create_grep_tool(sandbox))
    
    return tools


# =============================================================================
# Step 4: Create PTC Config
# =============================================================================

def create_ptc_config() -> CoreConfig:
    """Create configuration for PTC module."""
    return CoreConfig(
        daytona=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY", ""),
            base_url="https://app.daytona.io/api",
            python_version="3.12",
            snapshot_enabled=False,  # Disabled due to Daytona API bug
        ),
        security=SecurityConfig(
            max_execution_time=600,
            max_code_length=50000,
        ),
        mcp=MCPConfig(servers=[]),
        logging=LoggingConfig(level="INFO"),
        filesystem=FilesystemConfig(),
    )


# =============================================================================
# Step 5: Build LangGraph Agent with Memory
# =============================================================================

def build_react_agent(llm: ChatOpenAI, tools: list[BaseTool], checkpointer: Any = None):
    """Build a LangGraph agent with ReAct pattern and memory."""
    from langgraph.prebuilt import create_react_agent
    
    # Use 'prompt' parameter instead of deprecated 'state_modifier'
    agent = create_react_agent(
        llm,
        tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    return agent


# =============================================================================
# Step 6: Interactive CLI
# =============================================================================

def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 70)
    print("  PTC AGENT - Interactive CLI")
    print("  Programmatic Tool Calling with Daytona Sandbox")
    print("=" * 70)


def print_help():
    """Print help message."""
    print("""
Commands:
  > [your request]  - Ask the agent to do something
  > help            - Show this help
  > clear           - Clear screen
  > status          - Show sandbox status and links
  > files           - List files in sandbox
  > exit            - Exit the CLI (sandbox is preserved)

Examples:
  > Create a Python script that generates random ASCII art
  > Build a simple Flask API with a /hello endpoint
  > Create an HTML page with CSS and show me the contents
  > npm init -y and create a basic Node.js server
""")


async def run_interactive_cli():
    """Run the interactive CLI agent."""
    
    print_banner()
    
    # Validate environment
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ OPENAI_API_KEY not set!")
        print("   Set it in your .env file or environment")
        return
    
    if not os.getenv("DAYTONA_API_KEY"):
        print("\n❌ DAYTONA_API_KEY not set!")
        print("   Get your key at: https://app.daytona.io")
        return
    
    # Create PTC config and sandbox
    print("\n🔧 Initializing...")
    config = create_ptc_config()
    config.validate_api_keys()
    
    sandbox = PTCSandbox(config)
    mcp_registry = None
    
    try:
        # Initialize sandbox
        print("   Creating Daytona sandbox...")
        await sandbox.setup()
        print(f"   ✓ Sandbox ID: {sandbox.sandbox_id}")
        
        # Get web preview URL
        preview_url = None
        if hasattr(sandbox, 'sandbox') and hasattr(sandbox.sandbox, 'get_preview_link'):
            try:
                # Try to get preview link from Daytona
                preview_url = sandbox.sandbox.get_preview_link(8000)
                print(f"   ✓ Web Preview (port 8000): {preview_url}")
            except Exception:
                pass
        
        if not preview_url:
            print("   ℹ Web Preview: Start a server on port 8000 to get a link")
        
        # Create tools
        print("   Creating sandbox tools...")
        tools = create_all_tools(sandbox, mcp_registry)
        tool_names = [t.name for t in tools]
        print(f"   ✓ Tools: {', '.join(tool_names)}")
        
        # Create LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Create memory for conversation persistence
        checkpointer = MemorySaver()
        
        # Build agent with memory
        agent = build_react_agent(llm, tools, checkpointer)
        print("   ✓ Agent ready with memory")
        
        # Session config for conversation persistence
        session_config = {"configurable": {"thread_id": "ptc-session-1"}}
        
        print("\n" + "=" * 70)
        print("Ready! Type 'help' for commands or just ask me to build something.")
        print("=" * 70)
        
        # Message history for display
        conversation_count = 0
        
        while True:
            try:
                # Get user input
                print()
                user_input = input("You > ").strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() == 'exit':
                    print("\n👋 Goodbye! Your sandbox is preserved.")
                    print(f"   Sandbox ID: {sandbox.sandbox_id}")
                    break
                
                elif user_input.lower() == 'help':
                    print_help()
                    continue
                
                elif user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print_banner()
                    continue
                
                elif user_input.lower() == 'status':
                    print(f"\n📊 Sandbox Status")
                    print(f"   ID: {sandbox.sandbox_id}")
                    print(f"   Working Dir: /home/daytona")
                    if hasattr(sandbox, 'sandbox') and hasattr(sandbox.sandbox, 'get_preview_link'):
                        try:
                            for port in [3000, 5000, 8000, 8080]:
                                url = sandbox.sandbox.get_preview_link(port)
                                print(f"   Preview (port {port}): {url}")
                        except Exception:
                            print("   Preview: Start a server to get a link")
                    continue
                
                elif user_input.lower() == 'files':
                    print("\n📁 Files in sandbox:")
                    try:
                        result = await sandbox.execute_bash_command("ls -la /home/daytona", timeout=30)
                        if result.get("success"):
                            print(result.get("stdout", ""))
                        else:
                            print("   (empty or error)")
                    except Exception as e:
                        print(f"   Error: {e}")
                    continue
                
                # Run agent with user request
                conversation_count += 1
                print(f"\n🤖 Agent (thinking...)")
                
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config={**session_config, "recursion_limit": 50},
                )
                
                # Display results
                messages = result.get("messages", [])
                
                # Count tool calls
                tool_calls = sum(1 for m in messages if isinstance(m, ToolMessage))
                
                # Get final AI response
                ai_messages = [m for m in messages if isinstance(m, AIMessage) and m.content and not m.tool_calls]
                
                if ai_messages:
                    final_response = ai_messages[-1].content
                    print(f"\n🤖 Agent ({tool_calls} tool calls):")
                    print("-" * 50)
                    print(final_response)
                else:
                    # Show last few tool results if no final response
                    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
                    if tool_msgs:
                        print(f"\n🔧 Completed {len(tool_msgs)} operations")
                        last_tool = tool_msgs[-1]
                        if hasattr(last_tool, 'content'):
                            content = last_tool.content[:500]
                            if len(last_tool.content) > 500:
                                content += "..."
                            print(f"   Last result: {content}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Type 'exit' to quit properly.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup sandbox
        print("\n🧹 Cleaning up sandbox...")
        try:
            await sandbox.cleanup()
            print("   ✓ Done!")
        except Exception:
            print("   (cleanup skipped)")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    try:
        asyncio.run(run_interactive_cli())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
