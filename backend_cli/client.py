"""
Core client wrapper for LangGraph SDK with flexible connection options.
"""

import os
from typing import Optional

from langgraph_sdk import get_client as sdk_get_client


class LGCtlClient:
    """
    Wrapper around the LangGraph SDK client with convenience methods.

    Supports connection to:
    - Local development servers (http://localhost:8123)
    - LangSmith Cloud deployments (via LANGSMITH_DEPLOYMENT_URL)
    - Custom URLs
    """

    def __init__(
        self, url: Optional[str] = None, api_key: Optional[str] = None, timeout: float = 30.0
    ):
        """
        Initialize the client.

        Args:
            url: LangGraph server URL. Defaults to env vars or localhost.
            api_key: API key for authentication. Defaults to LANGSMITH_API_KEY.
            timeout: Request timeout in seconds.
        """
        self.url = url or self._resolve_url()
        self.api_key = api_key or os.getenv("LANGSMITH_API_KEY")
        self.timeout = timeout

        self._client = sdk_get_client(url=self.url, api_key=self.api_key)

    def _resolve_url(self) -> str:
        """Resolve the server URL from environment or defaults."""
        # Priority: LANGSMITH_DEPLOYMENT_URL > LANGGRAPH_URL > localhost
        return (
            os.getenv("LANGSMITH_DEPLOYMENT_URL")
            or os.getenv("LANGGRAPH_URL")
            or "http://localhost:8123"
        )

    @property
    def store(self):
        """Access the store client."""
        return self._client.store

    @property
    def threads(self):
        """Access the threads client."""
        return self._client.threads

    @property
    def runs(self):
        """Access the runs client."""
        return self._client.runs

    @property
    def assistants(self):
        """Access the assistants client."""
        return self._client.assistants

    @property
    def crons(self):
        """Access the crons client."""
        return self._client.crons

    def is_remote(self) -> bool:
        """Check if connected to a remote deployment."""
        return not self.url.startswith("http://localhost")

    def __repr__(self) -> str:
        mode = "remote" if self.is_remote() else "local"
        return f"LGCtlClient({self.url}, mode={mode})"


def get_client(url: Optional[str] = None, api_key: Optional[str] = None) -> LGCtlClient:
    """
    Convenience function to create a client.

    Args:
        url: Optional URL override
        api_key: Optional API key override

    Returns:
        Configured LGCtlClient instance
    """
    return LGCtlClient(url=url, api_key=api_key)
