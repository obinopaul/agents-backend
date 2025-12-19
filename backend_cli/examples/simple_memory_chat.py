#!/usr/bin/env python3
"""
Simple memory-augmented chat example.

This is a minimal example showing how to use LangGraph store with memories.
For a more complete example with file loading, see memory_graph.py.

Usage:
    python examples/simple_memory_chat.py

Environment variables (can be set in .env file):
    ANTHROPIC_API_KEY=your-key
    OPENAI_API_KEY=your-key  # for embeddings
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

# Load environment variables from .env file
load_dotenv()

# Initialize model and embeddings
model = init_chat_model("anthropic:claude-haiku-4-5")
embeddings = init_embeddings("openai:text-embedding-3-small")

# Create store with semantic search enabled
store = InMemoryStore(
    index={
        "embed": embeddings,
        "dims": 1536,
    }
)

# Add some example memories
store.put(("user_123", "memories"), "1", {"text": "I love pizza, especially margherita"})
store.put(
    ("user_123", "memories"), "2", {"text": "I am a software engineer working on AI projects"}
)
store.put(("user_123", "memories"), "3", {"text": "I prefer dark mode in all my applications"})
store.put(("user_123", "memories"), "4", {"text": "I'm learning Rust and really enjoying it"})
store.put(("user_123", "memories"), "5", {"text": "I have a cat named Luna"})
store.put(("user_123", "memories"), "6", {"text": "I usually work from home on Fridays"})
store.put(("user_123", "memories"), "7", {"text": "My favorite framework is FastAPI"})
store.put(("user_123", "memories"), "8", {"text": "I'm vegetarian but eat fish occasionally"})


def chat(state: MessagesState, *, store: BaseStore):
    """Chat node with memory retrieval."""
    # Search for memories relevant to the user's message
    items = store.search(
        ("user_123", "memories"),
        query=state["messages"][-1].content,
        limit=3,
    )

    # Format memories
    memories = "\n".join(f"- {item.value['text']}" for item in items)
    memories_section = f"## Memories about user\n{memories}" if memories else ""

    # Generate response with memory context
    response = model.invoke(
        [
            {
                "role": "system",
                "content": f"You are a helpful assistant. Use these memories to personalize responses.\n{memories_section}",
            },
            *state["messages"],
        ]
    )

    return {"messages": [response]}


# Build the graph
builder = StateGraph(MessagesState)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
graph = builder.compile(store=store)


if __name__ == "__main__":
    # Test with some example queries
    test_queries = [
        "I'm hungry, what should I eat?",
        "What programming language should I learn next?",
        "Tell me about my pet",
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"User: {query}")
        print(f"{'=' * 60}")
        print("Assistant: ", end="")

        for message, metadata in graph.stream(
            input={"messages": [{"role": "user", "content": query}]},
            stream_mode="messages",
        ):
            if hasattr(message, "content"):
                print(message.content, end="")

        print("\n")
