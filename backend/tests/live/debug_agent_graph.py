
import asyncio
import logging
from backend.src.agents.agents import create_agent
from langchain_core.tools import tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
def dummy_tool(x: int) -> int:
    """Dummy tool"""
    return x

async def main():
    print("--- Inspecting Agent Graph Structure ---")
    
    agent = create_agent(
        agent_name="GraphInspector",
        agent_type="assistant",
        tools=[dummy_tool],
        prompt_template="analyst",
        use_default_middleware=False
    )
    
    graph = agent.get_graph()
    print("\nGraph Nodes:")
    for node in graph.nodes:
        print(f" - {node}")
        
    print("\nGraph Edges:")
    # Edges might be complex to print, but let's try basic structure
    pass

if __name__ == "__main__":
    asyncio.run(main())
