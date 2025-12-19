"""
Thread commands for lgctl.

Threads maintain conversation state across multiple interactions.
Each thread has a unique ID and accumulated state.
"""

from typing import Any, Dict, List, Optional

from ..client import LGCtlClient
from ..formatters import Formatter


class ThreadCommands:
    """
    Thread management commands.

    Commands:
        ls      - list threads
        get     - get thread details
        create  - create new thread
        rm      - delete a thread
        state   - get/update thread state
        history - get thread state history
        cp      - copy thread state to new thread
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter

    async def ls(
        self,
        limit: int = 20,
        offset: int = 0,
        metadata: Optional[Dict] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        List threads.

        Args:
            limit: Max threads to return
            offset: Pagination offset
            metadata: Filter by metadata
            status: Filter by status (idle, busy, interrupted, error)

        Returns:
            List of thread summaries
        """
        kwargs = {"limit": limit, "offset": offset}
        if metadata:
            kwargs["metadata"] = metadata
        if status:
            kwargs["status"] = status

        threads = await self.client.threads.search(**kwargs)
        return [
            {
                "thread_id": t.get("thread_id"),
                "status": t.get("status", "unknown"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
                "metadata": t.get("metadata", {}),
            }
            for t in threads
        ]

    async def get(self, thread_id: str) -> Optional[Dict]:
        """
        Get thread details.

        Args:
            thread_id: Thread ID

        Returns:
            Thread details or None
        """
        try:
            thread = await self.client.threads.get(thread_id)
            return {
                "thread_id": thread.get("thread_id"),
                "status": thread.get("status"),
                "created_at": thread.get("created_at"),
                "updated_at": thread.get("updated_at"),
                "metadata": thread.get("metadata", {}),
                "values": thread.get("values", {}),
            }
        except Exception:
            return None

    async def create(
        self,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        if_exists: str = "raise",
    ) -> Dict:
        """
        Create a new thread.

        Args:
            thread_id: Optional custom thread ID
            metadata: Optional metadata
            if_exists: Behavior if thread exists ("raise", "return")

        Returns:
            Created thread details
        """
        kwargs = {}
        if thread_id:
            kwargs["thread_id"] = thread_id
        if metadata:
            kwargs["metadata"] = metadata
        if if_exists:
            kwargs["if_exists"] = if_exists

        thread = await self.client.threads.create(**kwargs)
        return {
            "thread_id": thread.get("thread_id"),
            "status": thread.get("status"),
            "created_at": thread.get("created_at"),
        }

    async def rm(self, thread_id: str) -> Dict:
        """
        Delete a thread.

        Args:
            thread_id: Thread ID to delete

        Returns:
            Confirmation
        """
        await self.client.threads.delete(thread_id)
        return {
            "status": "ok",
            "thread_id": thread_id,
            "action": "deleted",
        }

    async def state(
        self, thread_id: str, checkpoint_id: Optional[str] = None, subgraphs: bool = False
    ) -> Optional[Dict]:
        """
        Get thread state.

        Args:
            thread_id: Thread ID
            checkpoint_id: Specific checkpoint (default: latest)
            subgraphs: Include subgraph states

        Returns:
            Thread state
        """
        kwargs = {}
        if checkpoint_id:
            kwargs["checkpoint_id"] = checkpoint_id
        if subgraphs:
            kwargs["subgraphs"] = subgraphs

        try:
            state = await self.client.threads.get_state(thread_id, **kwargs)
            return {
                "thread_id": thread_id,
                "checkpoint_id": state.get("checkpoint", {}).get("checkpoint_id"),
                "values": state.get("values", {}),
                "next": state.get("next", []),
                "tasks": state.get("tasks", []),
                "created_at": state.get("created_at"),
            }
        except Exception:
            return None

    async def update_state(
        self,
        thread_id: str,
        values: Dict[str, Any],
        as_node: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Dict:
        """
        Update thread state.

        Args:
            thread_id: Thread ID
            values: Values to update
            as_node: Node to update as
            checkpoint_id: Checkpoint to update from

        Returns:
            Update confirmation
        """
        kwargs = {"values": values}
        if as_node:
            kwargs["as_node"] = as_node
        if checkpoint_id:
            kwargs["checkpoint_id"] = checkpoint_id

        result = await self.client.threads.update_state(thread_id, **kwargs)
        return {
            "status": "ok",
            "thread_id": thread_id,
            "checkpoint_id": result.get("checkpoint", {}).get("checkpoint_id"),
        }

    async def history(
        self,
        thread_id: str,
        limit: int = 10,
        before: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get thread state history.

        Args:
            thread_id: Thread ID
            limit: Max history entries
            before: Filter before timestamp
            checkpoint_id: Start from checkpoint

        Returns:
            List of historical states
        """
        kwargs = {"limit": limit}
        if before:
            kwargs["before"] = before
        if checkpoint_id:
            kwargs["checkpoint_id"] = checkpoint_id

        history = await self.client.threads.get_history(thread_id, **kwargs)
        return [
            {
                "checkpoint_id": h.get("checkpoint", {}).get("checkpoint_id"),
                "thread_id": h.get("checkpoint", {}).get("thread_id"),
                "created_at": h.get("created_at"),
                "next": h.get("next", []),
            }
            for h in history
        ]

    async def cp(
        self,
        src_thread_id: str,
        dst_thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Dict:
        """
        Copy thread state to a new thread.

        Args:
            src_thread_id: Source thread ID
            dst_thread_id: Optional destination thread ID
            checkpoint_id: Specific checkpoint to copy from

        Returns:
            New thread details
        """
        # Get source state
        state = await self.state(src_thread_id, checkpoint_id=checkpoint_id)
        if not state:
            raise ValueError(f"Thread not found: {src_thread_id}")

        # Create new thread
        new_thread = await self.create(thread_id=dst_thread_id)

        # Copy state if there are values
        if state.get("values"):
            await self.update_state(new_thread["thread_id"], state["values"])

        return {
            "status": "ok",
            "action": "copied",
            "from_thread": src_thread_id,
            "to_thread": new_thread["thread_id"],
        }

    async def patch(self, thread_id: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Update thread metadata.

        Args:
            thread_id: Thread ID
            metadata: New metadata

        Returns:
            Updated thread
        """
        kwargs = {}
        if metadata:
            kwargs["metadata"] = metadata

        thread = await self.client.threads.update(thread_id, **kwargs)
        return {
            "thread_id": thread.get("thread_id"),
            "metadata": thread.get("metadata", {}),
            "updated_at": thread.get("updated_at"),
        }
