# LangChain Integration Guide

This guide shows how to integrate the sandbox infrastructure with your LangChain-based agent.

---

## Overview

There are two ways to integrate:

1. **Direct Integration** - Create LangChain tools that talk to the sandbox
2. **MCP Integration** - Use the MCP server running inside the sandbox

We'll cover both approaches.

---

## Approach 1: Direct LangChain Tools

This approach creates LangChain tools that communicate directly with your sandbox server.

### Dependencies

```bash
pip install langchain langchain-openai httpx
```

### Create Sandbox Tools

Create `langchain_sandbox_tools.py`:

```python
"""LangChain tools for sandbox operations."""

import asyncio
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun

# Import your sandbox client
from sandbox_server.client import SandboxClient


# ============================================================
# PYDANTIC SCHEMAS FOR TOOL ARGUMENTS
# ============================================================

class RunCommandInput(BaseModel):
    command: str = Field(description="The shell command to run")
    background: bool = Field(
        default=False, 
        description="Run command in background"
    )


class WriteFileInput(BaseModel):
    path: str = Field(description="File path relative to workspace")
    content: str = Field(description="Content to write")


class ReadFileInput(BaseModel):
    path: str = Field(description="File path relative to workspace")


class SearchFilesInput(BaseModel):
    pattern: str = Field(description="Glob pattern to search for")
    path: str = Field(default=".", description="Directory to search in")


# ============================================================
# LANGCHAIN TOOLS
# ============================================================

class SandboxRunCommandTool(BaseTool):
    """Run shell commands in the sandbox."""
    
    name: str = "sandbox_run_command"
    description: str = """Run a shell command in the isolated sandbox environment.
Use this for:
- Running Python scripts
- Installing packages (pip install, npm install)
- Git operations
- File system operations (ls, mkdir, etc.)
- Any other shell command

The sandbox has Python 3.10, Node.js, and common dev tools installed."""

    args_schema: Type[BaseModel] = RunCommandInput
    
    # These will be set when tool is initialized
    sandbox_client: SandboxClient = None
    sandbox_id: str = None
    
    def _run(
        self, 
        command: str,
        background: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Sync wrapper for async operation."""
        return asyncio.run(self._arun(command, background))
    
    async def _arun(
        self, 
        command: str,
        background: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Run the command asynchronously."""
        try:
            output = await self.sandbox_client.run_command(
                self.sandbox_id,
                command,
                background=background
            )
            return output if output else "(no output)"
        except Exception as e:
            return f"Error running command: {str(e)}"


class SandboxWriteFileTool(BaseTool):
    """Write files in the sandbox."""
    
    name: str = "sandbox_write_file"
    description: str = """Write content to a file in the sandbox.
Creates parent directories if they don't exist.
Use for:
- Creating new source files
- Saving generated code
- Writing configuration files"""

    args_schema: Type[BaseModel] = WriteFileInput
    
    sandbox_client: SandboxClient = None
    sandbox_id: str = None
    
    def _run(
        self, 
        path: str,
        content: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return asyncio.run(self._arun(path, content))
    
    async def _arun(
        self, 
        path: str,
        content: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            await self.sandbox_client.write_file(
                self.sandbox_id, path, content
            )
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class SandboxReadFileTool(BaseTool):
    """Read files from the sandbox."""
    
    name: str = "sandbox_read_file"
    description: str = """Read the contents of a file from the sandbox.
Use for:
- Reading source code
- Checking file contents
- Reading command output files"""

    args_schema: Type[BaseModel] = ReadFileInput
    
    sandbox_client: SandboxClient = None
    sandbox_id: str = None
    
    def _run(
        self, 
        path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return asyncio.run(self._arun(path))
    
    async def _arun(
        self, 
        path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            content = await self.sandbox_client.read_file(
                self.sandbox_id, path
            )
            return content
        except Exception as e:
            return f"Error reading file: {str(e)}"


# ============================================================
# TOOL FACTORY
# ============================================================

def create_sandbox_tools(
    sandbox_client: SandboxClient,
    sandbox_id: str
) -> list[BaseTool]:
    """Create all sandbox tools with the given client and sandbox ID."""
    
    tools = []
    
    for ToolClass in [
        SandboxRunCommandTool,
        SandboxWriteFileTool,
        SandboxReadFileTool,
    ]:
        tool = ToolClass()
        tool.sandbox_client = sandbox_client
        tool.sandbox_id = sandbox_id
        tools.append(tool)
    
    return tools
```

### Use with LangChain Agent

```python
"""Example: LangChain agent with sandbox tools."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from sandbox_server.client import SandboxClient
from langchain_sandbox_tools import create_sandbox_tools


async def main():
    # 1. Create sandbox
    client = SandboxClient("http://localhost:8080")
    result = await client.create_sandbox(user_id="langchain_user")
    sandbox_id = result["sandbox_id"]
    
    print(f"Created sandbox: {sandbox_id}")
    print(f"VS Code: {result['vscode_url']}")
    
    try:
        # 2. Create tools
        tools = create_sandbox_tools(client, sandbox_id)
        
        # 3. Create agent
        llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a coding assistant with access to a secure sandbox environment.
You can run commands, write files, and read files in the sandbox.
The sandbox has Python 3.10, Node.js 20, and common dev tools installed.
Work in the /workspace directory.
Always explain what you're doing before executing commands."""
            ),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools,
            verbose=True,
            max_iterations=10
        )
        
        # 4. Run agent
        response = await agent_executor.ainvoke({
            "input": """Create a Python project with:
1. A main.py file that prints "Hello, Sandbox!"
2. A requirements.txt with requests library
3. Install the requirements
4. Run the main.py file
Show me the output."""
        })
        
        print("\n" + "="*50)
        print("Agent Response:")
        print(response["output"])
        
    finally:
        # 5. Cleanup
        await client.delete_sandbox(sandbox_id)
        print("\nSandbox deleted")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Approach 2: MCP Integration

The MCP server running inside the sandbox exposes tools via the Model Context Protocol. This is more dynamic - tools are discovered at runtime.

### Using langchain-mcp-adapters

```bash
pip install langchain-mcp-adapters
```

```python
"""LangChain agent using MCP tools from sandbox."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from sandbox_server.client import SandboxClient


async def main():
    # 1. Create sandbox
    client = SandboxClient("http://localhost:8080")
    result = await client.create_sandbox(user_id="mcp_user")
    
    sandbox_id = result["sandbox_id"]
    mcp_url = result["mcp_url"]
    
    print(f"Created sandbox: {sandbox_id}")
    print(f"MCP URL: {mcp_url}")
    
    try:
        # 2. Connect to MCP server in sandbox
        async with MultiServerMCPClient(
            {
                "sandbox": {
                    "transport": "sse",
                    "url": f"{mcp_url}/sse",
                }
            }
        ) as mcp_client:
            
            # 3. Get tools from MCP server
            tools = mcp_client.get_tools()
            print(f"Discovered {len(tools)} tools from sandbox MCP")
            
            # 4. Create agent with MCP tools
            llm = ChatOpenAI(model="gpt-4-turbo-preview")
            agent = create_react_agent(llm, tools)
            
            # 5. Run agent
            response = await agent.ainvoke({
                "messages": [
                    {
                        "role": "user",
                        "content": "Create a hello.py file and run it"
                    }
                ]
            })
            
            print(response["messages"][-1].content)
    
    finally:
        await client.delete_sandbox(sandbox_id)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Advanced: Session Manager

For production, you want to manage sandbox lifecycle properly:

```python
"""Sandbox session manager for LangChain agents."""

import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from sandbox_server.client import SandboxClient
from langchain_sandbox_tools import create_sandbox_tools


@dataclass
class SandboxSession:
    """Represents an active sandbox session."""
    sandbox_id: str
    user_id: str
    mcp_url: str
    vscode_url: str
    created_at: datetime
    last_activity: datetime
    tools: list


class SandboxSessionManager:
    """Manage sandbox sessions for users."""
    
    def __init__(
        self, 
        server_url: str,
        idle_timeout: int = 3600,  # 1 hour
    ):
        self.client = SandboxClient(server_url)
        self.sessions: Dict[str, SandboxSession] = {}
        self.idle_timeout = idle_timeout
    
    async def get_or_create_session(self, user_id: str) -> SandboxSession:
        """Get existing session or create new one."""
        
        # Check for existing session
        if user_id in self.sessions:
            session = self.sessions[user_id]
            session.last_activity = datetime.utcnow()
            return session
        
        # Create new sandbox
        result = await self.client.create_sandbox(user_id=user_id)
        
        # Create tools
        tools = create_sandbox_tools(
            self.client, 
            result["sandbox_id"]
        )
        
        # Create session
        now = datetime.utcnow()
        session = SandboxSession(
            sandbox_id=result["sandbox_id"],
            user_id=user_id,
            mcp_url=result["mcp_url"],
            vscode_url=result["vscode_url"],
            created_at=now,
            last_activity=now,
            tools=tools
        )
        
        self.sessions[user_id] = session
        return session
    
    async def end_session(self, user_id: str):
        """End a user's session."""
        if user_id not in self.sessions:
            return
        
        session = self.sessions.pop(user_id)
        await self.client.delete_sandbox(session.sandbox_id)
    
    async def cleanup_idle_sessions(self):
        """Cleanup sessions that have been idle too long."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.idle_timeout)
        
        idle_users = [
            user_id 
            for user_id, session in self.sessions.items()
            if session.last_activity < cutoff
        ]
        
        for user_id in idle_users:
            await self.end_session(user_id)
        
        return len(idle_users)
    
    async def cleanup_all(self):
        """Cleanup all sessions."""
        for user_id in list(self.sessions.keys()):
            await self.end_session(user_id)


# Usage example
async def agent_with_session():
    manager = SandboxSessionManager("http://localhost:8080")
    
    try:
        # Get session (creates sandbox if needed)
        session = await manager.get_or_create_session("user123")
        
        print(f"Sandbox: {session.sandbox_id}")
        print(f"VS Code: {session.vscode_url}")
        
        # Use session.tools with your LangChain agent
        # ...
        
    finally:
        await manager.cleanup_all()
```

---

## Integration with LangGraph

For more complex workflows, use LangGraph with sandbox tools:

```python
"""LangGraph workflow with sandbox tools."""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage

from sandbox_server.client import SandboxClient
from langchain_sandbox_tools import create_sandbox_tools


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "Chat history"]
    sandbox_id: str
    vscode_url: str


async def create_sandbox_graph(sandbox_server_url: str):
    """Create a LangGraph workflow with sandbox tools."""
    
    # Create sandbox
    client = SandboxClient(sandbox_server_url)
    result = await client.create_sandbox(user_id="langgraph_user")
    
    # Create tools
    tools = create_sandbox_tools(client, result["sandbox_id"])
    
    # Create LLM
    llm = ChatOpenAI(model="gpt-4-turbo-preview")
    llm_with_tools = llm.bind_tools(tools)
    
    # Define nodes
    def agent(state: AgentState):
        """The agent decides what to do."""
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
    
    def should_continue(state: AgentState):
        """Check if we should continue or end."""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END
    
    # Build graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent)
    workflow.add_node("tools", ToolNode(tools))
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    
    workflow.add_edge("tools", "agent")
    
    graph = workflow.compile()
    
    # Return graph with sandbox info
    return graph, result["sandbox_id"], result["vscode_url"], client


async def main():
    graph, sandbox_id, vscode_url, client = await create_sandbox_graph(
        "http://localhost:8080"
    )
    
    print(f"VS Code: {vscode_url}")
    
    try:
        result = await graph.ainvoke({
            "messages": [
                HumanMessage(content="Create a Flask hello world app and run it")
            ],
            "sandbox_id": sandbox_id,
            "vscode_url": vscode_url
        })
        
        for message in result["messages"]:
            print(message.content)
    
    finally:
        await client.delete_sandbox(sandbox_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Best Practices

### 1. Always Clean Up

```python
try:
    # Use sandbox
    pass
finally:
    await client.delete_sandbox(sandbox_id)
```

### 2. Handle Timeouts

```python
class SandboxRunCommandTool(BaseTool):
    timeout: int = 60
    
    async def _arun(self, command: str, ...):
        try:
            return await asyncio.wait_for(
                self.sandbox_client.run_command(...),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            return "Command timed out"
```

### 3. Provide Good Tool Descriptions

```python
description = """Run a shell command in the sandbox.
Available tools: Python 3.10, Node.js 20, pip, npm, git, curl, wget
Working directory: /workspace
Max runtime: 60 seconds

Examples:
- python script.py
- pip install requests
- npm install express
- git clone <url>"""
```

### 4. Limit Command Scope

```python
BLOCKED_COMMANDS = ["rm -rf /", "shutdown", "reboot"]

async def _arun(self, command: str, ...):
    for blocked in BLOCKED_COMMANDS:
        if blocked in command:
            return f"Command blocked: {blocked}"
    # ... execute
```

---

## Summary

You now have two integration paths:

1. **Direct Tools** - More control, works with any LangChain agent
2. **MCP Tools** - Dynamic discovery, tools defined in sandbox

Both approaches work with:
- Standard LangChain agents
- LangGraph workflows
- Custom agent implementations

The sandbox provides:
- Isolated code execution
- VS Code in browser
- MCP tool server
- File system access
- Network isolation

Your agent can now safely execute code without affecting your host system!
