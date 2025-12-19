"""
Interactive REPL for lgctl.

Provides an interactive shell with command completion,
history, and contextual navigation.
"""

import json
import shlex
from typing import Optional

from .client import LGCtlClient
from .commands import (
    AssistantCommands,
    CronCommands,
    MemoryOps,
    RunCommands,
    StoreCommands,
    ThreadCommands,
)
from .formatters import Formatter


class REPL:
    """
    Interactive REPL for lgctl.

    Features:
    - Context-aware prompts
    - Namespace navigation (cd/use)
    - Short command aliases
    - History
    """

    HELP = """
lgctl REPL - Interactive Memory Management
═══════════════════════════════════════════

Navigation:
  use <ns>          Set working namespace (e.g., use user,123)
  pwd               Show current namespace
  cd <ns>           Alias for use
  ..                Go up one namespace level

Store Commands:
  ls [ns] [-i]      List namespaces (or items with -i)
  get <ns> <key>    Get item (or just <key> if namespace set)
  put <ns> <k> <v>  Store item
  rm <ns> <key>     Delete item
  search [ns] <q>   Semantic search
  cat <ns> <key>    Alias for get
  count [ns]        Count items
  tree [ns]         Show namespace tree

Thread Commands:
  threads           List threads
  thread <id>       Get thread details
  state <id>        Get thread state
  history <id>      Get thread history

Assistant Commands:
  assistants        List assistants
  assistant <id>    Get assistant details

Run Commands:
  runs <thread_id>  List runs for thread
  run <tid> <rid>   Get run details

Memory Operations:
  analyze [ns]      Analyze memory usage
  stats             Memory statistics
  find [ns] -k/-v   Find by key/value pattern
  grep <pattern>    Search all values

Utility:
  export [ns] [file]  Export memories
  clear               Clear screen
  help                Show this help
  exit/quit           Exit REPL

Shortcuts:
  s <q>             Quick search in current namespace
  l                 ls in current namespace
  g <key>           get in current namespace

Format: lgctl> or [namespace]> when namespace is set
"""

    def __init__(
        self,
        client: LGCtlClient,
        formatter: Formatter,
    ):
        self.client = client
        self.formatter = formatter
        self.current_namespace: Optional[str] = None

        # Initialize command handlers
        self.store = StoreCommands(client, formatter)
        self.threads_cmd = ThreadCommands(client, formatter)
        self.runs_cmd = RunCommands(client, formatter)
        self.assistants_cmd = AssistantCommands(client, formatter)
        self.crons_cmd = CronCommands(client, formatter)
        self.ops = MemoryOps(client, formatter)

    def _prompt(self) -> str:
        """Generate the prompt string."""
        if self.current_namespace:
            return f"[{self.current_namespace}]> "
        return "lgctl> "

    def _resolve_namespace(self, ns: Optional[str] = None) -> str:
        """Resolve namespace, using current if not provided."""
        if ns:
            if ns == "..":
                # Go up one level
                if self.current_namespace:
                    parts = self.current_namespace.split(",")
                    if len(parts) > 1:
                        return ",".join(parts[:-1])
                return ""
            return ns
        return self.current_namespace or ""

    async def _handle_command(self, line: str) -> bool:
        """
        Handle a single command.

        Returns:
            False if should exit, True otherwise
        """
        line = line.strip()
        if not line:
            return True

        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()

        cmd = parts[0].lower()
        args = parts[1:]

        try:
            # Exit commands
            if cmd in ("exit", "quit", "q"):
                return False

            # Help
            elif cmd in ("help", "h", "?"):
                print(self.HELP)

            # Clear screen
            elif cmd == "clear":
                print("\033[H\033[J", end="")

            # Navigation
            elif cmd in ("use", "cd"):
                if args:
                    ns = args[0]
                    if ns == "..":
                        ns = self._resolve_namespace("..")
                    if ns == "" or ns == "/":
                        self.current_namespace = None
                        print("Namespace cleared (root)")
                    else:
                        self.current_namespace = ns
                        print(f"Namespace: {ns}")
                else:
                    self.current_namespace = None
                    print("Namespace cleared (root)")

            elif cmd == "pwd":
                print(self.current_namespace or "(root)")

            elif cmd == "..":
                self.current_namespace = self._resolve_namespace("..") or None
                print(f"Namespace: {self.current_namespace or '(root)'}")

            # Store commands
            elif cmd in ("ls", "l"):
                show_items = "-i" in args
                args = [a for a in args if a != "-i"]
                ns = args[0] if args else self._resolve_namespace()
                result = await self.store.ls(namespace=ns, show_items=show_items)
                self.formatter.print_list(result)

            elif cmd in ("get", "cat", "g"):
                if len(args) >= 2:
                    ns, key = args[0], args[1]
                elif len(args) == 1 and self.current_namespace:
                    ns, key = self.current_namespace, args[0]
                else:
                    print("Usage: get <namespace> <key> or get <key> (with namespace set)")
                    return True

                result = await self.store.get(ns, key)
                if result:
                    self.formatter.print_item(result)
                else:
                    print(f"Not found: {ns}/{key}")

            elif cmd == "put":
                if len(args) >= 3:
                    ns, key = args[0], args[1]
                    value = " ".join(args[2:])
                elif len(args) >= 2 and self.current_namespace:
                    ns = self.current_namespace
                    key, value = args[0], " ".join(args[1:])
                else:
                    print("Usage: put <namespace> <key> <value>")
                    return True

                # Try to parse as JSON, fall back to string
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass

                await self.store.put(ns, key, value)
                print(f"ok: stored {ns}/{key}")

            elif cmd == "rm":
                if len(args) >= 2:
                    ns, key = args[0], args[1]
                elif len(args) == 1 and self.current_namespace:
                    ns, key = self.current_namespace, args[0]
                else:
                    print("Usage: rm <namespace> <key>")
                    return True

                await self.store.rm(ns, key)
                print(f"ok: deleted {ns}/{key}")

            elif cmd in ("search", "s"):
                if self.current_namespace and (len(args) == 0 or "," not in args[0]):
                    ns = self.current_namespace
                    query = " ".join(args)
                elif args:
                    ns = args[0]
                    query = " ".join(args[1:]) if len(args) > 1 else ""
                else:
                    ns = ""
                    query = ""

                result = await self.store.search(namespace=ns, query=query)
                self.formatter.print_list(result)

            elif cmd == "count":
                ns = args[0] if args else self._resolve_namespace()
                result = await self.store.count(ns)
                print(f"{result['namespace']}: {result['count']} items")

            elif cmd == "tree":
                ns = args[0] if args else self._resolve_namespace()
                result = await self.store.tree(ns)
                for item in result:
                    print(item["tree"])

            # Thread commands
            elif cmd == "threads":
                limit = int(args[0]) if args else 20
                result = await self.threads_cmd.ls(limit=limit)
                self.formatter.print_list(result)

            elif cmd == "thread":
                if not args:
                    print("Usage: thread <thread_id>")
                    return True
                result = await self.threads_cmd.get(args[0])
                if result:
                    self.formatter.print_item(result)
                else:
                    print(f"Thread not found: {args[0]}")

            elif cmd == "state":
                if not args:
                    print("Usage: state <thread_id>")
                    return True
                result = await self.threads_cmd.state(args[0])
                if result:
                    self.formatter.print_item(result)
                else:
                    print(f"Thread not found: {args[0]}")

            elif cmd == "history":
                if not args:
                    print("Usage: history <thread_id>")
                    return True
                limit = int(args[1]) if len(args) > 1 else 10
                result = await self.threads_cmd.history(args[0], limit=limit)
                self.formatter.print_list(result)

            # Assistant commands
            elif cmd == "assistants":
                result = await self.assistants_cmd.ls()
                self.formatter.print_list(result)

            elif cmd == "assistant":
                if not args:
                    print("Usage: assistant <assistant_id>")
                    return True
                result = await self.assistants_cmd.get(args[0])
                if result:
                    self.formatter.print_item(result)
                else:
                    print(f"Assistant not found: {args[0]}")

            # Run commands
            elif cmd == "runs":
                if not args:
                    print("Usage: runs <thread_id>")
                    return True
                result = await self.runs_cmd.ls(args[0])
                self.formatter.print_list(result)

            elif cmd == "run":
                if len(args) < 2:
                    print("Usage: run <thread_id> <run_id>")
                    return True
                result = await self.runs_cmd.get(args[0], args[1])
                if result:
                    self.formatter.print_item(result)
                else:
                    print(f"Run not found: {args[1]}")

            # Memory operations
            elif cmd == "analyze":
                ns = args[0] if args else self._resolve_namespace()
                detailed = "-d" in args or "--detailed" in args
                result = await self.ops.analyze(ns, detailed=detailed)
                print(f"\nMemory Analysis: {result['namespace']}")
                print(f"Total namespaces: {result['total_namespaces']}")
                print(f"Total items: {result['total_items']}")
                if result.get("largest_namespace"):
                    print(f"Largest namespace: {result['largest_namespace']}")
                print("\nNamespace breakdown:")
                for ns_info in result["namespaces"][:20]:
                    print(f"  {ns_info['namespace']}: {ns_info.get('item_count', 'N/A')} items")

            elif cmd == "stats":
                result = await self.ops.stats()
                self.formatter.print_item(result)

            elif cmd == "find":
                ns = ""
                key_pattern = None
                value_contains = None

                i = 0
                while i < len(args):
                    if args[i] == "-k" and i + 1 < len(args):
                        key_pattern = args[i + 1]
                        i += 2
                    elif args[i] == "-v" and i + 1 < len(args):
                        value_contains = args[i + 1]
                        i += 2
                    else:
                        ns = args[i]
                        i += 1

                ns = ns or self._resolve_namespace()
                result = await self.ops.find(
                    namespace=ns, key_pattern=key_pattern, value_contains=value_contains
                )
                self.formatter.print_list(result)

            elif cmd == "grep":
                if not args:
                    print("Usage: grep <pattern> [namespace]")
                    return True
                pattern = args[0]
                ns = args[1] if len(args) > 1 else self._resolve_namespace()
                result = await self.ops.grep(pattern, namespace=ns)
                self.formatter.print_list(result)

            elif cmd == "export":
                ns = ""
                output_file = None

                for arg in args:
                    if "." in arg and "," not in arg:
                        output_file = arg
                    else:
                        ns = arg

                ns = ns or self._resolve_namespace()
                result = await self.ops.export(namespace=ns, output_file=output_file)
                if output_file:
                    print(f"Exported {result['exported']} items to {output_file}")
                else:
                    print(result.get("data", ""))

            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")

        except Exception as e:
            print(f"Error: {e}")

        return True

    async def run(self):
        """Run the interactive REPL."""
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                lgctl - Memory Management REPL              ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print(f"\nConnected to: {self.client.url}")
        mode = "remote" if self.client.is_remote() else "local"
        print(f"Mode: {mode}")
        print("\nType 'help' for commands, 'exit' to quit.\n")

        while True:
            try:
                line = input(self._prompt())
                should_continue = await self._handle_command(line)
                if not should_continue:
                    print("Goodbye!")
                    break
            except KeyboardInterrupt:
                print("\n(Use 'exit' to quit)")
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
