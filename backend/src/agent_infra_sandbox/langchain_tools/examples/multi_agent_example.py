"""Multi-agent example demonstrating workspace isolation."""

import asyncio
from langchain_tools import SandboxToolkit, SandboxClient


async def agent_task(agent_name: str, workspace: str, tools: dict):
    """Simulate an agent working in its isolated workspace."""
    
    print(f"\n[{agent_name}] Starting work in {workspace}")
    
    # Create a file in the workspace
    await tools["file_write"].ainvoke({
        "file": f"{workspace}/task.txt",
        "content": f"This file was created by {agent_name}",
    })
    print(f"[{agent_name}] Created task.txt")
    
    # Run some Python code
    result = await tools["jupyter_execute"].ainvoke({
        "code": f"""
workspace = "{workspace}"
agent = "{agent_name}"
print(f"Running as {{agent}} in {{workspace}}")

# Do some work
result = sum(range(100))
print(f"Computed: {{result}}")
""",
        "session_id": f"{agent_name}_session",
    })
    print(f"[{agent_name}] Python result: {result.strip()}")
    
    # List files in workspace
    files = await tools["file_list"].ainvoke({
        "path": workspace,
    })
    print(f"[{agent_name}] Files:\n{files}")
    
    return f"{agent_name} completed"


async def multi_agent_example():
    """Demonstrate multiple agents with isolated workspaces."""
    
    print("=" * 60)
    print("LangChain Sandbox Tools - Multi-Agent Example")
    print("=" * 60)
    
    # Create client
    client = SandboxClient()
    
    # Check health
    if not await client.health_check():
        print("\n❌ Sandbox not running! Start with:")
        print("  docker run --security-opt seccomp=unconfined --rm -d -p 8080:8080 ghcr.io/agent-infra/sandbox:latest")
        return
    
    print("\n✅ Sandbox connected")
    
    # Create isolated workspaces for each agent
    print("\n📁 Creating isolated workspaces...")
    workspace1 = await client.create_workspace("agent_alpha")
    workspace2 = await client.create_workspace("agent_beta")
    workspace3 = await client.create_workspace("agent_gamma")
    
    print(f"   - Agent Alpha: {workspace1}")
    print(f"   - Agent Beta:  {workspace2}")
    print(f"   - Agent Gamma: {workspace3}")
    
    # Create toolkit and tools
    toolkit = SandboxToolkit()
    tools = {t.name: t for t in toolkit.get_tools()}
    
    # Run agents concurrently (simulated)
    print("\n🤖 Running agents concurrently...")
    
    results = await asyncio.gather(
        agent_task("Agent_Alpha", workspace1, tools),
        agent_task("Agent_Beta", workspace2, tools),
        agent_task("Agent_Gamma", workspace3, tools),
    )
    
    print("\n" + "-" * 40)
    print("Results:")
    for result in results:
        print(f"   ✅ {result}")
    
    # Verify isolation - check that each workspace has only its own file
    print("\n" + "-" * 40)
    print("Verifying workspace isolation...")
    
    for name, workspace in [
        ("Alpha", workspace1),
        ("Beta", workspace2),
        ("Gamma", workspace3),
    ]:
        content = await tools["file_read"].ainvoke({
            "file": f"{workspace}/task.txt",
        })
        print(f"   {name}'s task.txt: {content.strip().split(chr(10))[-1]}")
    
    # Cleanup sessions
    print("\n🧹 Cleaning up sessions...")
    await client.cleanup_sessions()
    
    print("\n" + "=" * 60)
    print("✅ Multi-agent example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(multi_agent_example())
