"""Quick test script to verify the agent responds correctly."""
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger('test')


async def test_agent():
    from backend.src.agents import create_agent
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage
    
    # Create a simple calculator tool
    @tool
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression and return the result."""
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return f"The result of {expression} is {result}"
        except Exception as e:
            return f"Error calculating: {e}"
    
    print("=" * 60)
    print("AGENT TEST - Creating agent...")
    print("=" * 60)
    
    agent = create_agent(
        agent_name="math_agent",
        agent_type="researcher",
        tools=[calculate],
        prompt_template="researcher",
        locale="en-US",
        use_default_middleware=False,  # Skip middleware for quick test
    )
    print(f"Agent created: {type(agent).__name__}")
    
    # Test with a simple question
    question = "What is 25 * 4? Please use the calculate tool to compute this."
    print(f"\nQuestion: {question}")
    print("-" * 60)
    
    test_input = {
        "messages": [
            HumanMessage(content=question)
        ]
    }
    
    print("\nInvoking agent...")
    result = await agent.ainvoke(test_input)
    
    print(f"\nResult keys: {list(result.keys())}")
    messages = result.get("messages", [])
    print(f"Number of messages: {len(messages)}")
    
    # Print all messages
    print("\n" + "=" * 60)
    print("CONVERSATION:")
    print("=" * 60)
    
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        content = getattr(msg, "content", str(msg))
        
        # Handle tool calls
        tool_calls = getattr(msg, "tool_calls", None)
        
        print(f"\n[{i}] {msg_type}:")
        if content:
            print(f"    Content: {content[:300]}{'...' if len(str(content)) > 300 else ''}")
        if tool_calls:
            for tc in tool_calls:
                print(f"    Tool Call: {tc.get('name', 'unknown')}({tc.get('args', {})})")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agent())
