#!/usr/bin/env python3
"""
Memory-augmented chat using a remote LangGraph store.

This example shows how to:
1. Connect to a remote LangGraph deployment
2. Load generated memories via the lgctl client
3. Use semantic search in the chat loop

Usage:
    # Generate and import memories first
    python scripts/generate_memories.py -n 1000 -o memories.jsonl --distribution users
    lgctl ops import memories.jsonl --overwrite

    # Run the chat
    python examples/remote_memory_chat.py --user user_1

Environment variables (can be set in .env file):
    ANTHROPIC_API_KEY=your-key
    LANGSMITH_API_KEY=your-key
    LANGSMITH_DEPLOYMENT_URL=https://your-deployment.langsmith.dev
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from langchain.chat_models import init_chat_model
    from langgraph_sdk import get_client
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nInstall required packages:")
    print("  pip install langchain-anthropic langgraph langgraph-sdk python-dotenv")
    sys.exit(1)


async def search_memories(client, namespace: tuple, query: str, limit: int = 5) -> list[dict]:
    """Search for memories in the remote store."""
    try:
        results = await client.store.search_items(
            namespace,
            query=query,
            limit=limit,
        )
        return results.get("items", [])
    except Exception as e:
        print(f"Warning: Memory search failed: {e}")
        return []


def format_memory(item: dict) -> str:
    """Format a memory item for display in context."""
    value = item.get("value", {})
    mem_type = value.get("type", "unknown")

    if mem_type == "preference":
        return f"[preference] Prefers {value.get('category')}: {value.get('value')}"
    elif mem_type == "fact":
        return f"[fact] {value.get('content')}"
    elif mem_type == "context":
        tech = ", ".join(value.get("tech", []))
        return f"[context] Working on {value.get('project')} ({value.get('status')}). Tech: {tech}"
    elif mem_type == "interaction":
        return f"[interaction] {value.get('action')} about {value.get('topic')}"
    elif mem_type == "note":
        return f"[note] {value.get('content')}"
    elif mem_type == "text":
        return f"[text] {value.get('content')}"
    else:
        return f"[{mem_type}] {value}"


async def chat_with_memories(
    user_message: str,
    chat_model,
    lg_client,
    user_namespace: tuple,
    message_history: list,
) -> str:
    """Generate a chat response with memory augmentation."""

    # Search for relevant memories
    memories = await search_memories(lg_client, user_namespace, user_message, limit=5)

    # Format memories for context
    if memories:
        memory_texts = [format_memory(m) for m in memories]
        memories_context = "## Relevant memories about the user\n" + "\n".join(
            f"- {t}" for t in memory_texts
        )
    else:
        memories_context = ""

    # Build messages
    system_prompt = f"""You are a helpful AI assistant with access to memories about the user.
Use these memories to personalize your responses when relevant.
Don't explicitly mention that you're using memories unless asked.

{memories_context}"""

    messages = [
        {"role": "system", "content": system_prompt},
        *message_history,
        {"role": "user", "content": user_message},
    ]

    # Generate response
    response = chat_model.invoke(messages)
    return response.content


async def interactive_chat(chat_model, lg_client, user_id: str):
    """Run an interactive chat session."""
    user_namespace = ("memories", user_id)

    print("\n" + "=" * 60)
    print(f"Memory-Augmented Chat (user: {user_id})")
    print("=" * 60)
    print("Type 'quit' to exit, 'search <query>' to search memories directly.\n")

    message_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        # Direct memory search command
        if user_input.lower().startswith("search "):
            query = user_input[7:]
            print(f"\nSearching memories for: '{query}'")
            memories = await search_memories(lg_client, user_namespace, query, limit=10)
            if memories:
                for i, m in enumerate(memories, 1):
                    print(f"  {i}. {format_memory(m)}")
            else:
                print("  No memories found.")
            print()
            continue

        # Generate response with memory augmentation
        response = await chat_with_memories(
            user_input,
            chat_model,
            lg_client,
            user_namespace,
            message_history,
        )

        print(f"Assistant: {response}\n")

        # Update history
        message_history.append({"role": "user", "content": user_input})
        message_history.append({"role": "assistant", "content": response})

        # Keep history manageable
        if len(message_history) > 20:
            message_history = message_history[-20:]


async def main():
    parser = argparse.ArgumentParser(
        description="Chat with remote LangGraph store memories",
    )
    parser.add_argument(
        "--user",
        type=str,
        default="user_1",
        help="User ID for memory namespace (default: user_1)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic:claude-sonnet-4-20250514",
        help="Chat model to use (default: anthropic:claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="LangGraph deployment URL (default: from LANGSMITH_DEPLOYMENT_URL)",
    )

    args = parser.parse_args()

    # Check environment
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    url = args.url or os.getenv("LANGSMITH_DEPLOYMENT_URL") or os.getenv("LANGGRAPH_URL")
    if not url:
        print("Error: No LangGraph URL configured")
        print("Set LANGSMITH_DEPLOYMENT_URL or use --url")
        sys.exit(1)

    # Initialize
    print(f"Connecting to {url}...")
    lg_client = get_client(url=url, api_key=os.getenv("LANGSMITH_API_KEY"))

    print(f"Initializing chat model ({args.model})...")
    chat_model = init_chat_model(args.model)

    # Run chat
    await interactive_chat(chat_model, lg_client, args.user)


if __name__ == "__main__":
    asyncio.run(main())
