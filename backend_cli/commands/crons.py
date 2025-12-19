"""
Cron commands for lgctl.

Crons schedule recurring runs on threads.
"""

from typing import Dict, List, Optional

from ..client import LGCtlClient
from ..formatters import Formatter


class CronCommands:
    """
    Cron job management commands.

    Commands:
        ls      - list cron jobs
        get     - get cron details
        create  - schedule a new cron job
        rm      - delete a cron job
        patch   - update cron configuration
        enable  - enable a cron job
        disable - disable a cron job
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter

    async def ls(
        self,
        assistant_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """
        List cron jobs.

        Args:
            assistant_id: Filter by assistant
            thread_id: Filter by thread
            limit: Max results
            offset: Pagination offset

        Returns:
            List of cron summaries
        """
        kwargs = {"limit": limit, "offset": offset}
        if assistant_id:
            kwargs["assistant_id"] = assistant_id
        if thread_id:
            kwargs["thread_id"] = thread_id

        crons = await self.client.crons.search(**kwargs)
        return [
            {
                "cron_id": c.get("cron_id"),
                "thread_id": c.get("thread_id"),
                "assistant_id": c.get("assistant_id"),
                "schedule": c.get("schedule"),
                "enabled": c.get("enabled", True),
                "next_run_at": c.get("next_run_at"),
                "created_at": c.get("created_at"),
            }
            for c in crons
        ]

    async def get(self, cron_id: str) -> Optional[Dict]:
        """
        Get cron job details.

        Args:
            cron_id: Cron job ID

        Returns:
            Cron details or None
        """
        try:
            cron = await self.client.crons.get(cron_id)
            return {
                "cron_id": cron.get("cron_id"),
                "thread_id": cron.get("thread_id"),
                "assistant_id": cron.get("assistant_id"),
                "schedule": cron.get("schedule"),
                "enabled": cron.get("enabled", True),
                "input": cron.get("input"),
                "metadata": cron.get("metadata", {}),
                "next_run_at": cron.get("next_run_at"),
                "last_run_at": cron.get("last_run_at"),
                "created_at": cron.get("created_at"),
                "updated_at": cron.get("updated_at"),
            }
        except Exception:
            return None

    async def create(
        self,
        assistant_id: str,
        schedule: str,
        thread_id: Optional[str] = None,
        input: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Create a new cron job.

        Args:
            assistant_id: Assistant to run
            schedule: Cron schedule (e.g., "0 * * * *" for hourly)
            thread_id: Thread to run on (creates new if not specified)
            input: Input data for each run
            metadata: Custom metadata

        Returns:
            Created cron details
        """
        kwargs = {
            "assistant_id": assistant_id,
            "schedule": schedule,
        }
        if thread_id:
            kwargs["thread_id"] = thread_id
        if input:
            kwargs["input"] = input
        if metadata:
            kwargs["metadata"] = metadata

        cron = await self.client.crons.create(**kwargs)
        return {
            "cron_id": cron.get("cron_id"),
            "thread_id": cron.get("thread_id"),
            "assistant_id": cron.get("assistant_id"),
            "schedule": cron.get("schedule"),
            "next_run_at": cron.get("next_run_at"),
            "created_at": cron.get("created_at"),
        }

    async def rm(self, cron_id: str) -> Dict:
        """
        Delete a cron job.

        Args:
            cron_id: Cron job ID

        Returns:
            Deletion confirmation
        """
        await self.client.crons.delete(cron_id)
        return {
            "status": "ok",
            "cron_id": cron_id,
            "action": "deleted",
        }

    async def patch(
        self,
        cron_id: str,
        schedule: Optional[str] = None,
        input: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Update a cron job.

        Args:
            cron_id: Cron job ID
            schedule: New schedule
            input: New input
            metadata: New metadata

        Returns:
            Updated cron details
        """
        kwargs = {}
        if schedule:
            kwargs["schedule"] = schedule
        if input:
            kwargs["input"] = input
        if metadata:
            kwargs["metadata"] = metadata

        cron = await self.client.crons.update(cron_id, **kwargs)
        return {
            "cron_id": cron.get("cron_id"),
            "schedule": cron.get("schedule"),
            "next_run_at": cron.get("next_run_at"),
            "updated_at": cron.get("updated_at"),
        }

    async def enable(self, cron_id: str) -> Dict:
        """
        Enable a cron job.

        Args:
            cron_id: Cron job ID

        Returns:
            Update confirmation
        """
        await self.client.crons.update(cron_id, enabled=True)
        return {
            "status": "ok",
            "cron_id": cron_id,
            "enabled": True,
        }

    async def disable(self, cron_id: str) -> Dict:
        """
        Disable a cron job.

        Args:
            cron_id: Cron job ID

        Returns:
            Update confirmation
        """
        await self.client.crons.update(cron_id, enabled=False)
        return {
            "status": "ok",
            "cron_id": cron_id,
            "enabled": False,
        }
