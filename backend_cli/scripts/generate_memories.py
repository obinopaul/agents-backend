#!/usr/bin/env python3
"""
Generate arbitrary test memories for experimentation with lgctl.

This script generates JSONL files that can be imported using `lgctl ops import`.
Designed to efficiently generate millions of records.

Usage:
    # Generate to file (recommended for large datasets)
    python scripts/generate_memories.py -n 1000000 -o memories.jsonl

    # Stream to stdout (can pipe to import)
    python scripts/generate_memories.py -n 1000 | lgctl ops import --stdin

    # Generate with specific patterns
    python scripts/generate_memories.py -n 50000 --namespace "user,test" -o test.jsonl

    # Import the generated file
    lgctl ops import memories.jsonl --overwrite
"""

import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, Iterator, TextIO

# Sample data pools for generating realistic memories
USERS = [f"user_{i}" for i in range(1, 1001)]  # 1000 users
SESSIONS = [f"session_{i:06d}" for i in range(1, 10001)]  # 10000 sessions
PROJECTS = [
    "api-gateway", "web-frontend", "data-pipeline", "ml-service", "auth-service",
    "payment-processor", "notification-hub", "analytics-engine", "search-service",
    "cache-layer", "message-queue", "config-service", "monitoring", "logging",
]

TOPICS = [
    "python", "javascript", "rust", "golang", "typescript", "java", "csharp",
    "machine_learning", "data_science", "web_development", "devops", "security",
    "databases", "api_design", "testing", "debugging", "performance", "architecture",
    "microservices", "kubernetes", "docker", "aws", "gcp", "azure", "terraform",
]

SENTIMENTS = ["positive", "neutral", "negative", "curious", "focused", "frustrated"]
SOURCES = ["conversation", "explicit", "inferred", "system", "feedback", "observation"]
ACTIONS = ["code_review", "debugging", "refactoring", "learning", "planning", "implementing"]

# Expandable content templates
PREFERENCE_CATEGORIES = {
    "editor": ["vscode", "neovim", "vim", "emacs", "sublime", "intellij", "webstorm"],
    "theme": ["dark", "light", "solarized", "monokai", "dracula", "nord"],
    "language": TOPICS[:10],
    "framework": ["fastapi", "django", "flask", "react", "vue", "angular", "svelte", "nextjs"],
    "testing": ["pytest", "jest", "mocha", "unittest", "vitest", "playwright"],
    "vcs": ["git", "github", "gitlab", "bitbucket"],
    "shell": ["bash", "zsh", "fish", "powershell"],
    "os": ["linux", "macos", "windows", "wsl"],
}

FACT_TEMPLATES = [
    "User prefers {style} programming patterns",
    "User works on {domain} applications",
    "User is experienced with {tech}",
    "User prefers {methodology} development",
    "User works in a {architecture} architecture",
    "User maintains {count} open source projects",
    "User focuses on {area} development",
    "User is learning about {topic}",
    "User has {years} years of experience",
    "User typically works with {team_size} team members",
]

FACT_FILLS = {
    "style": ["functional", "object-oriented", "procedural", "reactive", "declarative"],
    "domain": ["e-commerce", "fintech", "healthcare", "gaming", "social", "enterprise", "saas"],
    "tech": TOPICS,
    "methodology": ["test-driven", "behavior-driven", "agile", "continuous integration"],
    "architecture": ["microservices", "monolithic", "serverless", "event-driven", "hexagonal"],
    "count": ["several", "multiple", "a few", "many"],
    "area": ["backend", "frontend", "fullstack", "devops", "data", "ml/ai", "mobile"],
    "topic": ["AI/ML integration", "cloud architecture", "system design", "distributed systems"],
    "years": ["2-3", "3-5", "5-7", "7-10", "10+"],
    "team_size": ["small (2-5)", "medium (5-10)", "large (10+)"],
}

NOTE_TEMPLATES = [
    "Remember to use {practice} consistently",
    "Prefers {approach} over {alternative}",
    "Likes {style} commit messages",
    "Uses {convention} format",
    "Appreciates {feedback_type} suggestions",
    "Values {quality} over {tradeoff}",
    "Prefers {pattern} over {antipattern}",
    "Likes {coverage} test coverage",
    "Tends to {habit} when coding",
    "Usually asks about {concern} first",
]

NOTE_FILLS = {
    "practice": ["type hints", "docstrings", "error handling", "logging", "testing"],
    "approach": ["explicit error handling", "composition", "immutability", "pure functions"],
    "alternative": ["try/except blocks", "inheritance", "mutability", "side effects"],
    "style": ["detailed", "concise", "conventional", "semantic"],
    "convention": ["conventional commits", "gitmoji", "angular", "custom"],
    "feedback_type": ["performance optimization", "security", "readability", "simplification"],
    "quality": ["code readability", "performance", "simplicity", "correctness"],
    "tradeoff": ["cleverness", "premature optimization", "complexity", "verbosity"],
    "pattern": ["composition", "explicit returns", "early returns", "dependency injection"],
    "antipattern": ["inheritance", "implicit behavior", "nested conditionals", "global state"],
    "coverage": ["comprehensive", "critical path", "integration", "unit"],
    "habit": ["refactor as you go", "write tests first", "document thoroughly", "prototype quickly"],
    "concern": ["edge cases", "performance", "security", "maintainability"],
}


def fill_template(template: str, fills: dict[str, list[str]]) -> str:
    """Fill a template string with random choices from fills dict."""
    result = template
    for key, options in fills.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, random.choice(options), 1)
    return result


def generate_uuid() -> str:
    """Generate a short UUID for keys."""
    return uuid.uuid4().hex[:12]


def generate_timestamp(max_days_ago: int = 90) -> str:
    """Generate a random timestamp within the last N days."""
    delta = timedelta(
        days=random.randint(0, max_days_ago),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return (datetime.now() - delta).isoformat()


def generate_preference() -> dict[str, Any]:
    """Generate a preference memory."""
    category = random.choice(list(PREFERENCE_CATEGORIES.keys()))
    return {
        "type": "preference",
        "category": category,
        "value": random.choice(PREFERENCE_CATEGORIES[category]),
        "confidence": round(random.uniform(0.5, 1.0), 2),
        "source": random.choice(SOURCES),
    }


def generate_fact() -> dict[str, Any]:
    """Generate a fact memory."""
    template = random.choice(FACT_TEMPLATES)
    return {
        "type": "fact",
        "content": fill_template(template, FACT_FILLS),
        "confidence": round(random.uniform(0.6, 1.0), 2),
        "source": random.choice(SOURCES),
    }


def generate_context() -> dict[str, Any]:
    """Generate a context memory."""
    return {
        "type": "context",
        "project": random.choice(PROJECTS),
        "status": random.choice(["active", "maintenance", "development", "archived"]),
        "tech": random.sample(TOPICS, k=random.randint(1, 4)),
        "priority": random.choice(["high", "medium", "low"]),
    }


def generate_interaction() -> dict[str, Any]:
    """Generate an interaction memory."""
    return {
        "type": "interaction",
        "action": random.choice(ACTIONS),
        "sentiment": random.choice(SENTIMENTS),
        "topic": random.choice(TOPICS),
        "duration_minutes": random.randint(1, 120),
        "successful": random.random() > 0.1,
    }


def generate_note() -> dict[str, Any]:
    """Generate a note memory."""
    template = random.choice(NOTE_TEMPLATES)
    return {
        "type": "note",
        "content": fill_template(template, NOTE_FILLS),
        "importance": round(random.uniform(0.3, 1.0), 2),
    }


def generate_embedding_text() -> dict[str, Any]:
    """Generate a text memory suitable for embedding/semantic search."""
    texts = [
        f"The user asked about {random.choice(TOPICS)} and how to implement {random.choice(ACTIONS)}",
        f"Discussion about {random.choice(PROJECTS)} architecture using {random.choice(TOPICS)}",
        f"User wants to learn more about {random.choice(TOPICS)} best practices",
        f"Helped with {random.choice(ACTIONS)} in {random.choice(TOPICS)} codebase",
        f"User preference for {random.choice(list(PREFERENCE_CATEGORIES.keys()))} settings",
    ]
    return {
        "type": "text",
        "content": random.choice(texts),
        "embedding_ready": True,
    }


GENERATORS = {
    "preference": generate_preference,
    "fact": generate_fact,
    "context": generate_context,
    "interaction": generate_interaction,
    "note": generate_note,
    "text": generate_embedding_text,
}


def generate_namespace(base_namespace: str | None = None, distribution: str = "mixed") -> list[str]:
    """Generate a namespace based on distribution pattern."""
    if base_namespace:
        return base_namespace.split(",")

    if distribution == "users":
        # User-centric: memories/user_X/category
        patterns = [
            ["memories", random.choice(USERS)],
            ["memories", random.choice(USERS), "preferences"],
            ["memories", random.choice(USERS), "facts"],
            ["memories", random.choice(USERS), "context"],
            ["memories", random.choice(USERS), "interactions"],
        ]
    elif distribution == "sessions":
        # Session-centric
        patterns = [
            ["sessions", random.choice(SESSIONS)],
            ["sessions", random.choice(SESSIONS), "messages"],
            ["sessions", random.choice(SESSIONS), "context"],
        ]
    elif distribution == "projects":
        # Project-centric
        patterns = [
            ["projects", random.choice(PROJECTS)],
            ["projects", random.choice(PROJECTS), "notes"],
            ["projects", random.choice(PROJECTS), "context"],
        ]
    elif distribution == "flat":
        # Single namespace (good for testing large namespaces)
        return ["test", "memories"]
    else:  # mixed
        patterns = [
            ["memories", random.choice(USERS)],
            ["memories", random.choice(USERS), random.choice(["preferences", "facts", "context"])],
            ["sessions", random.choice(SESSIONS)],
            ["sessions", random.choice(SESSIONS), random.choice(["messages", "context"])],
            ["projects", random.choice(PROJECTS)],
            ["projects", random.choice(PROJECTS), random.choice(["notes", "context"])],
            ["cache", random.choice(USERS)],
            ["analytics", random.choice(USERS), "events"],
        ]

    return random.choice(patterns)


def generate_memory(
    base_namespace: str | None = None,
    category: str | None = None,
    distribution: str = "mixed",
) -> dict[str, Any]:
    """Generate a single memory record."""
    ns = generate_namespace(base_namespace, distribution)
    key = f"mem_{generate_uuid()}"

    if category and category in GENERATORS:
        value = GENERATORS[category]()
    else:
        value = random.choice(list(GENERATORS.values()))()

    # Add common metadata
    created = generate_timestamp()
    value["created_at"] = created
    value["importance"] = round(random.uniform(0.1, 1.0), 2)

    # Optionally add tags
    if random.random() > 0.7:
        value["tags"] = random.sample(TOPICS, k=random.randint(1, 3))

    return {
        "namespace": ns,
        "key": key,
        "value": value,
        "created_at": created,
        "updated_at": created,
    }


def generate_memories_stream(
    count: int,
    base_namespace: str | None = None,
    category: str | None = None,
    distribution: str = "mixed",
) -> Iterator[dict[str, Any]]:
    """Generate memories as a stream (memory efficient for large datasets)."""
    for _ in range(count):
        yield generate_memory(base_namespace, category, distribution)


def write_jsonl(
    output: TextIO,
    count: int,
    base_namespace: str | None = None,
    category: str | None = None,
    distribution: str = "mixed",
    progress_interval: int = 100000,
    quiet: bool = False,
) -> int:
    """Write memories to a file-like object in JSONL format."""
    written = 0
    for memory in generate_memories_stream(count, base_namespace, category, distribution):
        output.write(json.dumps(memory) + "\n")
        written += 1

        if not quiet and progress_interval and written % progress_interval == 0:
            print(f"  Generated {written:,} / {count:,} memories...", file=sys.stderr)

    return written


def main():
    parser = argparse.ArgumentParser(
        description="Generate test memories for lgctl (outputs JSONL for import)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 1 million memories to file
  %(prog)s -n 1000000 -o memories.jsonl

  # Generate and import in one command
  %(prog)s -n 10000 | lgctl ops import --stdin --overwrite

  # Generate user-focused memories
  %(prog)s -n 100000 --distribution users -o users.jsonl

  # Generate only fact-type memories
  %(prog)s -n 50000 --category fact -o facts.jsonl

  # Generate in a specific namespace
  %(prog)s -n 10000 --namespace "test,experiment" -o test.jsonl

  # Import generated file
  lgctl ops import memories.jsonl --overwrite
        """,
    )

    parser.add_argument(
        "-n", "--count",
        type=int,
        default=1000,
        help="Number of memories to generate (default: 1000)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Fixed namespace for all memories (comma-separated)",
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=list(GENERATORS.keys()),
        default=None,
        help="Only generate memories of this category",
    )
    parser.add_argument(
        "--distribution",
        type=str,
        choices=["mixed", "users", "sessions", "projects", "flat"],
        default="mixed",
        help="Namespace distribution pattern (default: mixed)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible generation",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        if not args.quiet:
            print(f"Using random seed: {args.seed}", file=sys.stderr)

    if not args.quiet:
        print(f"Generating {args.count:,} memories...", file=sys.stderr)
        if args.namespace:
            print(f"  Namespace: {args.namespace}", file=sys.stderr)
        if args.category:
            print(f"  Category: {args.category}", file=sys.stderr)
        print(f"  Distribution: {args.distribution}", file=sys.stderr)

    # Determine progress interval based on count
    progress_interval = max(args.count // 10, 100000) if args.count > 100000 else 0

    if args.output:
        with open(args.output, "w") as f:
            written = write_jsonl(
                f, args.count, args.namespace, args.category,
                args.distribution, progress_interval, args.quiet
            )
        if not args.quiet:
            print(f"\nWrote {written:,} memories to {args.output}", file=sys.stderr)
            # Estimate file size
            import os
            size = os.path.getsize(args.output)
            if size > 1_000_000_000:
                print(f"File size: {size / 1_000_000_000:.2f} GB", file=sys.stderr)
            elif size > 1_000_000:
                print(f"File size: {size / 1_000_000:.2f} MB", file=sys.stderr)
            else:
                print(f"File size: {size / 1_000:.2f} KB", file=sys.stderr)
    else:
        # Write to stdout
        write_jsonl(
            sys.stdout, args.count, args.namespace, args.category,
            args.distribution, progress_interval, args.quiet
        )
        if not args.quiet:
            print(f"\nGenerated {args.count:,} memories to stdout", file=sys.stderr)


if __name__ == "__main__":
    main()
