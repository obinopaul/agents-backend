"""LangChain agent integration example using ReAct agent."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def langchain_agent_example():
    """Demonstrate integration with LangChain ReAct agent."""
    
    print("=" * 60)
    print("LangChain Sandbox Tools - Agent Integration Example")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠️  OPENAI_API_KEY not set. This example requires an LLM.")
        print("   Set your API key in .env or environment variables.")
        print("\n   Showing code example instead:\n")
        
        print("""
# Install dependencies:
# pip install langchain langchain-openai

from langchain_tools import create_sandbox_tools
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

# Create LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Create sandbox tools
tools = create_sandbox_tools(base_url="http://localhost:8080")

# Get ReAct prompt
prompt = hub.pull("hwchase17/react")

# Create agent
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Run agent
result = await agent_executor.ainvoke({
    "input": "Create a Python file that calculates fibonacci numbers, then run it"
})
print(result["output"])
""")
        return
    
    # If API key is set, run actual example
    try:
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain import hub
        from langchain_tools import create_sandbox_tools, SandboxClient
        
        # Check sandbox
        client = SandboxClient()
        if not await client.health_check():
            print("\n❌ Sandbox not running!")
            return
        
        print("\n✅ Sandbox connected")
        print("🤖 Creating LangChain agent...")
        
        # Create LLM
        llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Create sandbox tools
        tools = create_sandbox_tools()
        print(f"   Loaded {len(tools)} tools")
        
        # Get ReAct prompt
        prompt = hub.pull("hwchase17/react")
        
        # Create agent
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True,
            max_iterations=10,
        )
        
        # Run agent with a task
        print("\n" + "-" * 40)
        print("Running agent with task...")
        print("-" * 40)
        
        result = await agent_executor.ainvoke({
            "input": """
            1. Check the sandbox environment info
            2. Create a Python file called 'fibonacci.py' that defines a function 
               to calculate the nth Fibonacci number
            3. Run the file and print the first 10 Fibonacci numbers
            """
        })
        
        print("\n" + "-" * 40)
        print("Agent Result:")
        print("-" * 40)
        print(result["output"])
        
    except ImportError as e:
        print(f"\n⚠️  Missing dependency: {e}")
        print("   Install with: pip install langchain langchain-openai")
    
    print("\n" + "=" * 60)
    print("✅ Agent integration example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(langchain_agent_example())
