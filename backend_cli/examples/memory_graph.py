#!/usr/bin/env python3
"""
Example LangGraph application that uses the store with generated memories.

This demonstrates:
1. Loading memories from a JSONL file into the store
2. Using semantic search to retrieve relevant memories
3. Augmenting chat responses with retrieved context

Usage:
    # First, generate some test memories
    python scripts/generate_memories.py -n 1000 -o examples/memories.jsonl --seed 42

    # Then run this example
    python examples/memory_graph.py

    # Or run with a custom memories file
    python examples/memory_graph.py --memories path/to/memories.jsonl

Requirements:
    pip install langchain-anthropic langchain-openai langgraph
    export ANTHROPIC_API_KEY=your-key
    export OPENAI_API_KEY=your-key  # for embeddings
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from langchain.chat_models import init_chat_model
    from langchain.embeddings import init_embeddings
    from langgraph.graph import START, MessagesState, StateGraph
    from langgraph.store.base import BaseStore
    from langgraph.store.memory import InMemoryStore
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nInstall required packages:")
    print("  pip install langchain-anthropic langchain-openai langgraph python-dotenv")
    sys.exit(1)


def load_memories_from_jsonl(filepath: str, limit: int | None = None) -> list[dict]:
    """Load memories from a JSONL file."""
    memories = []
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            if line.strip():
                memories.append(json.loads(line))
    return memories


def memory_to_text(value: dict) -> str:
    """Convert a memory value to searchable text."""
    mem_type = value.get("type", "unknown")

    if mem_type == "preference":
        return f"User prefers {value.get('category', 'unknown')}: {value.get('value', 'unknown')} (confidence: {value.get('confidence', 0):.0%})"

    elif mem_type == "fact":
        return value.get("content", "Unknown fact")

    elif mem_type == "context":
        tech = ", ".join(value.get("tech", []))
        return f"Working on {value.get('project', 'unknown')} project ({value.get('status', 'unknown')}). Tech: {tech}"

    elif mem_type == "interaction":
        return f"Previous {value.get('action', 'interaction')} about {value.get('topic', 'unknown')} - sentiment: {value.get('sentiment', 'neutral')}"

    elif mem_type == "note":
        return value.get("content", "Unknown note")

    elif mem_type == "text":
        return value.get("content", "Unknown text")

    else:
        # Fallback: stringify the value
        return json.dumps(value)


def populate_store(store: InMemoryStore, memories: list[dict], user_id: str = "user_1") -> int:
    """Populate the store with memories, converting them to searchable text."""
    count = 0
    for memory in memories:
        # Use original namespace or create one based on user_id
        ns = memory.get("namespace", [])
        if isinstance(ns, str):
            ns = tuple(ns.split(","))
        else:
            ns = tuple(ns)

        # If namespace doesn't start with a user, prefix it
        if not ns or not ns[0].startswith("user_"):
            ns = (user_id, "memories") + ns

        key = memory.get("key", f"mem_{count}")
        value = memory.get("value", {})

        # Add searchable text field
        text = memory_to_text(value)
        store_value = {
            "text": text,
            "original": value,
            "type": value.get("type", "unknown"),
        }

        store.put(ns, key, store_value)
        count += 1

    return count


def create_chat_graph(
    store: InMemoryStore, model_name: str = "gpt-4o-mini", user_id: str = "user_1"
):
    """Create a chat graph that uses memories from the store."""

    model = init_chat_model(model_name)

    def chat(state: MessagesState, *, store: BaseStore):
        """Chat node that retrieves relevant memories and generates a response."""
        last_message = state["messages"][-1].content

        # Search for relevant memories across user's namespace
        items = store.search(
            (user_id, "memories"),
            query=last_message,
            limit=5,
        )

        # Format memories for context
        if items:
            memory_texts = []
            for item in items:
                text = item.value.get("text", "")
                mem_type = item.value.get("type", "unknown")
                memory_texts.append(f"- [{mem_type}] {text}")

            memories_context = "## Relevant memories about the user\n" + "\n".join(memory_texts)
        else:
            memories_context = ""

        # Build system prompt
        system_prompt = f"""You are a helpful AI assistant with access to memories about the user.
Use these memories to personalize your responses when relevant.
Don't mention that you're using memories unless the user asks.

{memories_context}"""

        # Generate response
        response = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                *state["messages"],
            ]
        )

        return {"messages": [response]}

    # Build the graph
    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat)
    builder.add_edge(START, "chat")

    return builder.compile(store=store)


def interactive_chat(graph, verbose: bool = False):
    """Run an interactive chat session."""
    print("\n" + "=" * 60)
    print("Memory-Augmented Chat")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the conversation.")
    print("Type 'memories' to see what memories were used.\n")

    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower() == "memories":
            # Show recent memory retrieval (would need to track this)
            print("[Memory inspection not implemented in this demo]")
            continue

        messages.append({"role": "user", "content": user_input})

        print("Assistant: ", end="", flush=True)

        # Stream the response
        for message, metadata in graph.stream(
            input={"messages": messages},
            stream_mode="messages",
        ):
            if hasattr(message, "content"):
                print(message.content, end="", flush=True)

        print()  # New line after response

        # Get the final response to add to messages
        result = graph.invoke({"messages": messages})
        if result.get("messages"):
            last_msg = result["messages"][-1]
            messages.append({"role": "assistant", "content": last_msg.content})


def main():
    parser = argparse.ArgumentParser(
        description="Memory-augmented chat using LangGraph store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate memories first
  python scripts/generate_memories.py -n 500 -o examples/memories.jsonl --seed 42

  # Run with generated memories
  python examples/memory_graph.py --memories examples/memories.jsonl

  # Run with limited memories for faster startup
  python examples/memory_graph.py --memories examples/memories.jsonl --limit 100

  # Use a different model
  python examples/memory_graph.py --model gpt-4o --memories examples/memories.jsonl
        """,
    )

    parser.add_argument(
        "--memories",
        type=str,
        default="examples/memories.jsonl",
        help="Path to memories JSONL file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of memories to load",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic:claude-haiku-4-5",
        help="Chat model to use (default: anthropic:claude-haiku-4-5)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="user_1",
        help="User ID for memory namespace (default: user_1)",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="openai:text-embedding-3-small",
        help="Embedding model for semantic search (default: openai:text-embedding-3-small)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output",
    )
    parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="Single message mode (no interactive chat)",
    )

    args = parser.parse_args()

    # Check for API keys
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Export your Anthropic API key: export ANTHROPIC_API_KEY=your-key")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set (needed for embeddings)")
        print("Export your OpenAI API key: export OPENAI_API_KEY=your-key")
        sys.exit(1)

    # Check if memories file exists
    memories_path = Path(args.memories)
    if not memories_path.exists():
        print(f"Memories file not found: {args.memories}")
        print("\nGenerate memories first:")
        print(f"  python scripts/generate_memories.py -n 500 -o {args.memories} --seed 42")
        sys.exit(1)

    # Initialize embeddings and store
    print(f"Initializing embeddings ({args.embedding_model})...")
    embeddings = init_embeddings(args.embedding_model)

    store = InMemoryStore(
        index={
            "embed": embeddings,
            "dims": 1536,
        }
    )

    # Load memories
    print(f"Loading memories from {args.memories}...")
    memories = load_memories_from_jsonl(args.memories, limit=args.limit)
    count = populate_store(store, memories, user_id=args.user_id)
    print(f"Loaded {count} memories into store")

    # Create the graph
    print(f"Creating chat graph with model {args.model}...")
    graph = create_chat_graph(store, model_name=args.model, user_id=args.user_id)

    # Run
    if args.single:
        # Single message mode
        print("\nAssistant: ", end="", flush=True)
        for message, metadata in graph.stream(
            input={"messages": [{"role": "user", "content": args.single}]},
            stream_mode="messages",
        ):
            if hasattr(message, "content"):
                print(message.content, end="", flush=True)
        print()
    else:
        # Interactive mode
        interactive_chat(graph, verbose=args.verbose)


if __name__ == "__main__":
    main()
