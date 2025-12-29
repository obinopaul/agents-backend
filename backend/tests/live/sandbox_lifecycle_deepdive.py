#!/usr/bin/env python3
"""
================================================================================
SANDBOX LIFECYCLE DEEP DIVE - Step-by-Step Annotated Test
================================================================================

Author: Paul (agents-backend project)
Purpose: This file demonstrates the COMPLETE lifecycle of how the sandbox
         system works, step-by-step, with detailed annotations mapping each
         step to the actual code in the project.

HOW TO RUN:
    1. Make sure Docker is running (for Redis, PostgreSQL)
    2. Start the backend: docker-compose up -d --build
    3. Run this test: python backend/tests/live/sandbox_lifecycle_deepdive.py

================================================================================
HIGH-LEVEL LIFECYCLE OVERVIEW (10 STEPS)
================================================================================

When you deploy this to the cloud and build your chatbot frontend, here's 
EXACTLY what happens, step-by-step:

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: BACKEND STARTUP (Before any user connects)                          │
│                                                                              │
│ When you run `docker-compose up`, the FastAPI backend starts.               │
│ During startup, the backend initializes the SandboxController.              │
│ NO E2B sandboxes are created yet - the system is just "ready".              │
│                                                                              │
│ Code Location:                                                               │
│   - backend/src/sandbox/sandbox_server/main.py → lifespan() function        │
│   - backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py      │
│                                                                              │
│ What happens:                                                                │
│   1. PostgreSQL tables created (sandboxes table)                             │
│   2. SandboxController instantiated with config                              │
│   3. Redis queue consumer started (for timeout management)                   │
│   4. Server listens on port 8000                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: USER STARTS CHAT SESSION (Frontend connects)                        │
│                                                                              │
│ When a user opens your chatbot frontend and starts a conversation,          │
│ the frontend calls your backend API to initialize the session.              │
│                                                                              │
│ Code Location:                                                               │
│   - backend/app/agent/api/v1/chat.py → chat endpoints                        │
│   - This test simulates this by calling the sandbox create endpoint         │
│                                                                              │
│ What happens:                                                                │
│   1. Frontend authenticates (gets JWT token)                                 │
│   2. Frontend sends chat request with user message                           │
│   3. Backend decides: "This user needs a sandbox"                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: SANDBOX GET OR CREATE (Session-based reuse - II-Agent pattern)      │
│                                                                              │
│ The backend FIRST checks if this session already has a sandbox.             │
│ If yes, connect to it. If no, create a new one and link it.                 │
│ This is where the actual cloud VM is spun up (if needed).                   │
│                                                                              │
│ Code Location:                                                               │
│   - backend/src/services/sandbox_service.py → get_or_create_sandbox()       │
│   - backend/src/sandbox/sandbox_server/db/manager.py                        │
│     → get_sandbox_for_session() & update_session_sandbox()                  │
│   - backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py      │
│     → create_sandbox() or connect()                                          │
│   - backend/src/sandbox/sandbox_server/sandboxes/e2b.py → E2BSandbox.create()│
│                                                                              │
│ What happens (II-Agent pattern - now implemented!):                          │
│   1. SandboxService.get_or_create_sandbox(user_id, session_id) called        │
│   2. IF session already has sandbox:                                         │
│      → Get sandbox_id from SessionMetrics.sandbox_id                         │
│      → Check if sandbox is still running in Sandbox table                    │
│      → Connect to existing sandbox (saves ~30-60s!)                          │
│   3. ELSE (no existing sandbox):                                             │
│      → SandboxController.create_sandbox() creates new E2B VM                 │
│      → E2BSandbox.create() calls E2B API to spin up cloud VM                 │
│      → Sandbox ID stored in PostgreSQL (Sandbox table)                       │
│      → Session linked to sandbox (SessionMetrics.sandbox_id updated)         │
│      → start-services.sh runs inside sandbox (starts MCP server)             │
│   4. MCP credentials written if user has saved settings                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: MCP SERVER STARTS INSIDE SANDBOX                                    │
│                                                                              │
│ When the E2B sandbox is created, start-services.sh runs automatically.      │
│ This script starts the MCP Tool Server on port 6060.                         │
│                                                                              │
│ Code Location (inside E2B template):                                         │
│   - backend/docker/sandbox/start-services.sh                                 │
│   - The MCP server: backend/src/tool_server/mcp/server.py                    │
│                                                                              │
│ What happens inside the sandbox:                                             │
│   1. tmux session created: mcp-server-system-never-kill                      │
│   2. Python MCP server starts on port 6060                                   │
│   3. All 40+ tools registered (shell, file, browser, web, media)             │
│   4. Health endpoint available at https://6060-{sandbox-id}.e2b.app/health   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: WAIT FOR MCP SERVER TO BE READY                                     │
│                                                                              │
│ The MCP server takes a few seconds to fully initialize.                     │
│ We poll the /health endpoint until it responds.                             │
│                                                                              │
│ Code Location:                                                               │
│   - This test file → _wait_for_mcp_server()                                  │
│   - In production: your chat endpoint would do this                          │
│                                                                              │
│ What happens:                                                                │
│   1. Poll https://6060-{sandbox-id}.e2b.app/health                           │
│   2. Retry every 5 seconds until 200 OK                                      │
│   3. Once ready, MCP tools are accessible                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: GET LANGCHAIN TOOLS VIA MCP                                         │
│                                                                              │
│ Now that MCP server is running, we connect to it using                      │
│ langchain-mcp-adapters to get LangChain-compatible tools.                   │
│                                                                              │
│ Code Location:                                                               │
│   - langchain_mcp_adapters.client.MultiServerMCPClient                       │
│   - The tools come from: backend/src/tool_server/tools/*                     │
│                                                                              │
│ What happens:                                                                │
│   1. Create MultiServerMCPClient pointing to sandbox MCP URL                 │
│   2. Call client.get_tools() to fetch all available tools                    │
│   3. Tools returned as LangChain Tool objects                                │
│   4. Example tools: shell_run_command, file_read, browser_navigate           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: INITIALIZE LLM                                                       │
│                                                                              │
│ Get an LLM instance using the project's get_llm() helper.                   │
│ This reads from your .env configuration.                                     │
│                                                                              │
│ Code Location:                                                               │
│   - backend/src/llms/llm.py → get_llm()                                       │
│                                                                              │
│ What happens:                                                                │
│   1. Reads LLM_PROVIDER from .env (openai, anthropic, etc.)                   │
│   2. Creates appropriate LangChain ChatModel                                  │
│   3. Returns configured LLM ready for agent use                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 8: CREATE LANGGRAPH AGENT                                               │
│                                                                              │
│ Combine the LLM and MCP tools into a LangGraph ReAct agent.                 │
│ This agent can now reason and use tools.                                     │
│                                                                              │
│ Code Location:                                                               │
│   - langgraph.prebuilt.create_react_agent                                    │
│   - In production: backend/src/graph/builder.py (more sophisticated)         │
│                                                                              │
│ What happens:                                                                │
│   1. create_react_agent(llm, tools) creates the agent                        │
│   2. Agent has reasoning loop: think → act → observe → repeat               │
│   3. Agent is ready to process user messages                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 9: AGENT PROCESSES USER MESSAGE                                         │
│                                                                              │
│ The agent receives the user's message and starts reasoning.                 │
│ It may call tools (which execute in the E2B sandbox).                       │
│                                                                              │
│ Code Location:                                                               │
│   - agent.ainvoke({"messages": [...]})                                        │
│   - Tools execute via MCP → tool_server inside sandbox                       │
│                                                                              │
│ What happens:                                                                │
│   1. Agent receives: "Create a hello world Python file"                      │
│   2. Agent reasons: "I need to write a file"                                 │
│   3. Agent calls tool: file_write(path="/workspace/hello.py", content="...") │
│   4. MCP server receives request, executes in sandbox                        │
│   5. Tool result returned to agent                                           │
│   6. Agent responds: "I've created hello.py for you"                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 10: CLEANUP (Session ends)                                              │
│                                                                              │
│ When the user leaves or session times out, sandbox is deleted.              │
│                                                                              │
│ Code Location:                                                               │
│   - backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py      │
│     → delete_sandbox()                                                        │
│   - Automatic via Redis queue timeout                                        │
│                                                                              │
│ What happens:                                                                │
│   1. Redis queue triggers "pause" action after idle timeout                  │
│   2. If still idle, E2B hard timeout kills sandbox                           │
│   3. Sandbox removed from PostgreSQL                                         │
│   4. Cloud resources freed                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
NOW LET'S IMPLEMENT EACH STEP WITH CODE
================================================================================
"""

import asyncio
import sys
import os
import uuid
import httpx
from datetime import datetime
from typing import List, Optional

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.getcwd())

# LangChain/LangGraph imports
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage


# =============================================================================
# CONFIGURATION
# =============================================================================
# These would come from your .env in production

BASE_URL = "http://127.0.0.1:8000"  # Your FastAPI backend
TEST_USER = "sandbox_test"           # Test user (create with create_test_user.py)
TEST_PASSWORD = "TestPass123!"       # Test password


# =============================================================================
# STEP-BY-STEP IMPLEMENTATION
# =============================================================================

class SandboxLifecycleDeepDive:
    """
    This class walks through the COMPLETE sandbox lifecycle step-by-step.
    Each method corresponds to one of the 10 steps outlined above.
    """
    
    def __init__(self):
        # State that will be populated as we go through the lifecycle
        self.http_client: Optional[httpx.AsyncClient] = None
        self.jwt_token: Optional[str] = None
        self.sandbox_id: Optional[str] = None
        self.mcp_url: Optional[str] = None
        self.mcp_client = None
        self.langchain_tools: List = []
        self.llm = None
        self.agent = None
    
    # =========================================================================
    # STEP 1: Backend is Already Running
    # =========================================================================
    # NOTE: This step happens BEFORE this test runs.
    # When you run `docker-compose up -d --build`, the backend starts.
    # 
    # What happens in the backend during startup:
    #   File: backend/src/sandbox/sandbox_server/main.py
    #   
    #   @asynccontextmanager
    #   async def lifespan(app: FastAPI):
    #       global sandbox_controller
    #       await init_database()  # Create PostgreSQL tables
    #       config = SandboxConfig()
    #       sandbox_controller = SandboxController(config)  # <-- KEY LINE
    #       await sandbox_controller.start()  # Starts Redis queue consumer
    #       yield
    #       await sandbox_controller.shutdown()
    #
    # At this point:
    #   ✅ PostgreSQL ready with 'sandboxes' table
    #   ✅ SandboxController instantiated
    #   ✅ Redis queue consumer listening
    #   ❌ NO E2B sandboxes created yet (lazy creation)
    # =========================================================================
    
    async def step_1_verify_backend_running(self):
        """
        STEP 1: Verify the backend is running and ready.
        
        In production: Your frontend would call the health endpoint first.
        
        Code locations involved:
          - backend/main.py → the main FastAPI app
          - backend/src/sandbox/sandbox_server/main.py → sandbox server (embedded)
        """
        print("\n" + "="*70)
        print("STEP 1: VERIFY BACKEND IS RUNNING")
        print("="*70)
        print("""
        What's happening behind the scenes:
        -----------------------------------
        When docker-compose started the backend, it ran:
        
            SandboxController(config)  # from lifecycle/sandbox_controller.py
            await sandbox_controller.start()
        
        This initialized:
          - PostgreSQL connection (for sandbox state)
          - Redis queue (for timeout management)
          - SandboxFactory (for E2B/Daytona provider selection)
        
        But NO E2B sandboxes exist yet. The system is just "ready".
        """)
        
        # Create HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=180.0,
            headers={
                'User-Agent': 'SandboxLifecycleTest/1.0',
                'X-Request-ID': str(uuid.uuid4()),
                'Content-Type': 'application/json'
            }
        )
        
        # Check backend health
        try:
            response = await self.http_client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                print("✅ Backend is running and healthy")
                print(f"   URL: {BASE_URL}")
                print(f"   Version: {health_data.get('version', 'N/A')}")
                print(f"   Service: {health_data.get('service', 'N/A')}")
                return True
            else:
                print(f"❌ Backend returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to backend: {e}")
            print("   Make sure to run: docker-compose up -d --build")
            return False
    
    # =========================================================================
    # STEP 2: User Authentication
    # =========================================================================
    
    async def step_2_user_authentication(self):
        """
        STEP 2: Authenticate as a user.
        
        In production: Your frontend would call this after user logs in.
        
        Code locations involved:
          - backend/app/agent/api/v1/auth.py → authentication endpoints
          - JWT token generation and validation
        """
        print("\n" + "="*70)
        print("STEP 2: USER AUTHENTICATION")
        print("="*70)
        print("""
        What's happening:
        -----------------
        In your chatbot frontend, users log in with their credentials.
        The backend returns a JWT token that must be included in all
        subsequent requests.
        
        This token identifies the user and their permissions.
        The sandbox will be created FOR this specific user.
        """)
        
        # Login to get JWT token
        response = await self.http_client.post(
            f'{BASE_URL}/api/v1/auth/login/swagger',
            params={'username': TEST_USER, 'password': TEST_PASSWORD}
        )
        
        if response.status_code == 200:
            self.jwt_token = response.json().get('access_token')
            self.http_client.headers['Authorization'] = f'Bearer {self.jwt_token}'
            print(f"✅ Authenticated as: {TEST_USER}")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
            print("   Run: python backend/tests/live/create_test_user.py")
            return False
    
    # =========================================================================
    # STEP 3: Create E2B Sandbox (The Key Step!)
    # =========================================================================
    
    async def step_3_create_sandbox(self):
        """
        STEP 3: Create an E2B sandbox for this user's session.
        
        THIS IS THE KEY STEP where the E2B cloud VM is created.
        
        Code locations involved (trace the call chain):
        
          1. HTTP Request hits:
             backend/src/sandbox/sandbox_server/main.py
             → POST /sandboxes/create endpoint
        
          2. Which calls:
             SandboxController.create_sandbox(user_id)
             File: backend/src/sandbox/sandbox_server/lifecycle/sandbox_controller.py
        
          3. Which calls:
             E2BSandbox.create(config, queue, sandbox_id, metadata, template_id)
             File: backend/src/sandbox/sandbox_server/sandboxes/e2b.py
        
          4. E2BSandbox.create() does:
             - AsyncSandbox.create(template_id)  # E2B API call to spin up VM
             - sandbox.commands.run("bash /app/start-services.sh &")  # Start MCP
             - Store sandbox info in PostgreSQL
        
        After this step:
          ✅ E2B cloud VM is running
          ✅ start-services.sh has been triggered
          ✅ MCP server is starting on port 6060
          ✅ Sandbox ID stored in PostgreSQL
        """
        print("\n" + "="*70)
        print("STEP 3: CREATE E2B SANDBOX")
        print("="*70)
        print("""
        What's happening:
        -----------------
        This is where the ACTUAL E2B cloud VM is created.
        
        Call chain:
          HTTP POST /sandboxes/create
              ↓
          SandboxController.create_sandbox()  
              ↓  (lifecycle/sandbox_controller.py)
          E2BSandbox.create()
              ↓  (sandboxes/e2b.py)
          AsyncSandbox.create(template_id)   # E2B API
              ↓
          sandbox.commands.run("bash /app/start-services.sh &")
        
        The start-services.sh script (inside the E2B template) runs:
          - MCP Tool Server on port 6060
          - code-server (VS Code) on port 9000
        
        This typically takes 30-60 seconds...
        """)
        
        print("\n   ⏳ Creating E2B sandbox (this takes ~30-60 seconds)...")
        start_time = datetime.now()
        
        response = await self.http_client.post(
            f'{BASE_URL}/agent/sandboxes/sandboxes/create',
            json={'user_id': 'lifecycle-deepdive-test'}
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if response.status_code == 200:
            data = response.json().get('data', {})
            self.sandbox_id = data.get('sandbox_id')
            self.mcp_url = data.get('mcp_url')
            
            print(f"\n✅ Sandbox created in {elapsed:.1f} seconds!")
            print(f"   Sandbox ID: {self.sandbox_id}")
            print(f"   MCP URL: {self.mcp_url}")
            print(f"   VSCode URL: {data.get('vscode_url', 'N/A')}")
            print("""
        What was created:
        -----------------
          • E2B cloud VM (Ubuntu + Python 3.12 + Node.js 24)
          • MCP Tool Server starting on port 6060
          • code-server (VS Code IDE) on port 9000
          • Workspace at /workspace
          • All 40+ tools available
            """)
            return True
        else:
            print(f"❌ Sandbox creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    # =========================================================================
    # STEP 4 & 5: Wait for MCP Server
    # =========================================================================
    
    async def step_4_5_wait_for_mcp_server(self, max_wait_seconds=90):
        """
        STEPS 4-5: Wait for MCP server to be ready inside the sandbox.
        
        The MCP server takes a few seconds to fully initialize after
        start-services.sh runs.
        
        What's happening inside the sandbox:
        
          File: backend/docker/sandbox/start-services.sh
          
          #!/bin/bash
          # Start MCP server in tmux (so it persists)
          tmux new-session -d -s mcp-server-system-never-kill \
              "PYTHONPATH=/app/agents_backend/src \
               python -m tool_server.mcp.server --port 6060"
        
          # Start code-server
          tmux new-session -d -s code-server-system-never-kill \
              "code-server --port 9000 --auth none /workspace"
        
        The MCP server (tool_server/mcp/server.py) then:
          1. Registers all tools from tool_server/tools/*
          2. Exposes /health endpoint
          3. Exposes /mcp endpoint for LangChain MCP adapters
          4. Exposes /credential endpoint for auth setup
        """
        print("\n" + "="*70)
        print("STEPS 4-5: WAIT FOR MCP SERVER TO BE READY")
        print("="*70)
        print("""
        What's happening inside the sandbox:
        ------------------------------------
        The start-services.sh script started these services:
        
          1. MCP Tool Server (port 6060)
             - Runs: python -m tool_server.mcp.server
             - Registers 40+ tools
             - Exposes /health, /mcp, /credential endpoints
        
          2. code-server (port 9000)
             - VS Code in browser
             - Access: https://9000-{sandbox-id}.e2b.app
        
        We poll /health until the MCP server is ready...
        """)
        
        start = datetime.now()
        attempt = 0
        
        while (datetime.now() - start).seconds < max_wait_seconds:
            attempt += 1
            try:
                health_url = f"{self.mcp_url}/health"
                response = await self.http_client.get(health_url, timeout=10.0)
                if response.status_code == 200:
                    elapsed = (datetime.now() - start).seconds
                    print(f"\n✅ MCP server is ready! (attempt {attempt}, {elapsed}s)")
                    print(f"   Health endpoint: {health_url}")
                    return True
            except Exception:
                pass
            
            elapsed = (datetime.now() - start).seconds
            print(f"   ⏳ Waiting for MCP server... ({elapsed}s / {max_wait_seconds}s)")
            await asyncio.sleep(5)
        
        print(f"❌ MCP server did not become ready within {max_wait_seconds}s")
        return False
    
    # =========================================================================
    # STEP 6: Get LangChain Tools via MCP
    # =========================================================================
    
    async def step_6_get_langchain_tools(self):
        """
        STEP 6: Connect to MCP server and get LangChain-compatible tools.
        
        This uses the langchain-mcp-adapters package to connect to
        the MCP server and convert MCP tools to LangChain Tools.
        
        Code locations involved:
          - langchain_mcp_adapters.client.MultiServerMCPClient
          - The actual tools: backend/src/tool_server/tools/*
            - tools/shell/ → shell_run_command, shell_view, etc.
            - tools/file_system/ → file_read, file_write, etc.
            - tools/browser/ → browser_navigate, browser_click, etc.
            - tools/web/ → web_search, web_visit, etc.
            - tools/media/ → image_generate, video_generate
        
        After this step:
          ✅ We have LangChain Tool objects
          ✅ Each tool can be called and will execute in the sandbox
        """
        print("\n" + "="*70)
        print("STEP 6: GET LANGCHAIN TOOLS VIA MCP")
        print("="*70)
        print("""
        What's happening:
        -----------------
        The MCP server exposes tools via the Model Context Protocol.
        We use langchain-mcp-adapters to:
        
          1. Connect to MCP server at {mcp_url}/mcp
          2. List all available tools
          3. Convert them to LangChain Tool objects
        
        These tools include:
          • Shell: run commands, view output
          • Files: read, write, edit, patch
          • Browser: navigate, click, screenshot (Playwright)
          • Web: search, visit pages
          • Media: generate images/videos (Vertex AI)
        """.format(mcp_url=self.mcp_url))
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            # Connect to MCP server
            self.mcp_client = MultiServerMCPClient({
                "sandbox": {
                    "url": f"{self.mcp_url}/mcp",
                    "transport": "http"
                },
            })
            
            # Get all tools as LangChain Tools
            self.langchain_tools = await self.mcp_client.get_tools()
            
            print(f"\n✅ Retrieved {len(self.langchain_tools)} LangChain tools!")
            print("\n   Available tools:")
            
            # Group and display tools
            tool_names = sorted([t.name for t in self.langchain_tools])
            for i, name in enumerate(tool_names, 1):
                print(f"   {i:2}. {name}")
            
            return True
            
        except ImportError:
            print("❌ langchain-mcp-adapters not installed")
            print("   Run: pip install langchain-mcp-adapters")
            return False
        except Exception as e:
            print(f"❌ Failed to get tools: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # =========================================================================
    # STEP 7: Initialize LLM
    # =========================================================================
    
    async def step_7_initialize_llm(self):
        """
        STEP 7: Get an LLM instance using the project's helper.
        
        Code locations involved:
          - backend/src/llms/llm.py → get_llm()
          - Reads from .env: LLM_PROVIDER, OPENAI_API_KEY, etc.
        
        The get_llm() function supports:
          - OpenAI (gpt-4o, gpt-4o-mini, etc.)
          - Anthropic (claude-3.5-sonnet, etc.)
          - Google (gemini-pro, etc.)
          - Local models via Ollama
        """
        print("\n" + "="*70)
        print("STEP 7: INITIALIZE LLM")
        print("="*70)
        print("""
        What's happening:
        -----------------
        The get_llm() helper reads your .env configuration:
        
          LLM_PROVIDER=openai
          OPENAI_API_KEY=sk-...
          OPENAI_MODEL=gpt-4o-mini
        
        And returns a configured LangChain ChatModel.
        """)
        
        try:
            from backend.src.llms.llm import get_llm
            
            self.llm = get_llm()
            model_name = getattr(self.llm, 'model_name', 
                                getattr(self.llm, 'model', 'Unknown'))
            
            print(f"✅ LLM initialized: {model_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize LLM: {e}")
            print("   Check your .env file has LLM configuration")
            return False
    
    # =========================================================================
    # STEP 8: Create LangGraph Agent
    # =========================================================================
    
    async def step_8_create_agent(self):
        """
        STEP 8: Create a LangGraph ReAct agent with the tools and LLM.
        
        Code locations involved:
          - langgraph.prebuilt.create_react_agent
          - In production: backend/src/graph/builder.py (full workflow)
        
        The ReAct pattern:
          1. Agent receives user message
          2. Agent THINKS about what to do
          3. Agent ACTS (calls a tool if needed)
          4. Agent OBSERVES the result
          5. Repeat until task complete
          6. Agent responds to user
        """
        print("\n" + "="*70)
        print("STEP 8: CREATE LANGGRAPH AGENT")
        print("="*70)
        print("""
        What's happening:
        -----------------
        We combine the LLM and tools into a LangGraph agent.
        
        This simple version uses create_react_agent(), which implements
        the ReAct (Reasoning + Acting) pattern:
        
          User: "Create a hello world Python file"
              ↓
          Agent THINKS: "I need to write a file"
              ↓
          Agent ACTS: file_write(path="hello.py", content="print('Hello')")
              ↓
          Agent OBSERVES: "File written successfully"
              ↓
          Agent RESPONDS: "I've created hello.py for you!"
        
        In production, your backend uses a more sophisticated graph:
          backend/src/graph/builder.py
        
        With nodes for:
          - Background research
          - Planning
          - Execution
          - Human feedback
          - Reporting
        """)
        
        try:
            self.agent = create_react_agent(self.llm, self.langchain_tools)
            print(f"✅ Agent created with {len(self.langchain_tools)} tools!")
            return True
        except Exception as e:
            print(f"❌ Failed to create agent: {e}")
            return False
    
    # =========================================================================
    # STEP 9: Agent Processes User Message
    # =========================================================================
    
    async def step_9_run_agent_task(self, task: str):
        """
        STEP 9: The agent processes a user message and uses tools.
        
        This is the actual "agent doing work" step.
        The agent will reason about the task and call tools as needed.
        
        Tool execution flow:
          1. Agent decides to call a tool (e.g., file_write)
          2. LangChain MCP adapter sends request to MCP server
          3. MCP server (inside sandbox) executes the tool
          4. Result returned to agent
          5. Agent continues reasoning or responds
        """
        print("\n" + "="*70)
        print("STEP 9: AGENT PROCESSES USER MESSAGE")
        print("="*70)
        print(f"""
        What's happening:
        -----------------
        The agent receives the user's message:
          "{task}"
        
        Agent reasoning loop:
          1. Parse the request
          2. Decide which tools to use
          3. Execute tools (in E2B sandbox)
          4. Observe results
          5. Formulate response
        
        Executing now...
        """)
        
        try:
            result = await self.agent.ainvoke({
                "messages": [HumanMessage(content=task)]
            })
            
            print("\n" + "-"*70)
            print("AGENT EXECUTION TRACE:")
            print("-"*70)
            
            for msg in result.get("messages", []):
                msg_type = getattr(msg, 'type', 'unknown')
                content = getattr(msg, 'content', '')
                
                if msg_type == 'human':
                    print(f"\n👤 USER: {content}")
                elif msg_type == 'ai':
                    # Check for tool calls
                    tool_calls = getattr(msg, 'tool_calls', [])
                    if tool_calls:
                        print(f"\n🤖 AGENT (thinking): Will use tools...")
                        for tc in tool_calls:
                            print(f"   📎 Tool: {tc.get('name', 'unknown')}")
                            print(f"      Args: {tc.get('args', {})}")
                    elif content:
                        print(f"\n🤖 AGENT: {content}")
                elif msg_type == 'tool':
                    tool_name = getattr(msg, 'name', 'unknown')
                    # Truncate long outputs
                    display_content = content[:500] + "..." if len(content) > 500 else content
                    print(f"\n🔧 TOOL RESULT [{tool_name}]:")
                    print(f"   {display_content}")
            
            print("\n" + "-"*70)
            print("✅ Agent completed the task!")
            return True
            
        except Exception as e:
            print(f"\n❌ Agent error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # =========================================================================
    # STEP 10: Cleanup
    # =========================================================================
    
    async def step_10_cleanup(self):
        """
        STEP 10: Delete the sandbox and cleanup resources.
        
        In production this happens via:
          1. Automatic timeout (Redis queue schedules pause → terminate)
          2. User explicitly ends session
          3. Admin cleanup
        
        Code locations involved:
          - SandboxController.delete_sandbox()
          - E2BSandbox.delete() → calls sandbox.kill()
          - PostgreSQL: sandbox record deleted
        """
        print("\n" + "="*70)
        print("STEP 10: CLEANUP")
        print("="*70)
        print("""
        What's happening:
        -----------------
        Deleting the sandbox:
          1. HTTP DELETE /sandboxes/{sandbox_id}
          2. SandboxController.delete_sandbox()
          3. E2BSandbox.delete() → AsyncSandbox.kill()
          4. PostgreSQL record removed
          5. Redis queue messages cancelled
          6. E2B cloud VM terminated
        
        In production, this happens automatically via:
          • Idle timeout (configured in SandboxConfig)
          • Session end
          • User logout
        """)
        
        # Delete sandbox
        if self.sandbox_id and self.http_client:
            try:
                response = await self.http_client.delete(
                    f'{BASE_URL}/agent/sandboxes/sandboxes/{self.sandbox_id}'
                )
                if response.status_code == 200:
                    print(f"✅ Sandbox {self.sandbox_id} deleted")
                else:
                    print(f"⚠️ Sandbox deletion returned: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        print("\n✅ Cleanup complete!")
    
    # =========================================================================
    # RUN ALL STEPS
    # =========================================================================
    
    async def run_full_lifecycle(self, test_task: str = None):
        """Run through all 10 steps of the sandbox lifecycle."""
        
        print("\n" + "="*70)
        print("🚀 SANDBOX LIFECYCLE DEEP DIVE")
        print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        if test_task is None:
            test_task = "Create a Python file called hello.py that prints 'Hello from the sandbox!' and then run it to show the output."
        
        try:
            # Step 1: Verify backend
            if not await self.step_1_verify_backend_running():
                return False
            
            # Step 2: Authenticate
            if not await self.step_2_user_authentication():
                return False
            
            # Step 3: Create sandbox
            if not await self.step_3_create_sandbox():
                return False
            
            # Steps 4-5: Wait for MCP
            if not await self.step_4_5_wait_for_mcp_server():
                return False
            
            # Step 6: Get tools
            if not await self.step_6_get_langchain_tools():
                return False
            
            # Step 7: Initialize LLM
            if not await self.step_7_initialize_llm():
                return False
            
            # Step 8: Create agent
            if not await self.step_8_create_agent():
                return False
            
            # Step 9: Run task
            await self.step_9_run_agent_task(test_task)
            
            return True
            
        finally:
            # Step 10: Always cleanup
            await self.step_10_cleanup()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Run the sandbox lifecycle deep dive."""
    
    import argparse
    parser = argparse.ArgumentParser(
        description="Sandbox Lifecycle Deep Dive - Step-by-Step Annotated Test"
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Custom task for the agent to perform"
    )
    args = parser.parse_args()
    
    lifecycle = SandboxLifecycleDeepDive()
    success = await lifecycle.run_full_lifecycle(args.task)
    
    print("\n" + "="*70)
    if success:
        print("✅ LIFECYCLE COMPLETE - All steps executed successfully!")
    else:
        print("❌ LIFECYCLE INCOMPLETE - Check errors above")
    print("="*70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
