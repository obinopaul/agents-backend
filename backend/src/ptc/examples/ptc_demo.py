#!/usr/bin/env python3
"""PTC Module Demo Script.

This script demonstrates how to use the PTC (Programmatic Tool Calling) module
with a LangChain/LangGraph-based agent.

The PTC module provides:
- PTCSandbox: Execute Python code in a secure Daytona sandbox
- MCPRegistry: Connect to and discover tools from MCP servers
- Session/SessionManager: Manage conversation sessions with sandbox persistence
- AgentConfig: Configuration for LLM and infrastructure settings

Usage:
    1. Set environment variables:
       - DAYTONA_API_KEY: Your Daytona API key
       - ANTHROPIC_API_KEY or OPENAI_API_KEY: Your LLM API key
    
    2. Run the demo:
       python ptc_demo.py

Requirements:
    - langchain-anthropic or langchain-openai
    - daytona-sdk
    - See backend requirements.txt for full list
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def demo_basic_sandbox():
    """Demonstrate basic PTCSandbox usage for code execution."""
    from backend.src.ptc import PTCSandbox
    from backend.src.config.core import (
        CoreConfig,
        DaytonaConfig,
        FilesystemConfig,
        LoggingConfig,
        MCPConfig,
        SecurityConfig,
    )
    
    print("\n" + "=" * 60)
    print("Demo 1: Basic PTCSandbox Code Execution")
    print("=" * 60)
    
    # Create minimal config
    config = CoreConfig(
        daytona=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY", ""),
            base_url="https://app.daytona.io/api",
            snapshot_enabled=False,  # Disabled due to API bug
        ),
        security=SecurityConfig(),
        mcp=MCPConfig(servers=[]),
        logging=LoggingConfig(),
        filesystem=FilesystemConfig(),
    )
    
    # Validate API key
    config.validate_api_keys()
    
    # Create sandbox
    sandbox = PTCSandbox(config)
    
    try:
        # Initialize sandbox (creates Daytona workspace)
        print("\n[1] Initializing sandbox...")
        await sandbox.setup()
        print(f"    Sandbox ID: {sandbox.sandbox_id}")
        
        # Execute simple code
        print("\n[2] Executing Python code...")
        result = await sandbox.execute("""
import sys
print(f"Python version: {sys.version}")
print("Hello from the sandbox!")

# Do some computation
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
print(f"Sum of {numbers} = {total}")
""")
        
        print("\n[3] Execution Result:")
        print(f"    Success: {result.success}")
        print(f"    Output:\n      {result.output.replace(chr(10), chr(10) + '      ')}")
        
        if result.error:
            print(f"    Error: {result.error}")
            
    finally:
        # Cleanup
        print("\n[4] Cleaning up sandbox...")
        await sandbox.cleanup()
        print("    Done!")


async def demo_agent_config():
    """Demonstrate AgentConfig programmatic configuration."""
    from backend.src.ptc.config import AgentConfig
    from backend.src.config.core import MCPServerConfig
    
    print("\n" + "=" * 60)
    print("Demo 2: AgentConfig Programmatic Configuration")
    print("=" * 60)
    
    # Import LangChain chat model
    try:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-sonnet-4-20250514")
        print("\n[1] Using Claude Sonnet via LangChain")
    except ImportError:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4")
            print("\n[1] Using GPT-4 via LangChain")
        except ImportError:
            print("\n[ERROR] Neither langchain-anthropic nor langchain-openai installed.")
            print("        Run: pip install langchain-anthropic")
            return
    
    # Create config with optional MCP servers
    print("\n[2] Creating AgentConfig...")
    config = AgentConfig.create(
        llm=llm,
        # Optional: Add MCP servers for additional tools
        mcp_servers=[
            MCPServerConfig(
                name="filesystem",
                description="File system operations",
                command="npx",
                args=["-y", "@anthropics/mcp-server-filesystem@latest"],
                enabled=True,
            ),
        ],
        # Optional: Customize security settings
        max_execution_time=600,  # 10 minutes
    )
    
    print(f"    LLM: {config.llm.name}")
    print(f"    Daytona URL: {config.daytona.base_url}")
    print(f"    MCP Servers: {len(config.mcp.servers)}")
    
    # Convert to CoreConfig for PTCSandbox
    print("\n[3] Converting to CoreConfig for PTCSandbox...")
    core_config = config.to_core_config()
    print(f"    CoreConfig ready!")
    print(f"    Security max_execution_time: {core_config.security.max_execution_time}s")


async def demo_session_manager():
    """Demonstrate SessionManager for conversation management."""
    from backend.src.ptc import SessionManager
    from backend.src.config.core import (
        CoreConfig,
        DaytonaConfig,
        FilesystemConfig,
        LoggingConfig,
        MCPConfig,
        SecurityConfig,
    )
    
    print("\n" + "=" * 60)
    print("Demo 3: SessionManager for Conversation Sessions")
    print("=" * 60)
    
    config = CoreConfig(
        daytona=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY", ""),
            snapshot_enabled=False,  # Disabled due to API bug
        ),
        security=SecurityConfig(),
        mcp=MCPConfig(servers=[]),
        logging=LoggingConfig(),
        filesystem=FilesystemConfig(),
    )
    
    config.validate_api_keys()
    
    manager = SessionManager(config)
    
    try:
        # Create session for a conversation
        print("\n[1] Creating session for conversation 'demo-123'...")
        session = await manager.get_or_create_session("demo-123")
        print(f"    Session created!")
        print(f"    Sandbox ID: {session.sandbox.sandbox_id}")
        
        # Execute code within the session
        print("\n[2] Executing code in session...")
        result = await session.sandbox.execute("""
# Store state in the session
session_data = {"user": "demo", "counter": 0}
session_data["counter"] += 1
print(f"Session counter: {session_data['counter']}")
""")
        print(f"    Output: {result.output.strip()}")
        
        # Get existing session (reuses sandbox)
        print("\n[3] Reusing existing session...")
        same_session = await manager.get_or_create_session("demo-123")
        print(f"    Same sandbox: {session.sandbox.sandbox_id == same_session.sandbox.sandbox_id}")
        
    finally:
        # Cleanup all sessions
        print("\n[4] Cleaning up sessions...")
        await manager.cleanup_all()
        print("    Done!")


async def demo_mcp_integration():
    """Demonstrate MCP integration for tool discovery."""
    from backend.src.ptc import MCPRegistry, ToolFunctionGenerator
    from backend.src.config.core import (
        CoreConfig,
        DaytonaConfig,
        FilesystemConfig,
        LoggingConfig,
        MCPConfig,
        MCPServerConfig,
        SecurityConfig,
    )
    
    print("\n" + "=" * 60)
    print("Demo 4: MCP Integration (Tool Discovery)")
    print("=" * 60)
    print("\n[NOTE] This demo requires MCP servers to be running.")
    print("       It shows how tool discovery works, but won't")
    print("       actually connect to servers without proper setup.")
    
    # Create config with example MCP servers
    config = CoreConfig(
        daytona=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY", ""),
            snapshot_enabled=False,  # Disabled due to API bug
        ),
        security=SecurityConfig(),
        mcp=MCPConfig(
            servers=[
                MCPServerConfig(
                    name="tavily",
                    description="Web search capabilities",
                    command="npx",
                    args=["-y", "tavily-mcp@latest"],
                    env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
                    enabled=False,  # Disabled for demo
                ),
            ],
            tool_discovery_enabled=True,
        ),
        logging=LoggingConfig(),
        filesystem=FilesystemConfig(),
    )
    
    print("\n[1] MCP Configuration:")
    for server in config.mcp.servers:
        status = "enabled" if server.enabled else "disabled"
        print(f"    - {server.name}: {server.description} [{status}]")
    
    print("\n[2] MCPRegistry provides:")
    print("    - connect_all(): Connect to all configured MCP servers")
    print("    - get_all_tools(): Discover available tools")
    print("    - call_tool(): Execute tool calls")
    
    print("\n[3] ToolFunctionGenerator provides:")
    print("    - generate_tool_module(): Generate Python code for tools")
    print("    - generate_mcp_client_code(): Generate MCP client code")
    print("    - Enables PTC: agents write code to call tools!")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("PTC MODULE DEMO")
    print("Demonstrating Programmatic Tool Calling capabilities")
    print("=" * 60)
    
    # Check for required environment variables
    if not os.getenv("DAYTONA_API_KEY"):
        print("\n[WARNING] DAYTONA_API_KEY not set.")
        print("          Some demos require this to run.")
        print("          Get your key at: https://app.daytona.io")
    
    # Run demos
    try:
        # Demo 1: Basic sandbox (requires DAYTONA_API_KEY)
        if os.getenv("DAYTONA_API_KEY"):
            await demo_basic_sandbox()
        else:
            print("\n[SKIP] Demo 1 requires DAYTONA_API_KEY")
        
        # Demo 2: AgentConfig (no external deps)
        await demo_agent_config()
        
        # Demo 3: SessionManager (requires DAYTONA_API_KEY)
        if os.getenv("DAYTONA_API_KEY"):
            await demo_session_manager()
        else:
            print("\n[SKIP] Demo 3 requires DAYTONA_API_KEY")
        
        # Demo 4: MCP Integration (informational)
        await demo_mcp_integration()
        
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("DEMOS COMPLETE")
    print("=" * 60)
    print("\nFor more information, see:")
    print("  - backend/src/ptc/__init__.py (module documentation)")
    print("  - backend/src/ptc/config/ (configuration options)")
    print("  - backend/src/ptc/sandbox.py (PTCSandbox class)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
