"""Example showing integration with a FastAPI backend.

This demonstrates how to use SandboxSession in a backend where
each API chat session gets its own isolated sandbox workspace.
"""

import asyncio
from typing import Dict, Optional
from contextlib import asynccontextmanager

# Uncomment when using with FastAPI
# from fastapi import FastAPI, HTTPException, Depends
# from pydantic import BaseModel

from langchain_tools import SandboxSession


class SessionManager:
    """Manages sandbox sessions for all active chats.
    
    In a real backend, you'd use this to:
    1. Create a session when a user starts a new chat
    2. Reuse the session for subsequent messages in the same chat
    3. Clean up when the chat ends or times out
    """
    
    def __init__(self, sandbox_url: str = "http://localhost:8080"):
        self.sandbox_url = sandbox_url
        self._sessions: Dict[str, SandboxSession] = {}
    
    async def get_or_create_session(self, chat_id: str) -> SandboxSession:
        """Get existing session or create new one for a chat.
        
        Args:
            chat_id: Unique identifier for the chat (from your backend)
            
        Returns:
            SandboxSession bound to this chat
        """
        if chat_id not in self._sessions:
            session = await SandboxSession.create(
                session_id=chat_id,
                base_url=self.sandbox_url,
            )
            self._sessions[chat_id] = session
        
        return self._sessions[chat_id]
    
    async def end_session(self, chat_id: str) -> bool:
        """End and cleanup a chat session.
        
        Args:
            chat_id: Chat to end
            
        Returns:
            True if session was ended, False if not found
        """
        if chat_id in self._sessions:
            await self._sessions[chat_id].cleanup()
            del self._sessions[chat_id]
            return True
        return False
    
    async def cleanup_all(self):
        """Cleanup all sessions (call on shutdown)."""
        for chat_id in list(self._sessions.keys()):
            await self.end_session(chat_id)
    
    def list_sessions(self) -> list:
        """List all active session IDs."""
        return list(self._sessions.keys())


# =============================================================================
# FastAPI Integration Example (uncomment to use)
# =============================================================================

"""
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

app = FastAPI()
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    yield
    # Shutdown - cleanup all sessions
    await session_manager.cleanup_all()
    print("All sandbox sessions cleaned up")


class ChatMessage(BaseModel):
    message: str


class AgentResponse(BaseModel):
    response: str
    session_id: str
    workspace: str


@app.post("/api/chat/{chat_id}")
async def chat(chat_id: str, message: ChatMessage) -> AgentResponse:
    '''Process a chat message with sandbox tools.'''
    
    # Get or create session for this chat
    session = await session_manager.get_or_create_session(chat_id)
    tools = session.get_tools()
    
    # Here you would:
    # 1. Pass tools to your LangChain agent
    # 2. Process the user's message
    # 3. Return the agent's response
    
    # Example: Just echo for now
    return AgentResponse(
        response=f"Received: {message.message}",
        session_id=session.session_id,
        workspace=session.workspace_path,
    )


@app.delete("/api/chat/{chat_id}")
async def end_chat(chat_id: str):
    '''End a chat session and cleanup its sandbox workspace.'''
    
    if await session_manager.end_session(chat_id):
        return {"message": f"Session {chat_id} ended"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/api/sessions")
async def list_sessions():
    '''List all active chat sessions.'''
    return {"sessions": session_manager.list_sessions()}
"""


# =============================================================================
# Demo without FastAPI
# =============================================================================

async def demo():
    """Demonstrate session manager usage."""
    
    print("=" * 60)
    print("Backend Integration Demo")
    print("=" * 60)
    
    manager = SessionManager()
    
    # Simulate multiple chat users
    print("\n📱 Simulating 3 concurrent chat sessions...")
    
    # User 1 starts a chat
    session1 = await manager.get_or_create_session("user1_chat_abc")
    tools1 = {t.name: t for t in session1.get_tools()}
    print(f"✅ User 1 session: {session1.workspace_path}")
    
    # User 2 starts a chat  
    session2 = await manager.get_or_create_session("user2_chat_def")
    tools2 = {t.name: t for t in session2.get_tools()}
    print(f"✅ User 2 session: {session2.workspace_path}")
    
    # User 3 starts a chat
    session3 = await manager.get_or_create_session("user3_chat_ghi")
    tools3 = {t.name: t for t in session3.get_tools()}
    print(f"✅ User 3 session: {session3.workspace_path}")
    
    print(f"\n📊 Active sessions: {manager.list_sessions()}")
    
    # Simulate work in each session
    print("\n💼 Simulating work in each session...")
    
    await tools1["file_write"].ainvoke({
        "file": "user1_file.txt",
        "content": "User 1's private data",
    })
    
    await tools2["file_write"].ainvoke({
        "file": "user2_file.txt", 
        "content": "User 2's private data",
    })
    
    await tools3["python_execute"].ainvoke({
        "code": "print('User 3 running Python!')",
    })
    
    # User 2 ends their chat
    print("\n👋 User 2 ends their chat...")
    await manager.end_session("user2_chat_def")
    print(f"📊 Active sessions: {manager.list_sessions()}")
    
    # Cleanup remaining
    print("\n🧹 Server shutdown - cleaning all sessions...")
    await manager.cleanup_all()
    print(f"📊 Active sessions: {manager.list_sessions()}")
    
    print("\n" + "=" * 60)
    print("✅ Backend integration demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
