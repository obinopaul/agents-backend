"""
Run commands for lgctl.

Runs are executions of a graph on a thread. They can be:
- Stateful (on a thread)
- Stateless
- Streaming or blocking
"""

from typing import AsyncIterator, Dict, List, Optional

from ..client import LGCtlClient
from ..formatters import Formatter


class RunCommands:
    """
    Run management commands.

    Commands:
        ls      - list runs
        get     - get run details
        create  - start a new run
        wait    - wait for run completion
        stream  - stream run output
        cancel  - cancel a running run
        join    - wait and get result
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter

    async def ls(
        self, thread_id: str, limit: int = 20, offset: int = 0, status: Optional[str] = None
    ) -> List[Dict]:
        """
        List runs for a thread.

        Args:
            thread_id: Thread ID
            limit: Max runs to return
            offset: Pagination offset
            status: Filter by status (pending, running, error, success, timeout, interrupted)

        Returns:
            List of run summaries
        """
        kwargs = {"limit": limit, "offset": offset}
        if status:
            kwargs["status"] = status

        runs = await self.client.runs.list(thread_id, **kwargs)
        return [
            {
                "run_id": r.get("run_id"),
                "thread_id": r.get("thread_id"),
                "assistant_id": r.get("assistant_id"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
            }
            for r in runs
        ]

    async def get(self, thread_id: str, run_id: str) -> Optional[Dict]:
        """
        Get run details.

        Args:
            thread_id: Thread ID
            run_id: Run ID

        Returns:
            Run details or None
        """
        try:
            run = await self.client.runs.get(thread_id, run_id)
            return {
                "run_id": run.get("run_id"),
                "thread_id": run.get("thread_id"),
                "assistant_id": run.get("assistant_id"),
                "status": run.get("status"),
                "metadata": run.get("metadata", {}),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "multitask_strategy": run.get("multitask_strategy"),
            }
        except Exception:
            return None

    async def create(
        self,
        thread_id: str,
        assistant_id: str,
        input: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        config: Optional[Dict] = None,
        multitask_strategy: str = "reject",
        interrupt_before: Optional[List[str]] = None,
        interrupt_after: Optional[List[str]] = None,
    ) -> Dict:
        """
        Create/start a new run.

        Args:
            thread_id: Thread ID (use None for stateless)
            assistant_id: Assistant ID
            input: Input data
            metadata: Run metadata
            config: Runtime config
            multitask_strategy: How to handle concurrent runs
            interrupt_before: Nodes to interrupt before
            interrupt_after: Nodes to interrupt after

        Returns:
            Created run details
        """
        kwargs = {
            "assistant_id": assistant_id,
            "multitask_strategy": multitask_strategy,
        }
        if input:
            kwargs["input"] = input
        if metadata:
            kwargs["metadata"] = metadata
        if config:
            kwargs["config"] = config
        if interrupt_before:
            kwargs["interrupt_before"] = interrupt_before
        if interrupt_after:
            kwargs["interrupt_after"] = interrupt_after

        run = await self.client.runs.create(thread_id, **kwargs)
        return {
            "run_id": run.get("run_id"),
            "thread_id": run.get("thread_id"),
            "assistant_id": run.get("assistant_id"),
            "status": run.get("status"),
            "created_at": run.get("created_at"),
        }

    async def wait(
        self,
        thread_id: str,
        assistant_id: str,
        input: Optional[Dict] = None,
        config: Optional[Dict] = None,
        multitask_strategy: str = "reject",
        raise_on_error: bool = True,
    ) -> Dict:
        """
        Start a run and wait for completion.

        Args:
            thread_id: Thread ID
            assistant_id: Assistant ID
            input: Input data
            config: Runtime config
            multitask_strategy: How to handle concurrent runs
            raise_on_error: Raise exception on error

        Returns:
            Final run result
        """
        kwargs = {
            "assistant_id": assistant_id,
            "multitask_strategy": multitask_strategy,
        }
        if input:
            kwargs["input"] = input
        if config:
            kwargs["config"] = config

        result = await self.client.runs.wait(thread_id, **kwargs, raise_on_error=raise_on_error)
        return result

    async def stream(
        self,
        thread_id: str,
        assistant_id: str,
        input: Optional[Dict] = None,
        config: Optional[Dict] = None,
        stream_mode: str = "values",
        multitask_strategy: str = "reject",
    ) -> AsyncIterator[Dict]:
        """
        Stream run output.

        Args:
            thread_id: Thread ID
            assistant_id: Assistant ID
            input: Input data
            config: Runtime config
            stream_mode: Streaming mode (values, updates, messages, events)
            multitask_strategy: How to handle concurrent runs

        Yields:
            Stream chunks
        """
        kwargs = {
            "assistant_id": assistant_id,
            "stream_mode": stream_mode,
            "multitask_strategy": multitask_strategy,
        }
        if input:
            kwargs["input"] = input
        if config:
            kwargs["config"] = config

        async for chunk in self.client.runs.stream(thread_id, **kwargs):
            yield {
                "event": chunk.event,
                "data": chunk.data,
            }

    async def cancel(self, thread_id: str, run_id: str, wait: bool = False) -> Dict:
        """
        Cancel a running run.

        Args:
            thread_id: Thread ID
            run_id: Run ID
            wait: Wait for cancellation to complete

        Returns:
            Cancellation result
        """
        await self.client.runs.cancel(thread_id, run_id, wait=wait)
        return {
            "status": "ok",
            "run_id": run_id,
            "action": "cancelled",
        }

    async def join(self, thread_id: str, run_id: str) -> Dict:
        """
        Wait for a run to complete and get result.

        Args:
            thread_id: Thread ID
            run_id: Run ID

        Returns:
            Final run result
        """
        result = await self.client.runs.join(thread_id, run_id)
        return result

    async def delete(self, thread_id: str, run_id: str) -> Dict:
        """
        Delete a run.

        Args:
            thread_id: Thread ID
            run_id: Run ID

        Returns:
            Deletion confirmation
        """
        await self.client.runs.delete(thread_id, run_id)
        return {
            "status": "ok",
            "run_id": run_id,
            "action": "deleted",
        }

    # Alias
    rm = delete
