"""
Store commands for lgctl.

The store is a namespace-based key-value storage with semantic search.
Commands operate on namespaces (directories) and items (files).

Namespace format: "a,b,c" -> ("a", "b", "c")
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from ..client import LGCtlClient
from ..formatters import Formatter


def parse_namespace(ns_str: str) -> Tuple[str, ...]:
    """Parse a namespace string into a tuple.

    Examples:
        "user,123" -> ("user", "123")
        "website,products" -> ("website", "products")
        "" -> ()
    """
    if not ns_str:
        return tuple()
    return tuple(ns_str.split(","))


def format_namespace(ns: Union[Tuple, List, str]) -> str:
    """Format a namespace tuple for display using comma notation."""
    if not ns:
        return "(root)"
    # Handle string namespaces (API sometimes returns strings)
    if isinstance(ns, str):
        return ns
    return ",".join(str(part) for part in ns)


class StoreCommands:
    """
    Store management commands.

    Unix-style commands:
        ls      - list namespaces or items
        get     - retrieve a specific item
        put     - store an item
        rm      - delete an item
        search  - semantic search across items
        mv      - move/rename an item
        cp      - copy an item
        cat     - dump item contents (alias for get)
        tree    - show namespace tree
        count   - count items in namespace
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter

    async def ls(
        self, namespace: str = "", max_depth: int = 2, limit: int = 100, show_items: bool = False
    ) -> List[Dict]:
        """
        List namespaces or items.

        Args:
            namespace: Namespace prefix to list (empty for root)
            max_depth: How deep to traverse
            limit: Max results to return
            show_items: If True, list items instead of namespaces

        Returns:
            List of namespaces or items
        """
        ns_tuple = parse_namespace(namespace)

        if show_items:
            # List items in the namespace
            results = await self.client.store.search_items(ns_tuple, limit=limit)
            items = results.get("items", [])
            return [
                {
                    "namespace": format_namespace(item.get("namespace", [])),
                    "key": item.get("key"),
                    "updated_at": item.get("updated_at"),
                }
                for item in items
            ]
        else:
            # List namespaces
            response = await self.client.store.list_namespaces(
                prefix=list(ns_tuple), max_depth=max_depth, limit=limit
            )

            # Handle different response formats from the API
            if isinstance(response, dict):
                # API returns {"namespaces": [...]}
                namespaces = response.get("namespaces", [])
            else:
                namespaces = response

            return [{"namespace": format_namespace(ns)} for ns in namespaces]

    async def get(self, namespace: str, key: str, refresh_ttl: bool = False) -> Optional[Dict]:
        """
        Get a specific item by namespace and key.

        Args:
            namespace: Namespace string (e.g., "user,123")
            key: Item key
            refresh_ttl: Whether to refresh TTL on access

        Returns:
            Item dict or None if not found
        """
        ns_tuple = parse_namespace(namespace)
        item = await self.client.store.get_item(ns_tuple, key, refresh_ttl=refresh_ttl)
        if item:
            return {
                "namespace": format_namespace(item.get("namespace", [])),
                "key": item.get("key"),
                "value": item.get("value"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
        return None

    async def put(
        self, namespace: str, key: str, value: Any, index: Optional[List[str]] = None
    ) -> Dict:
        """
        Store an item.

        Args:
            namespace: Namespace string
            key: Item key
            value: Value to store (will be wrapped in dict if not already)
            index: Fields to index for search (default: all)

        Returns:
            Confirmation dict
        """
        ns_tuple = parse_namespace(namespace)

        # Wrap simple values
        if not isinstance(value, dict):
            value = {"value": value}

        await self.client.store.put_item(ns_tuple, key, value, index=index)

        return {
            "status": "ok",
            "namespace": format_namespace(ns_tuple),
            "key": key,
        }

    async def rm(self, namespace: str, key: str) -> Dict:
        """
        Delete an item.

        Args:
            namespace: Namespace string
            key: Item key

        Returns:
            Confirmation dict
        """
        ns_tuple = parse_namespace(namespace)
        await self.client.store.delete_item(ns_tuple, key)
        return {
            "status": "ok",
            "namespace": format_namespace(ns_tuple),
            "key": key,
            "action": "deleted",
        }

    async def search(
        self,
        namespace: str = "",
        query: str = "",
        filter_dict: Optional[Dict] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Search items using semantic search.

        Args:
            namespace: Namespace to search in (empty for all)
            query: Search query (semantic search if store has embeddings)
            filter_dict: Metadata filters
            limit: Max results
            offset: Pagination offset

        Returns:
            List of matching items
        """
        ns_tuple = parse_namespace(namespace)
        results = await self.client.store.search_items(
            ns_tuple, query=query, filter=filter_dict or {}, limit=limit, offset=offset
        )

        items = results.get("items", [])
        return [
            {
                "namespace": format_namespace(item.get("namespace", [])),
                "key": item.get("key"),
                "value": item.get("value"),
                "score": item.get("score"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
            for item in items
        ]

    async def mv(
        self, src_namespace: str, src_key: str, dst_namespace: str, dst_key: Optional[str] = None
    ) -> Dict:
        """
        Move/rename an item.

        Args:
            src_namespace: Source namespace
            src_key: Source key
            dst_namespace: Destination namespace
            dst_key: Destination key (defaults to src_key)

        Returns:
            Confirmation dict
        """
        dst_key = dst_key or src_key

        # Get the item
        item = await self.get(src_namespace, src_key)
        if not item:
            raise ValueError(f"Item not found: {src_namespace}/{src_key}")

        # Put in new location
        await self.put(dst_namespace, dst_key, item["value"])

        # Delete from old location
        await self.rm(src_namespace, src_key)

        return {
            "status": "ok",
            "action": "moved",
            "from": f"{format_namespace(parse_namespace(src_namespace))}/{src_key}",
            "to": f"{format_namespace(parse_namespace(dst_namespace))}/{dst_key}",
        }

    async def cp(
        self, src_namespace: str, src_key: str, dst_namespace: str, dst_key: Optional[str] = None
    ) -> Dict:
        """
        Copy an item.

        Args:
            src_namespace: Source namespace
            src_key: Source key
            dst_namespace: Destination namespace
            dst_key: Destination key (defaults to src_key)

        Returns:
            Confirmation dict
        """
        dst_key = dst_key or src_key

        # Get the item
        item = await self.get(src_namespace, src_key)
        if not item:
            raise ValueError(f"Item not found: {src_namespace}/{src_key}")

        # Put in new location
        await self.put(dst_namespace, dst_key, item["value"])

        return {
            "status": "ok",
            "action": "copied",
            "from": f"{format_namespace(parse_namespace(src_namespace))}/{src_key}",
            "to": f"{format_namespace(parse_namespace(dst_namespace))}/{dst_key}",
        }

    async def count(self, namespace: str = "") -> Dict:
        """
        Count items in a namespace.

        Args:
            namespace: Namespace to count (empty for all)

        Returns:
            Count result dict
        """
        ns_tuple = parse_namespace(namespace)
        results = await self.client.store.search_items(
            ns_tuple,
            limit=10000,  # High limit to get accurate count
        )
        count = len(results.get("items", []))
        return {
            "namespace": format_namespace(ns_tuple) if namespace else "(all)",
            "count": count,
        }

    async def tree(self, namespace: str = "", max_depth: int = 10) -> List[Dict]:
        """
        Show namespace tree structure.

        Args:
            namespace: Starting namespace
            max_depth: Max depth to traverse

        Returns:
            List of namespaces with depth info
        """
        ns_tuple = parse_namespace(namespace)
        response = await self.client.store.list_namespaces(
            prefix=list(ns_tuple), max_depth=max_depth, limit=1000
        )

        # Handle different response formats from the API
        if isinstance(response, dict):
            namespaces = response.get("namespaces", [])
        else:
            namespaces = response

        # Build tree structure
        results = []
        for ns in namespaces:
            depth = len(ns) - len(ns_tuple)
            indent = "  " * depth
            name = ns[-1] if ns else "(root)"
            results.append(
                {
                    "tree": f"{indent}{name}",
                    "namespace": format_namespace(ns),
                    "depth": depth,
                }
            )

        return results

    # Alias
    cat = get
