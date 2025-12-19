"""
Higher-level memory operations for lgctl.

These operations combine multiple low-level commands to provide
useful workflows for managing memory at scale.

Unix philosophy: compose simple commands into powerful pipelines.
"""

import json
from datetime import datetime, timedelta
from typing import Callable, Dict, Iterator, List, Optional

from ..client import LGCtlClient
from ..formatters import Formatter
from .store import StoreCommands, format_namespace, parse_namespace


class MemoryOps:
    """
    Higher-level memory management operations.

    Operations:
        analyze     - analyze memory usage and patterns
        prune       - remove old/unused memories
        export      - export memories to file
        import_     - import memories from file
        dedupe      - find and remove duplicate entries
        migrate     - migrate memories between namespaces
        search_all  - deep search across all namespaces
        stats       - memory statistics
        diff        - compare two memory snapshots
        find        - find memories matching criteria
        grep        - search memory values with pattern
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter
        self.store = StoreCommands(client, formatter)

    async def analyze(self, namespace: str = "", detailed: bool = False) -> Dict:
        """
        Analyze memory usage and patterns.

        Args:
            namespace: Namespace to analyze (empty for all)
            detailed: Include detailed item analysis

        Returns:
            Analysis report
        """
        ns_tuple = parse_namespace(namespace)

        # Get all namespaces
        response = await self.client.store.list_namespaces(
            prefix=list(ns_tuple), max_depth=10, limit=1000
        )
        # Handle different response formats from the API
        if isinstance(response, dict):
            namespaces = response.get("namespaces", [])
        else:
            namespaces = response

        report = {
            "namespace": format_namespace(ns_tuple) if namespace else "(all)",
            "total_namespaces": len(namespaces),
            "namespaces": [],
            "total_items": 0,
            "analyzed_at": datetime.now().isoformat(),
        }

        # Analyze each namespace
        for ns in namespaces:
            ns_info = {
                "namespace": format_namespace(ns),
                "depth": len(ns),
            }

            # Count items
            results = await self.client.store.search_items(
                tuple(ns) if isinstance(ns, list) else ns, limit=10000
            )
            items = results.get("items", [])
            ns_info["item_count"] = len(items)
            report["total_items"] += len(items)

            if detailed and items:
                # Analyze item patterns
                keys = [i.get("key", "") for i in items]
                ns_info["sample_keys"] = keys[:5]

                # Size estimate
                total_size = sum(len(json.dumps(i.get("value", {}))) for i in items)
                ns_info["approx_size_bytes"] = total_size

                # Timestamps
                timestamps = [i.get("updated_at") for i in items if i.get("updated_at")]
                if timestamps:
                    ns_info["oldest"] = min(timestamps)
                    ns_info["newest"] = max(timestamps)

            report["namespaces"].append(ns_info)

        # Summary
        if report["namespaces"]:
            report["largest_namespace"] = max(
                report["namespaces"], key=lambda x: x.get("item_count", 0)
            )["namespace"]

        return report

    async def prune(
        self,
        namespace: str,
        before: Optional[str] = None,
        days_old: Optional[int] = None,
        dry_run: bool = True,
        filter_fn: Optional[Callable[[Dict], bool]] = None,
    ) -> Dict:
        """
        Remove old or unused memories.

        Args:
            namespace: Namespace to prune
            before: Remove items updated before this timestamp
            days_old: Remove items older than N days
            dry_run: If True, show what would be deleted without deleting
            filter_fn: Custom filter function (return True to delete)

        Returns:
            Pruning report
        """
        ns_tuple = parse_namespace(namespace)

        # Determine cutoff
        if days_old:
            cutoff = datetime.now() - timedelta(days=days_old)
            before = cutoff.isoformat()

        results = await self.client.store.search_items(ns_tuple, limit=10000)
        items = results.get("items", [])

        to_delete = []
        for item in items:
            should_delete = False

            if before and item.get("updated_at"):
                if item["updated_at"] < before:
                    should_delete = True

            if filter_fn and filter_fn(item):
                should_delete = True

            if should_delete:
                to_delete.append(item)

        report = {
            "namespace": format_namespace(ns_tuple),
            "total_items": len(items),
            "to_delete": len(to_delete),
            "dry_run": dry_run,
            "items": [
                {"key": i.get("key"), "updated_at": i.get("updated_at")}
                for i in to_delete[:20]  # Show first 20
            ],
        }

        if not dry_run:
            deleted = 0
            for item in to_delete:
                try:
                    await self.client.store.delete_item(
                        tuple(item.get("namespace", [])), item.get("key")
                    )
                    deleted += 1
                except Exception:
                    pass
            report["deleted"] = deleted

        return report

    async def export(
        self,
        namespace: str = "",
        output_file: Optional[str] = None,
        format: str = "jsonl",
        key_pattern: Optional[str] = None,
        value_contains: Optional[str] = None,
    ) -> Dict:
        """
        Export memories to a file.

        Args:
            namespace: Namespace to export (empty for all)
            output_file: Output file path (prints to stdout if None)
            format: Output format (jsonl, json)
            key_pattern: Only export items with keys containing this string
            value_contains: Only export items with values containing this string

        Returns:
            Export summary
        """
        ns_tuple = parse_namespace(namespace)

        results = await self.client.store.search_items(ns_tuple, limit=100000)
        items = results.get("items", [])

        export_data = []
        skipped = 0
        for item in items:
            # Apply key filter
            if key_pattern and key_pattern not in item.get("key", ""):
                skipped += 1
                continue

            # Apply value filter
            if value_contains:
                value_str = json.dumps(item.get("value", {}))
                if value_contains.lower() not in value_str.lower():
                    skipped += 1
                    continue

            export_data.append(
                {
                    "namespace": item.get("namespace"),
                    "key": item.get("key"),
                    "value": item.get("value"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )

        if output_file:
            with open(output_file, "w") as f:
                if format == "jsonl":
                    for item in export_data:
                        f.write(json.dumps(item) + "\n")
                else:
                    json.dump(export_data, f, indent=2, default=str)
        else:
            # Return data for stdout
            if format == "jsonl":
                return {
                    "exported": len(export_data),
                    "data": "\n".join(json.dumps(i, default=str) for i in export_data),
                }
            else:
                return {
                    "exported": len(export_data),
                    "data": export_data,
                }

        return {
            "exported": len(export_data),
            "file": output_file,
            "format": format,
        }

    async def import_(
        self,
        input_file: Optional[str] = None,
        namespace_prefix: str = "",
        dry_run: bool = True,
        overwrite: bool = False,
        batch_size: int = 100,
        stdin: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict:
        """
        Import memories from a file or stdin.

        Optimized for importing millions of records with batching.

        Args:
            input_file: Input file path (None if using stdin)
            namespace_prefix: Prefix to add to all namespaces
            dry_run: If True, show what would be imported
            overwrite: If True, overwrite existing items (skips existence check)
            batch_size: Number of items to process per batch
            stdin: Read from stdin instead of file
            progress_callback: Optional callback(processed, total) for progress

        Returns:
            Import summary
        """
        import sys

        prefix_tuple = parse_namespace(namespace_prefix)

        report = {
            "file": input_file or "(stdin)",
            "total_items": 0,
            "dry_run": dry_run,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
        }

        async def process_item(item: Dict) -> str:
            """Process a single item, returns status: 'imported', 'skipped', or 'error'."""
            ns = item.get("namespace", [])
            if isinstance(ns, str):
                ns = parse_namespace(ns)
            else:
                ns = tuple(ns)

            # Add prefix
            if prefix_tuple:
                ns = prefix_tuple + ns

            key = item.get("key")
            value = item.get("value")

            if dry_run:
                return "imported"

            try:
                # Skip existence check if overwriting (much faster for bulk imports)
                if not overwrite:
                    existing = await self.client.store.get_item(ns, key)
                    if existing:
                        return "skipped"

                await self.client.store.put_item(ns, key, value)
                return "imported"
            except Exception:
                return "error"

        async def process_batch(batch: List[Dict]) -> None:
            """Process a batch of items."""
            for item in batch:
                status = await process_item(item)
                if status == "imported":
                    report["imported"] += 1
                elif status == "skipped":
                    report["skipped"] += 1
                else:
                    report["errors"] += 1

        def iter_items(file_handle) -> Iterator[Dict]:
            """Iterate over items from file handle (supports JSON array or JSONL)."""
            first_char = file_handle.read(1)
            if not first_char:
                return

            if first_char == "[":
                # JSON array - read all at once
                file_handle.seek(0)
                items = json.load(file_handle)
                yield from items
            else:
                # JSONL - stream line by line
                file_handle.seek(0)
                for line in file_handle:
                    line = line.strip()
                    if line:
                        yield json.loads(line)

        # Process from stdin or file
        if stdin:
            source = sys.stdin
        else:
            source = open(input_file, "r")

        try:
            batch = []
            for item in iter_items(source):
                report["total_items"] += 1
                batch.append(item)

                if len(batch) >= batch_size:
                    await process_batch(batch)
                    if progress_callback:
                        progress_callback(
                            report["imported"] + report["skipped"] + report["errors"],
                            report["total_items"],
                        )
                    batch = []

            # Process remaining items
            if batch:
                await process_batch(batch)
                if progress_callback:
                    progress_callback(
                        report["imported"] + report["skipped"] + report["errors"],
                        report["total_items"],
                    )
        finally:
            if not stdin and source:
                source.close()

        return report

    async def dedupe(
        self, namespace: str, key_fn: Optional[Callable[[Dict], str]] = None, dry_run: bool = True
    ) -> Dict:
        """
        Find and remove duplicate entries.

        Args:
            namespace: Namespace to dedupe
            key_fn: Function to generate dedup key from value
            dry_run: If True, show dupes without deleting

        Returns:
            Deduplication report
        """
        ns_tuple = parse_namespace(namespace)

        results = await self.client.store.search_items(ns_tuple, limit=10000)
        items = results.get("items", [])

        # Group by dedup key
        seen = {}
        duplicates = []

        for item in items:
            if key_fn:
                dedup_key = key_fn(item.get("value", {}))
            else:
                # Default: hash the value
                dedup_key = json.dumps(item.get("value", {}), sort_keys=True)

            if dedup_key in seen:
                duplicates.append(item)
            else:
                seen[dedup_key] = item

        report = {
            "namespace": format_namespace(ns_tuple),
            "total_items": len(items),
            "unique_items": len(seen),
            "duplicates": len(duplicates),
            "dry_run": dry_run,
            "duplicate_keys": [d.get("key") for d in duplicates[:20]],
        }

        if not dry_run:
            deleted = 0
            for item in duplicates:
                try:
                    await self.client.store.delete_item(
                        tuple(item.get("namespace", [])), item.get("key")
                    )
                    deleted += 1
                except Exception:
                    pass
            report["deleted"] = deleted

        return report

    async def search_all(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Deep search across all namespaces.

        Args:
            query: Search query
            limit: Max results per namespace

        Returns:
            All matching items
        """
        # Get all namespaces
        response = await self.client.store.list_namespaces(prefix=[], max_depth=10, limit=1000)
        # Handle different response formats from the API
        if isinstance(response, dict):
            namespaces = response.get("namespaces", [])
        else:
            namespaces = response

        all_results = []

        for ns in namespaces:
            ns_tuple = tuple(ns) if isinstance(ns, list) else ns
            try:
                results = await self.client.store.search_items(ns_tuple, query=query, limit=limit)
                for item in results.get("items", []):
                    all_results.append(
                        {
                            "namespace": format_namespace(item.get("namespace", [])),
                            "key": item.get("key"),
                            "value": item.get("value"),
                            "score": item.get("score"),
                        }
                    )
            except Exception:
                pass

        # Sort by score if available (handle None scores)
        all_results.sort(key=lambda x: x.get("score") or 0, reverse=True)
        return all_results[: limit * 2]

    async def stats(self) -> Dict:
        """
        Get overall memory statistics.

        Returns:
            Statistics summary
        """
        response = await self.client.store.list_namespaces(prefix=[], max_depth=10, limit=1000)
        # Handle different response formats from the API
        if isinstance(response, dict):
            namespaces = response.get("namespaces", [])
        else:
            namespaces = response

        total_items = 0
        total_size = 0

        for ns in namespaces:
            ns_tuple = tuple(ns) if isinstance(ns, list) else ns
            try:
                results = await self.client.store.search_items(ns_tuple, limit=10000)
                items = results.get("items", [])
                total_items += len(items)
                total_size += sum(len(json.dumps(i.get("value", {}))) for i in items)
            except Exception:
                pass

        return {
            "total_namespaces": len(namespaces),
            "total_items": total_items,
            "approx_size_bytes": total_size,
            "approx_size_mb": round(total_size / (1024 * 1024), 2),
            "generated_at": datetime.now().isoformat(),
        }

    async def find(
        self,
        namespace: str = "",
        key_pattern: Optional[str] = None,
        value_contains: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Find memories matching criteria.

        Args:
            namespace: Namespace to search
            key_pattern: Key must contain this string
            value_contains: Value must contain this string
            limit: Max results

        Returns:
            Matching items
        """
        ns_tuple = parse_namespace(namespace)

        results = await self.client.store.search_items(ns_tuple, limit=10000)
        items = results.get("items", [])

        matches = []
        for item in items:
            if key_pattern and key_pattern not in item.get("key", ""):
                continue

            if value_contains:
                value_str = json.dumps(item.get("value", {}))
                if value_contains.lower() not in value_str.lower():
                    continue

            matches.append(
                {
                    "namespace": format_namespace(item.get("namespace", [])),
                    "key": item.get("key"),
                    "value": item.get("value"),
                }
            )

            if len(matches) >= limit:
                break

        return matches

    async def fix_values(
        self,
        namespace: str = "",
        dry_run: bool = True,
    ) -> Dict:
        """
        Fix malformed values that have double-escaped JSON.

        Detects and fixes patterns like:
            {"value": "{\"name\": \"...\"}"}  ->  {"name": "..."}

        This commonly happens when JSON is stored as an escaped string
        inside a wrapper object, breaking semantic search.

        Args:
            namespace: Namespace to fix (empty for all)
            dry_run: If True, show what would be fixed without fixing

        Returns:
            Fix report with counts and sample fixes
        """
        ns_tuple = parse_namespace(namespace)

        # Get all namespaces to process
        if namespace:
            namespaces_to_check = [ns_tuple]
        else:
            response = await self.client.store.list_namespaces(prefix=[], max_depth=10, limit=1000)
            if isinstance(response, dict):
                namespaces_to_check = [tuple(ns) for ns in response.get("namespaces", [])]
            else:
                namespaces_to_check = [tuple(ns) for ns in response]

        report = {
            "namespace": format_namespace(ns_tuple) if namespace else "(all)",
            "total_items": 0,
            "malformed": 0,
            "fixed": 0,
            "errors": 0,
            "dry_run": dry_run,
            "samples": [],
        }

        def is_escaped_json_value(value: dict) -> bool:
            """Check if value is a wrapper around escaped JSON."""
            if not isinstance(value, dict):
                return False
            # Check for {"value": "{...}"} pattern
            if len(value) == 1 and "value" in value:
                inner = value["value"]
                if isinstance(inner, str) and inner.startswith("{") and inner.endswith("}"):
                    try:
                        json.loads(inner)
                        return True
                    except json.JSONDecodeError:
                        return False
            return False

        def unwrap_value(value: dict) -> dict:
            """Unwrap escaped JSON from wrapper."""
            return json.loads(value["value"])

        for ns in namespaces_to_check:
            try:
                results = await self.client.store.search_items(ns, limit=100000)
                items = results.get("items", [])

                for item in items:
                    report["total_items"] += 1
                    value = item.get("value", {})

                    if is_escaped_json_value(value):
                        report["malformed"] += 1
                        fixed_value = unwrap_value(value)

                        # Add sample for first few
                        if len(report["samples"]) < 5:
                            report["samples"].append(
                                {
                                    "namespace": format_namespace(item.get("namespace", [])),
                                    "key": item.get("key"),
                                    "before": str(value)[:100] + "...",
                                    "after": str(fixed_value)[:100] + "...",
                                }
                            )

                        if not dry_run:
                            try:
                                item_ns = item.get("namespace", [])
                                if isinstance(item_ns, list):
                                    item_ns = tuple(item_ns)
                                await self.client.store.put_item(
                                    item_ns,
                                    item.get("key"),
                                    fixed_value,
                                )
                                report["fixed"] += 1
                            except Exception:
                                report["errors"] += 1
            except Exception:
                pass

        return report

    async def grep(self, pattern: str, namespace: str = "", limit: int = 100) -> List[Dict]:
        """
        Search memory values with a text pattern.

        Args:
            pattern: Text pattern to search for
            namespace: Namespace to search (empty for all)
            limit: Max results

        Returns:
            Matching items with context
        """
        import re

        ns_tuple = parse_namespace(namespace)

        # Get all items
        if namespace:
            results = await self.client.store.search_items(ns_tuple, limit=10000)
            items = results.get("items", [])
        else:
            items = await self.search_all("", limit=10000)

        matches = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Fallback to simple string match
            regex = None

        for item in items:
            value_str = json.dumps(item.get("value", {}))

            if regex:
                match = regex.search(value_str)
                if match:
                    # Extract context around match
                    start = max(0, match.start() - 50)
                    end = min(len(value_str), match.end() + 50)
                    context = value_str[start:end]

                    matches.append(
                        {
                            "namespace": item.get("namespace")
                            if isinstance(item.get("namespace"), str)
                            else format_namespace(item.get("namespace", [])),
                            "key": item.get("key"),
                            "match": match.group(),
                            "context": f"...{context}...",
                        }
                    )
            else:
                if pattern.lower() in value_str.lower():
                    matches.append(
                        {
                            "namespace": item.get("namespace")
                            if isinstance(item.get("namespace"), str)
                            else format_namespace(item.get("namespace", [])),
                            "key": item.get("key"),
                            "context": value_str[:200],
                        }
                    )

            if len(matches) >= limit:
                break

        return matches
