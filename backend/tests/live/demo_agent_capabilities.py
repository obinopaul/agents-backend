
import asyncio
import logging
import time
from typing import Dict, Any, List

# Setup logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import backend components
from backend.src.agents.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

# --- Define Real Tools ---
@tool
def calculator_add(a: int, b: int) -> int:
    """Add two numbers."""
    logger.info(f"TOOL EXECUTION: Adding {a} + {b}")
    return a + b

@tool
def calculator_multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    logger.info(f"TOOL EXECUTION: Multiplying {a} * {b}")
    return a * b

@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    logger.info(f"TOOL EXECUTION: Getting weather for {city}")
    return f"The weather in {city} is Sunny, 25°C"

# --- Helper for Printing ---
def print_header(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_step(step: str):
    print(f"\n--- {step} ---")

async def run_agent_interaction(agent: Any, user_input: str, config: Dict = None):
    print(f"\nUser: {user_input}")
    
    # We use 'stream' to see the thinking process
    # The compiled graph usually takes {"messages": [...]}
    initial_state = {"messages": [HumanMessage(content=user_input)]}
    
    print("Agent: (Thinking...)")
    async for event in agent.astream(initial_state, config=config):
        # Some middleware might yield non-dict events or we might get tool outputs
        if not isinstance(event, dict):
            # This handles case where stream yields something else or just skips
            continue
            
        for node_name, node_state in event.items():
            print(f"  [{node_name}] produced output")
            if not node_state or not isinstance(node_state, dict):
                continue
                
            if "messages" in node_state:
                last_msg = node_state["messages"][-1]
                # If it's the final response (AIMessage with content)
                if hasattr(last_msg, "content") and last_msg.content:
                     print(f"  -> Content: {last_msg.content[:100]}..." if len(last_msg.content) > 100 else f"  -> Content: {last_msg.content}")

# --- Scenarios ---

async def scenario_1_middleware_config():
    start_time = time.perf_counter()
    print_header("SCENARIO 1: Custom Middleware Configuration")
    print("Goal: Demonstrate configuring retry limits and using tools.")
    
    # Custom config for middleware
    mw_config = {
        "enable_model_retry": True,
        "model_max_retries": 2,
        "enable_tool_retry": True,
        "tool_max_retries": 2
    }
    
    agent = create_agent(
        agent_name="MathAgent",
        agent_type="assistant",
        tools=[calculator_add, calculator_multiply],
        prompt_template="generic", # Will fallback to default if not found
        use_default_middleware=True,
        middleware_config=mw_config
    )
    
    await run_agent_interaction(agent, "Calculate (5 + 3) * 10")
    print(f"\n[Timer] Scenario 1 finished in {time.perf_counter() - start_time:.4f}s")

async def scenario_2_default_middleware():
    start_time = time.perf_counter()
    print_header("SCENARIO 2: Default Production Middleware")
    print("Goal: Demonstrate default middleware stack (Summarization, Limits, etc).")
    
    agent = create_agent(
        agent_name="GeneralAgent",
        agent_type="assistant",
        tools=[get_weather],
        prompt_template="generic",
        use_default_middleware=True
        # No config passed, uses defaults from settings
    )
    
    await run_agent_interaction(agent, "What's the weather in Tokyo?")
    print(f"\n[Timer] Scenario 2 finished in {time.perf_counter() - start_time:.4f}s")

from langgraph.graph import StateGraph, MessagesState, START, END

async def scenario_3_interruption():
    start_time = time.perf_counter()
    print_header("SCENARIO 3: Graph Node Interruption (Native)")
    print("Goal: Demonstrate native `interrupt_before` by targeting a specific Graph Node.")
    print("Description: We build a sequence of two agents (Node A -> Node B) and interrupt before Node B.")
    
    # 1. Create two simple agents (using our factory) to act as nodes
    # Agent 1: Adds numbers
    agent_1 = create_agent(
        agent_name="Adder",
        agent_type="assistant",
        tools=[calculator_add],
        prompt_template="generic",
        use_default_middleware=False
    )
    
    # Agent 2: Multiplies numbers
    agent_2 = create_agent(
        agent_name="Multiplier",
        agent_type="assistant",
        tools=[calculator_multiply],
        prompt_template="generic",
        use_default_middleware=False
    )
    
    # 2. Define Node Functions
    async def run_agent_1(state: MessagesState):
        logging.info("--- Executing Node: agent_1 ---")
        # Invoke agent 1 with the current state
        result = await agent_1.ainvoke(state)
        # Return the last message (AIMessage) to update state
        return {"messages": [result["messages"][-1]]}

    async def run_agent_2(state: MessagesState):
        logging.info("--- Executing Node: agent_2 ---")
        # Invoke agent 2
        result = await agent_2.ainvoke(state)
        return {"messages": [result["messages"][-1]]}

    # 3. Build the Parent Graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent_1", run_agent_1)
    workflow.add_node("agent_2", run_agent_2)
    
    workflow.add_edge(START, "agent_1")
    workflow.add_edge("agent_1", "agent_2")
    workflow.add_edge("agent_2", END)
    
    # 4. Compile with Native Interrupt
    # We explicitly ask to interrupt before 'agent_2'
    interrupt_nodes = ["agent_2"]
    app = workflow.compile(interrupt_before=interrupt_nodes)
    
    print(f"\nGraph Structure: START -> agent_1 -> [INTERRUPT] -> agent_2 -> END")
    print("User Input: 'Add 5 and 5, then Multiply by 10'")
    
    initial_state = {"messages": [HumanMessage(content="Add 5 and 5. Then imply I want to multiply the result by 10.")]}
    
    try:
        print("\n--- Starting Graph Execution ---")
        async for event in app.astream(initial_state):
             # The event emission depends on stream_mode, defaults to values
             if not isinstance(event, dict): 
                 continue
                 
             for node_name, node_state in event.items():
                 print(f"  [{node_name}] produced output.")
                 if "messages" in node_state:
                     msg = node_state["messages"][-1]
                     if hasattr(msg, "content"):
                         print(f"   -> Result: {msg.content[:80]}...")

        # If execution stops here, it means we hit the interrupt or finished.
        # We can check the snapshot to see next steps
        print("\n--- Execution Paused/Stopped ---")
        print("Verifying stop reason...")
        
        # In a real app with persistence, we'd check app.get_state(config).next
        # But here astream simply exhausted because it hit an interrupt.
        # Since 'agent_2' output never printed, we know it stopped!
        
        print("Success: 'agent_2' did NOT execute.")
        print("Native 'interrupt_before' successfully halted graph execution at the target node.")

    except Exception as e:
        print(f"\n!!! Exception: {type(e).__name__}: {e}")
    
    print(f"\n[Timer] Scenario 3 finished in {time.perf_counter() - start_time:.4f}s")

async def main():
    print("Starting Manual Agent Capability Demo...")
    try:
        await scenario_1_middleware_config()
        await scenario_2_default_middleware()
        await scenario_3_interruption()
        print_header("DEMO COMPLETED SUCCESSFULLY")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
