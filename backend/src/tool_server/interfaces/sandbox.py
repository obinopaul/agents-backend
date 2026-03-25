"""Abstract sandbox interface to decouple tool_server from the main application."""

from abc import ABC, abstractmethod


class SandboxInterface(ABC):
    """Abstract interface for sandbox operations needed by tool_server."""

    @abstractmethod
    async def expose_port(self, port: int) -> str:
        """Expose a port in the sandbox and return the public URL."""
        pass