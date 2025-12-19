"""
CLI dispatcher for lgctl.

Provides a Unix-style command interface with subcommands.

Usage:
    lgctl store ls
    lgctl store get user,123 preferences
    lgctl threads ls
    lgctl ops analyze
"""

import argparse
import asyncio
import json
import sys

from dotenv import load_dotenv

from .client import get_client
from .commands import (
    AssistantCommands,
    CronCommands,
    MemoryOps,
    RunCommands,
    StoreCommands,
    ThreadCommands,
)
from .formatters import get_formatter


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="lgctl",
        description="LangGraph Memory Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lgctl store ls                          # List namespaces
  lgctl store ls -i user,123              # List items in namespace
  lgctl store get user,123 prefs          # Get specific item
  lgctl store search user,123 "food"      # Semantic search
  lgctl store put user,123 pref "pizza"   # Store item

  lgctl threads ls                        # List threads
  lgctl threads state <thread_id>         # Get thread state

  lgctl ops analyze                       # Analyze memory usage
  lgctl ops stats                         # Memory statistics
  lgctl ops export -o backup.jsonl        # Export memories

  lgctl repl                              # Interactive mode
        """,
    )

    # Global options
    parser.add_argument("-u", "--url", help="LangGraph server URL (default: from env)")
    parser.add_argument("-k", "--api-key", help="API key (default: from LANGSMITH_API_KEY)")
    parser.add_argument(
        "-f",
        "--format",
        choices=["table", "json", "raw"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-essential output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Store commands
    store_parser = subparsers.add_parser("store", aliases=["s"], help="Store operations")
    store_sub = store_parser.add_subparsers(dest="subcommand")

    # store ls
    ls_parser = store_sub.add_parser("ls", help="List namespaces or items")
    ls_parser.add_argument("namespace", nargs="?", default="", help="Namespace prefix")
    ls_parser.add_argument("-d", "--depth", type=int, default=2, help="Max depth")
    ls_parser.add_argument("-n", "--limit", type=int, default=100, help="Max results")
    ls_parser.add_argument(
        "-i", "--items", action="store_true", help="List items instead of namespaces"
    )

    # store get
    get_parser = store_sub.add_parser("get", aliases=["cat"], help="Get an item")
    get_parser.add_argument("namespace", help="Namespace (e.g., user,123)")
    get_parser.add_argument("key", help="Item key")

    # store put
    put_parser = store_sub.add_parser("put", help="Store an item")
    put_parser.add_argument("namespace", help="Namespace")
    put_parser.add_argument("key", help="Item key")
    put_parser.add_argument("value", nargs="+", help="Value to store")
    put_parser.add_argument("-j", "--json", action="store_true", help="Parse value as JSON")

    # store rm
    rm_parser = store_sub.add_parser("rm", help="Delete an item")
    rm_parser.add_argument("namespace", help="Namespace")
    rm_parser.add_argument("key", help="Item key")

    # store search
    search_parser = store_sub.add_parser("search", help="Search items")
    search_parser.add_argument("namespace", nargs="?", default="", help="Namespace to search")
    search_parser.add_argument("query", nargs="?", default="", help="Search query")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="Max results")

    # store mv
    mv_parser = store_sub.add_parser("mv", help="Move/rename an item")
    mv_parser.add_argument("src_namespace", help="Source namespace")
    mv_parser.add_argument("src_key", help="Source key")
    mv_parser.add_argument("dst_namespace", help="Destination namespace")
    mv_parser.add_argument("dst_key", nargs="?", help="Destination key")

    # store cp
    cp_parser = store_sub.add_parser("cp", help="Copy an item")
    cp_parser.add_argument("src_namespace", help="Source namespace")
    cp_parser.add_argument("src_key", help="Source key")
    cp_parser.add_argument("dst_namespace", help="Destination namespace")
    cp_parser.add_argument("dst_key", nargs="?", help="Destination key")

    # store count
    count_parser = store_sub.add_parser("count", help="Count items")
    count_parser.add_argument("namespace", nargs="?", default="", help="Namespace")

    # store tree
    tree_parser = store_sub.add_parser("tree", help="Show namespace tree")
    tree_parser.add_argument("namespace", nargs="?", default="", help="Starting namespace")
    tree_parser.add_argument("-d", "--depth", type=int, default=10, help="Max depth")

    # Thread commands
    thread_parser = subparsers.add_parser("threads", aliases=["t"], help="Thread operations")
    thread_sub = thread_parser.add_subparsers(dest="subcommand")

    # threads ls
    tls_parser = thread_sub.add_parser("ls", help="List threads")
    tls_parser.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    tls_parser.add_argument("--status", help="Filter by status")

    # threads get
    tget_parser = thread_sub.add_parser("get", help="Get thread details")
    tget_parser.add_argument("thread_id", help="Thread ID")

    # threads create
    tcreate_parser = thread_sub.add_parser("create", help="Create thread")
    tcreate_parser.add_argument("--id", help="Optional thread ID")
    tcreate_parser.add_argument("--metadata", help="JSON metadata")

    # threads rm
    trm_parser = thread_sub.add_parser("rm", help="Delete thread")
    trm_parser.add_argument("thread_id", help="Thread ID")

    # threads state
    tstate_parser = thread_sub.add_parser("state", help="Get thread state")
    tstate_parser.add_argument("thread_id", help="Thread ID")
    tstate_parser.add_argument("--checkpoint", help="Checkpoint ID")

    # threads history
    thist_parser = thread_sub.add_parser("history", help="Get thread history")
    thist_parser.add_argument("thread_id", help="Thread ID")
    thist_parser.add_argument("-n", "--limit", type=int, default=10, help="Max entries")

    # Run commands
    run_parser = subparsers.add_parser("runs", aliases=["r"], help="Run operations")
    run_sub = run_parser.add_subparsers(dest="subcommand")

    # runs ls
    rls_parser = run_sub.add_parser("ls", help="List runs")
    rls_parser.add_argument("thread_id", help="Thread ID")
    rls_parser.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    rls_parser.add_argument("--status", help="Filter by status")

    # runs get
    rget_parser = run_sub.add_parser("get", help="Get run details")
    rget_parser.add_argument("thread_id", help="Thread ID")
    rget_parser.add_argument("run_id", help="Run ID")

    # runs cancel
    rcancel_parser = run_sub.add_parser("cancel", help="Cancel a run")
    rcancel_parser.add_argument("thread_id", help="Thread ID")
    rcancel_parser.add_argument("run_id", help="Run ID")

    # Assistant commands
    assist_parser = subparsers.add_parser("assistants", aliases=["a"], help="Assistant operations")
    assist_sub = assist_parser.add_subparsers(dest="subcommand")

    # assistants ls
    als_parser = assist_sub.add_parser("ls", help="List assistants")
    als_parser.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    als_parser.add_argument("--graph-id", help="Filter by graph ID")

    # assistants get
    aget_parser = assist_sub.add_parser("get", help="Get assistant details")
    aget_parser.add_argument("assistant_id", help="Assistant ID")

    # assistants schema
    aschema_parser = assist_sub.add_parser("schema", help="Get assistant schemas")
    aschema_parser.add_argument("assistant_id", help="Assistant ID")

    # assistants graph
    agraph_parser = assist_sub.add_parser("graph", help="Get assistant graph")
    agraph_parser.add_argument("assistant_id", help="Assistant ID")

    # Cron commands
    cron_parser = subparsers.add_parser("crons", aliases=["c"], help="Cron operations")
    cron_sub = cron_parser.add_subparsers(dest="subcommand")

    # crons ls
    cls_parser = cron_sub.add_parser("ls", help="List cron jobs")
    cls_parser.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    cls_parser.add_argument("--assistant-id", help="Filter by assistant")

    # crons get
    cget_parser = cron_sub.add_parser("get", help="Get cron details")
    cget_parser.add_argument("cron_id", help="Cron ID")

    # crons rm
    crm_parser = cron_sub.add_parser("rm", help="Delete cron job")
    crm_parser.add_argument("cron_id", help="Cron ID")

    # Operations commands
    ops_parser = subparsers.add_parser("ops", aliases=["o"], help="Memory operations")
    ops_sub = ops_parser.add_subparsers(dest="subcommand")

    # ops analyze
    analyze_parser = ops_sub.add_parser("analyze", help="Analyze memory usage")
    analyze_parser.add_argument("namespace", nargs="?", default="", help="Namespace")
    analyze_parser.add_argument("-d", "--detailed", action="store_true", help="Detailed analysis")

    # ops stats
    ops_sub.add_parser("stats", help="Memory statistics")

    # ops export
    export_parser = ops_sub.add_parser("export", help="Export memories")
    export_parser.add_argument("namespace", nargs="?", default="", help="Namespace to export")
    export_parser.add_argument("-o", "--output", help="Output file")
    export_parser.add_argument(
        "--export-format", choices=["jsonl", "json"], default="jsonl", help="Export file format"
    )
    export_parser.add_argument("-k", "--key", help="Only export keys containing this string")
    export_parser.add_argument("-v", "--value", help="Only export values containing this string")

    # ops import
    import_parser = ops_sub.add_parser("import", help="Import memories")
    import_parser.add_argument("input_file", nargs="?", help="Input file (omit for stdin)")
    import_parser.add_argument("--prefix", default="", help="Namespace prefix")
    import_parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    import_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing")
    import_parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    import_parser.add_argument(
        "--batch-size", type=int, default=100, help="Batch size for processing (default: 100)"
    )

    # ops prune
    prune_parser = ops_sub.add_parser("prune", help="Prune old memories")
    prune_parser.add_argument("namespace", help="Namespace to prune")
    prune_parser.add_argument("--days", type=int, help="Remove items older than N days")
    prune_parser.add_argument("--before", help="Remove items before timestamp")
    prune_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Don't actually delete"
    )
    prune_parser.add_argument("--force", action="store_true", help="Actually delete")

    # ops dedupe
    dedupe_parser = ops_sub.add_parser("dedupe", help="Remove duplicates")
    dedupe_parser.add_argument("namespace", help="Namespace to dedupe")
    dedupe_parser.add_argument("--dry-run", action="store_true", default=True)
    dedupe_parser.add_argument("--force", action="store_true")

    # ops find
    find_parser = ops_sub.add_parser("find", help="Find memories")
    find_parser.add_argument("namespace", nargs="?", default="", help="Namespace")
    find_parser.add_argument("-k", "--key", help="Key pattern")
    find_parser.add_argument("-v", "--value", help="Value contains")
    find_parser.add_argument("-n", "--limit", type=int, default=100)

    # ops grep
    grep_parser = ops_sub.add_parser("grep", help="Search memory values")
    grep_parser.add_argument("pattern", help="Search pattern")
    grep_parser.add_argument("namespace", nargs="?", default="", help="Namespace")
    grep_parser.add_argument("-n", "--limit", type=int, default=100)

    # ops fix-values
    fix_parser = ops_sub.add_parser(
        "fix-values", help="Fix malformed values with double-escaped JSON"
    )
    fix_parser.add_argument("namespace", nargs="?", default="", help="Namespace (empty for all)")
    fix_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Show what would be fixed"
    )
    fix_parser.add_argument("--force", action="store_true", help="Actually fix the values")

    # REPL command
    subparsers.add_parser("repl", help="Interactive REPL mode")

    return parser


async def run_command(args: argparse.Namespace) -> int:
    """Run the specified command."""
    load_dotenv()

    client = get_client(url=args.url, api_key=args.api_key)
    formatter = get_formatter(args.format)

    try:
        if args.command in ("store", "s"):
            store = StoreCommands(client, formatter)

            if args.subcommand == "ls":
                result = await store.ls(
                    namespace=args.namespace,
                    max_depth=args.depth,
                    limit=args.limit,
                    show_items=args.items,
                )
                formatter.print_list(result)

            elif args.subcommand in ("get", "cat"):
                result = await store.get(args.namespace, args.key)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Item not found: {args.namespace}/{args.key}")
                    return 1

            elif args.subcommand == "put":
                value = " ".join(args.value)
                if args.json:
                    value = json.loads(value)
                result = await store.put(args.namespace, args.key, value)
                formatter.print_success(f"Stored {args.namespace}/{args.key}")

            elif args.subcommand == "rm":
                result = await store.rm(args.namespace, args.key)
                formatter.print_success(f"Deleted {args.namespace}/{args.key}")

            elif args.subcommand == "search":
                result = await store.search(
                    namespace=args.namespace, query=args.query, limit=args.limit
                )
                formatter.print_list(result)

            elif args.subcommand == "mv":
                result = await store.mv(
                    args.src_namespace, args.src_key, args.dst_namespace, args.dst_key
                )
                formatter.print_success(
                    f"Moved to {args.dst_namespace}/{args.dst_key or args.src_key}"
                )

            elif args.subcommand == "cp":
                result = await store.cp(
                    args.src_namespace, args.src_key, args.dst_namespace, args.dst_key
                )
                formatter.print_success(
                    f"Copied to {args.dst_namespace}/{args.dst_key or args.src_key}"
                )

            elif args.subcommand == "count":
                result = await store.count(args.namespace)
                formatter.print_item(result)

            elif args.subcommand == "tree":
                result = await store.tree(args.namespace, args.depth)
                for item in result:
                    print(item["tree"])

            else:
                print("Usage: lgctl store <ls|get|put|rm|search|mv|cp|count|tree>")
                return 1

        elif args.command in ("threads", "t"):
            threads = ThreadCommands(client, formatter)

            if args.subcommand == "ls":
                result = await threads.ls(limit=args.limit, status=args.status)
                formatter.print_list(result)

            elif args.subcommand == "get":
                result = await threads.get(args.thread_id)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Thread not found: {args.thread_id}")
                    return 1

            elif args.subcommand == "create":
                metadata = json.loads(args.metadata) if args.metadata else None
                result = await threads.create(thread_id=args.id, metadata=metadata)
                formatter.print_item(result)

            elif args.subcommand == "rm":
                result = await threads.rm(args.thread_id)
                formatter.print_success(f"Deleted thread {args.thread_id}")

            elif args.subcommand == "state":
                result = await threads.state(args.thread_id, checkpoint_id=args.checkpoint)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Thread not found: {args.thread_id}")
                    return 1

            elif args.subcommand == "history":
                result = await threads.history(args.thread_id, limit=args.limit)
                formatter.print_list(result)

            else:
                print("Usage: lgctl threads <ls|get|create|rm|state|history>")
                return 1

        elif args.command in ("runs", "r"):
            runs = RunCommands(client, formatter)

            if args.subcommand == "ls":
                result = await runs.ls(args.thread_id, limit=args.limit, status=args.status)
                formatter.print_list(result)

            elif args.subcommand == "get":
                result = await runs.get(args.thread_id, args.run_id)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Run not found: {args.run_id}")
                    return 1

            elif args.subcommand == "cancel":
                result = await runs.cancel(args.thread_id, args.run_id)
                formatter.print_success(f"Cancelled run {args.run_id}")

            else:
                print("Usage: lgctl runs <ls|get|cancel>")
                return 1

        elif args.command in ("assistants", "a"):
            assistants = AssistantCommands(client, formatter)

            if args.subcommand == "ls":
                result = await assistants.ls(graph_id=args.graph_id, limit=args.limit)
                formatter.print_list(result)

            elif args.subcommand == "get":
                result = await assistants.get(args.assistant_id)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Assistant not found: {args.assistant_id}")
                    return 1

            elif args.subcommand == "schema":
                result = await assistants.schema(args.assistant_id)
                print(json.dumps(result, indent=2))

            elif args.subcommand == "graph":
                result = await assistants.graph(args.assistant_id)
                print(json.dumps(result, indent=2))

            else:
                print("Usage: lgctl assistants <ls|get|schema|graph>")
                return 1

        elif args.command in ("crons", "c"):
            crons = CronCommands(client, formatter)

            if args.subcommand == "ls":
                result = await crons.ls(assistant_id=args.assistant_id, limit=args.limit)
                formatter.print_list(result)

            elif args.subcommand == "get":
                result = await crons.get(args.cron_id)
                if result:
                    formatter.print_item(result)
                else:
                    formatter.print_error(f"Cron not found: {args.cron_id}")
                    return 1

            elif args.subcommand == "rm":
                result = await crons.rm(args.cron_id)
                formatter.print_success(f"Deleted cron {args.cron_id}")

            else:
                print("Usage: lgctl crons <ls|get|rm>")
                return 1

        elif args.command in ("ops", "o"):
            ops = MemoryOps(client, formatter)

            if args.subcommand == "analyze":
                result = await ops.analyze(args.namespace, detailed=args.detailed)
                if args.format == "json":
                    print(json.dumps(result, indent=2, default=str))
                else:
                    print(f"\nMemory Analysis: {result['namespace']}")
                    print(f"Total namespaces: {result['total_namespaces']}")
                    print(f"Total items: {result['total_items']}")
                    if result.get("largest_namespace"):
                        print(f"Largest namespace: {result['largest_namespace']}")
                    print("\nNamespace breakdown:")
                    for ns in result["namespaces"][:20]:
                        print(f"  {ns['namespace']}: {ns.get('item_count', 'N/A')} items")

            elif args.subcommand == "stats":
                result = await ops.stats()
                formatter.print_item(result)

            elif args.subcommand == "export":
                result = await ops.export(
                    namespace=args.namespace,
                    output_file=args.output,
                    format=args.export_format,
                    key_pattern=args.key,
                    value_contains=args.value,
                )
                if args.output:
                    formatter.print_success(f"Exported {result['exported']} items to {args.output}")
                else:
                    print(result.get("data", ""))

            elif args.subcommand == "import":
                use_stdin = args.stdin or not args.input_file
                if not use_stdin and not args.input_file:
                    formatter.print_error("Either provide input_file or use --stdin")
                    return 1

                # Progress callback for large imports
                last_report = [0]

                def progress(processed: int, total: int) -> None:
                    if total >= 10000 and processed - last_report[0] >= 10000:
                        print(f"  Processed {processed:,} / {total:,} items...", file=sys.stderr)
                        last_report[0] = processed

                result = await ops.import_(
                    input_file=args.input_file,
                    namespace_prefix=args.prefix,
                    dry_run=args.dry_run,
                    overwrite=args.overwrite,
                    batch_size=args.batch_size,
                    stdin=use_stdin,
                    progress_callback=progress if not args.quiet else None,
                )
                formatter.print_item(result)

            elif args.subcommand == "prune":
                result = await ops.prune(
                    namespace=args.namespace,
                    days_old=args.days,
                    before=args.before,
                    dry_run=not args.force,
                )
                formatter.print_item(result)

            elif args.subcommand == "dedupe":
                result = await ops.dedupe(namespace=args.namespace, dry_run=not args.force)
                formatter.print_item(result)

            elif args.subcommand == "find":
                result = await ops.find(
                    namespace=args.namespace,
                    key_pattern=args.key,
                    value_contains=args.value,
                    limit=args.limit,
                )
                formatter.print_list(result)

            elif args.subcommand == "grep":
                result = await ops.grep(
                    pattern=args.pattern, namespace=args.namespace, limit=args.limit
                )
                formatter.print_list(result)

            elif args.subcommand == "fix-values":
                result = await ops.fix_values(
                    namespace=args.namespace,
                    dry_run=not args.force,
                )
                formatter.print_item(result)
                if result.get("samples"):
                    print("\nSample fixes:")
                    for sample in result["samples"]:
                        print(f"  {sample['namespace']}/{sample['key']}")
                        print(f"    Before: {sample['before']}")
                        print(f"    After:  {sample['after']}")

            else:
                print(
                    "Usage: lgctl ops <analyze|stats|export|import|prune|dedupe|find|grep|fix-values>"
                )
                return 1

        elif args.command == "repl":
            from .repl import REPL

            repl = REPL(client, formatter)
            await repl.run()

        else:
            parser = create_parser()
            parser.print_help()
            return 1

        return 0

    except Exception as e:
        formatter.print_error(str(e))
        return 1


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    exit_code = asyncio.run(run_command(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
