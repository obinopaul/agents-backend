"""
Assistant commands for lgctl.

Assistants are versioned configurations of graphs.
They define how a graph behaves when executed.
"""

from typing import Dict, List, Optional

from ..client import LGCtlClient
from ..formatters import Formatter


class AssistantCommands:
    """
    Assistant management commands.

    Commands:
        ls      - list assistants
        get     - get assistant details
        create  - create new assistant
        rm      - delete assistant
        graph   - get graph definition
        schema  - get input/output schemas
        patch   - update assistant config
    """

    def __init__(self, client: LGCtlClient, formatter: Formatter):
        self.client = client
        self.fmt = formatter

    async def ls(
        self,
        graph_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """
        List assistants.

        Args:
            graph_id: Filter by graph ID
            metadata: Filter by metadata
            limit: Max results
            offset: Pagination offset

        Returns:
            List of assistant summaries
        """
        kwargs = {"limit": limit, "offset": offset}
        if graph_id:
            kwargs["graph_id"] = graph_id
        if metadata:
            kwargs["metadata"] = metadata

        assistants = await self.client.assistants.search(**kwargs)
        return [
            {
                "assistant_id": a.get("assistant_id"),
                "graph_id": a.get("graph_id"),
                "name": a.get("name"),
                "version": a.get("version"),
                "created_at": a.get("created_at"),
                "updated_at": a.get("updated_at"),
                "metadata": a.get("metadata", {}),
            }
            for a in assistants
        ]

    async def get(self, assistant_id: str) -> Optional[Dict]:
        """
        Get assistant details.

        Args:
            assistant_id: Assistant ID

        Returns:
            Assistant details or None
        """
        try:
            assistant = await self.client.assistants.get(assistant_id)
            return {
                "assistant_id": assistant.get("assistant_id"),
                "graph_id": assistant.get("graph_id"),
                "name": assistant.get("name"),
                "version": assistant.get("version"),
                "config": assistant.get("config", {}),
                "metadata": assistant.get("metadata", {}),
                "created_at": assistant.get("created_at"),
                "updated_at": assistant.get("updated_at"),
            }
        except Exception:
            return None

    async def create(
        self,
        graph_id: str,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        if_exists: str = "raise",
    ) -> Dict:
        """
        Create a new assistant.

        Args:
            graph_id: Graph ID to use
            name: Optional name
            config: Configuration overrides
            metadata: Custom metadata
            if_exists: Behavior if exists ("raise", "return", "update")

        Returns:
            Created assistant details
        """
        kwargs = {"graph_id": graph_id, "if_exists": if_exists}
        if name:
            kwargs["name"] = name
        if config:
            kwargs["config"] = config
        if metadata:
            kwargs["metadata"] = metadata

        assistant = await self.client.assistants.create(**kwargs)
        return {
            "assistant_id": assistant.get("assistant_id"),
            "graph_id": assistant.get("graph_id"),
            "name": assistant.get("name"),
            "created_at": assistant.get("created_at"),
        }

    async def rm(self, assistant_id: str) -> Dict:
        """
        Delete an assistant.

        Args:
            assistant_id: Assistant ID

        Returns:
            Deletion confirmation
        """
        await self.client.assistants.delete(assistant_id)
        return {
            "status": "ok",
            "assistant_id": assistant_id,
            "action": "deleted",
        }

    async def graph(self, assistant_id: str) -> Dict:
        """
        Get graph definition for an assistant.

        Args:
            assistant_id: Assistant ID

        Returns:
            Graph definition
        """
        graph = await self.client.assistants.get_graph(assistant_id)
        return graph

    async def schema(self, assistant_id: str) -> Dict:
        """
        Get input/output schemas for an assistant.

        Args:
            assistant_id: Assistant ID

        Returns:
            Schema definitions
        """
        schemas = await self.client.assistants.get_schemas(assistant_id)
        return schemas

    async def patch(
        self,
        assistant_id: str,
        graph_id: Optional[str] = None,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Update an assistant.

        Args:
            assistant_id: Assistant ID
            graph_id: New graph ID
            name: New name
            config: New config
            metadata: New metadata

        Returns:
            Updated assistant details
        """
        kwargs = {}
        if graph_id:
            kwargs["graph_id"] = graph_id
        if name:
            kwargs["name"] = name
        if config:
            kwargs["config"] = config
        if metadata:
            kwargs["metadata"] = metadata

        assistant = await self.client.assistants.update(assistant_id, **kwargs)
        return {
            "assistant_id": assistant.get("assistant_id"),
            "graph_id": assistant.get("graph_id"),
            "name": assistant.get("name"),
            "updated_at": assistant.get("updated_at"),
        }

    async def versions(self, assistant_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """
        List assistant versions.

        Args:
            assistant_id: Assistant ID
            limit: Max versions
            offset: Pagination offset

        Returns:
            List of versions
        """
        try:
            versions = await self.client.assistants.get_versions(
                assistant_id, limit=limit, offset=offset
            )
            return [
                {
                    "version": v.get("version"),
                    "assistant_id": v.get("assistant_id"),
                    "created_at": v.get("created_at"),
                }
                for v in versions
            ]
        except Exception:
            return []
