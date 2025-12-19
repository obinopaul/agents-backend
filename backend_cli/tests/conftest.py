"""
Pytest configuration and shared fixtures for lgctl tests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from lgctl.formatters import JsonFormatter, RawFormatter, TableFormatter

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def pytest_collection_modifyitems(items):
    """Add asyncio marker to all async test functions."""
    import inspect

    for item in items:
        if inspect.iscoroutinefunction(item.obj):
            item.add_marker(pytest.mark.asyncio)


# =============================================================================
# Mock Data
# =============================================================================

MOCK_NAMESPACES = [
    ("user", "123"),
    ("user", "456"),
    ("website", "products"),
    ("website", "categories"),
]

MOCK_ITEMS = [
    {
        "namespace": ("user", "123"),
        "key": "preferences",
        "value": {"theme": "dark", "language": "en"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T12:00:00Z",
    },
    {
        "namespace": ("user", "123"),
        "key": "history",
        "value": {"visits": 10, "last_visit": "2024-01-15"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-14T10:00:00Z",
    },
    {
        "namespace": ("website", "products"),
        "key": "item_001",
        "value": {"name": "Widget", "price": 9.99},
        "created_at": "2024-01-05T00:00:00Z",
        "updated_at": "2024-01-10T08:00:00Z",
    },
]

MOCK_THREADS = [
    {
        "thread_id": "thread-001",
        "status": "idle",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T12:00:00Z",
        "metadata": {"user_id": "123"},
        "values": {"messages": []},
    },
    {
        "thread_id": "thread-002",
        "status": "busy",
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-15T13:00:00Z",
        "metadata": {"user_id": "456"},
        "values": {"messages": ["hello"]},
    },
]

MOCK_RUNS = [
    {
        "run_id": "run-001",
        "thread_id": "thread-001",
        "assistant_id": "assistant-001",
        "status": "success",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:01:00Z",
        "metadata": {},
        "multitask_strategy": "reject",
    },
    {
        "run_id": "run-002",
        "thread_id": "thread-001",
        "assistant_id": "assistant-001",
        "status": "error",
        "created_at": "2024-01-15T11:00:00Z",
        "updated_at": "2024-01-15T11:02:00Z",
        "metadata": {},
        "multitask_strategy": "reject",
    },
]

MOCK_ASSISTANTS = [
    {
        "assistant_id": "assistant-001",
        "graph_id": "graph-001",
        "name": "Test Assistant",
        "version": 1,
        "config": {"model": "gpt-4"},
        "metadata": {"description": "A test assistant"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-10T00:00:00Z",
    },
]

MOCK_CRONS = [
    {
        "cron_id": "cron-001",
        "thread_id": "thread-001",
        "assistant_id": "assistant-001",
        "schedule": "0 * * * *",
        "enabled": True,
        "input": {"trigger": "scheduled"},
        "metadata": {},
        "next_run_at": "2024-01-15T13:00:00Z",
        "last_run_at": "2024-01-15T12:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T12:00:00Z",
    },
]


# =============================================================================
# Mock Store Client
# =============================================================================


class MockStoreClient:
    """Mock LangGraph Store client."""

    def __init__(self, items: Optional[List[Dict]] = None, namespaces: Optional[List] = None):
        self._items = items or MOCK_ITEMS.copy()
        self._namespaces = namespaces or MOCK_NAMESPACES.copy()

    async def list_namespaces(
        self, prefix: Optional[List[str]] = None, max_depth: int = 2, limit: int = 100
    ) -> Dict:
        """Mock list namespaces."""
        prefix = prefix or []
        prefix_tuple = tuple(prefix)

        filtered = [
            ns
            for ns in self._namespaces
            if ns[: len(prefix_tuple)] == prefix_tuple or not prefix_tuple
        ]
        return {"namespaces": filtered[:limit]}

    async def search_items(
        self,
        namespace: tuple,
        query: str = "",
        filter: Optional[Dict] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """Mock search items."""
        filtered = []
        for item in self._items:
            item_ns = (
                tuple(item["namespace"])
                if isinstance(item["namespace"], list)
                else item["namespace"]
            )
            if item_ns == namespace or not namespace:
                # Simple query matching
                if query:
                    value_str = str(item.get("value", {}))
                    if query.lower() in value_str.lower():
                        item_copy = item.copy()
                        item_copy["score"] = 0.9  # Mock score
                        filtered.append(item_copy)
                else:
                    filtered.append(item)

        return {"items": filtered[offset : offset + limit]}

    async def get_item(
        self, namespace: tuple, key: str, refresh_ttl: bool = False
    ) -> Optional[Dict]:
        """Mock get item."""
        for item in self._items:
            item_ns = (
                tuple(item["namespace"])
                if isinstance(item["namespace"], list)
                else item["namespace"]
            )
            if item_ns == namespace and item["key"] == key:
                return item
        return None

    async def put_item(
        self, namespace: tuple, key: str, value: Any, index: Optional[List[str]] = None
    ) -> None:
        """Mock put item."""
        # Remove existing item if present
        self._items = [
            i for i in self._items if not (tuple(i["namespace"]) == namespace and i["key"] == key)
        ]
        # Add new item
        now = datetime.now().isoformat()
        self._items.append(
            {
                "namespace": namespace,
                "key": key,
                "value": value,
                "created_at": now,
                "updated_at": now,
            }
        )

    async def delete_item(self, namespace: tuple, key: str) -> None:
        """Mock delete item."""
        self._items = [
            i for i in self._items if not (tuple(i["namespace"]) == namespace and i["key"] == key)
        ]


# =============================================================================
# Mock Threads Client
# =============================================================================


class MockThreadsClient:
    """Mock LangGraph Threads client."""

    def __init__(self, threads: Optional[List[Dict]] = None):
        self._threads = threads or MOCK_THREADS.copy()

    async def search(
        self,
        limit: int = 20,
        offset: int = 0,
        metadata: Optional[Dict] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """Mock search threads."""
        filtered = self._threads
        if status:
            filtered = [t for t in filtered if t.get("status") == status]
        if metadata:
            filtered = [
                t
                for t in filtered
                if all(t.get("metadata", {}).get(k) == v for k, v in metadata.items())
            ]
        return filtered[offset : offset + limit]

    async def get(self, thread_id: str) -> Optional[Dict]:
        """Mock get thread."""
        for thread in self._threads:
            if thread["thread_id"] == thread_id:
                return thread
        raise Exception("Thread not found")

    async def create(
        self,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        if_exists: str = "raise",
    ) -> Dict:
        """Mock create thread."""
        new_thread = {
            "thread_id": thread_id or f"thread-{len(self._threads) + 1:03d}",
            "status": "idle",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "values": {},
        }
        self._threads.append(new_thread)
        return new_thread

    async def delete(self, thread_id: str) -> None:
        """Mock delete thread."""
        self._threads = [t for t in self._threads if t["thread_id"] != thread_id]

    async def get_state(
        self, thread_id: str, checkpoint_id: Optional[str] = None, subgraphs: bool = False
    ) -> Dict:
        """Mock get thread state."""
        for thread in self._threads:
            if thread["thread_id"] == thread_id:
                return {
                    "values": thread.get("values", {}),
                    "checkpoint": {"checkpoint_id": "cp-001", "thread_id": thread_id},
                    "next": [],
                    "tasks": [],
                    "created_at": thread.get("created_at"),
                }
        raise Exception("Thread not found")

    async def update_state(
        self,
        thread_id: str,
        values: Dict[str, Any],
        as_node: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Dict:
        """Mock update thread state."""
        for thread in self._threads:
            if thread["thread_id"] == thread_id:
                thread["values"].update(values)
                thread["updated_at"] = datetime.now().isoformat()
                return {"checkpoint": {"checkpoint_id": "cp-002"}}
        raise Exception("Thread not found")

    async def get_history(
        self,
        thread_id: str,
        limit: int = 10,
        before: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> List[Dict]:
        """Mock get thread history."""
        return [
            {
                "checkpoint": {"checkpoint_id": f"cp-{i:03d}", "thread_id": thread_id},
                "created_at": f"2024-01-{15 - i:02d}T12:00:00Z",
                "next": [],
            }
            for i in range(min(limit, 3))
        ]

    async def update(self, thread_id: str, metadata: Optional[Dict] = None) -> Dict:
        """Mock update thread."""
        for thread in self._threads:
            if thread["thread_id"] == thread_id:
                if metadata:
                    thread["metadata"] = metadata
                thread["updated_at"] = datetime.now().isoformat()
                return thread
        raise Exception("Thread not found")


# =============================================================================
# Mock Runs Client
# =============================================================================


class MockRunsClient:
    """Mock LangGraph Runs client."""

    def __init__(self, runs: Optional[List[Dict]] = None):
        self._runs = runs or MOCK_RUNS.copy()

    async def list(
        self, thread_id: str, limit: int = 20, offset: int = 0, status: Optional[str] = None
    ) -> List[Dict]:
        """Mock list runs."""
        filtered = [r for r in self._runs if r["thread_id"] == thread_id]
        if status:
            filtered = [r for r in filtered if r.get("status") == status]
        return filtered[offset : offset + limit]

    async def get(self, thread_id: str, run_id: str) -> Optional[Dict]:
        """Mock get run."""
        for run in self._runs:
            if run["thread_id"] == thread_id and run["run_id"] == run_id:
                return run
        raise Exception("Run not found")

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
        """Mock create run."""
        new_run = {
            "run_id": f"run-{len(self._runs) + 1:03d}",
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "multitask_strategy": multitask_strategy,
        }
        self._runs.append(new_run)
        return new_run

    async def wait(
        self,
        thread_id: str,
        assistant_id: str,
        input: Optional[Dict] = None,
        config: Optional[Dict] = None,
        multitask_strategy: str = "reject",
        raise_on_error: bool = True,
    ) -> Dict:
        """Mock wait for run."""
        return {"status": "success", "result": {"output": "completed"}}

    async def cancel(self, thread_id: str, run_id: str, wait: bool = False) -> None:
        """Mock cancel run."""
        for run in self._runs:
            if run["run_id"] == run_id:
                run["status"] = "cancelled"
                return
        raise Exception("Run not found")

    async def join(self, thread_id: str, run_id: str) -> Dict:
        """Mock join run."""
        return {"status": "success", "result": {"output": "joined"}}

    async def delete(self, thread_id: str, run_id: str) -> None:
        """Mock delete run."""
        self._runs = [r for r in self._runs if r["run_id"] != run_id]


# =============================================================================
# Mock Assistants Client
# =============================================================================


class MockAssistantsClient:
    """Mock LangGraph Assistants client."""

    def __init__(self, assistants: Optional[List[Dict]] = None):
        self._assistants = assistants or MOCK_ASSISTANTS.copy()

    async def search(
        self,
        graph_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """Mock search assistants."""
        filtered = self._assistants
        if graph_id:
            filtered = [a for a in filtered if a.get("graph_id") == graph_id]
        return filtered[offset : offset + limit]

    async def get(self, assistant_id: str) -> Optional[Dict]:
        """Mock get assistant."""
        for assistant in self._assistants:
            if assistant["assistant_id"] == assistant_id:
                return assistant
        raise Exception("Assistant not found")

    async def create(
        self,
        graph_id: str,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        if_exists: str = "raise",
    ) -> Dict:
        """Mock create assistant."""
        new_assistant = {
            "assistant_id": f"assistant-{len(self._assistants) + 1:03d}",
            "graph_id": graph_id,
            "name": name or f"Assistant {len(self._assistants) + 1}",
            "version": 1,
            "config": config or {},
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._assistants.append(new_assistant)
        return new_assistant

    async def delete(self, assistant_id: str) -> None:
        """Mock delete assistant."""
        self._assistants = [a for a in self._assistants if a["assistant_id"] != assistant_id]

    async def get_graph(self, assistant_id: str) -> Dict:
        """Mock get graph."""
        return {"nodes": [], "edges": []}

    async def get_schemas(self, assistant_id: str) -> Dict:
        """Mock get schemas."""
        return {"input": {}, "output": {}}

    async def update(
        self,
        assistant_id: str,
        graph_id: Optional[str] = None,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Mock update assistant."""
        for assistant in self._assistants:
            if assistant["assistant_id"] == assistant_id:
                if graph_id:
                    assistant["graph_id"] = graph_id
                if name:
                    assistant["name"] = name
                if config:
                    assistant["config"] = config
                if metadata:
                    assistant["metadata"] = metadata
                assistant["updated_at"] = datetime.now().isoformat()
                return assistant
        raise Exception("Assistant not found")

    async def get_versions(self, assistant_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """Mock get versions."""
        return [
            {"version": i, "assistant_id": assistant_id, "created_at": f"2024-01-{i:02d}T00:00:00Z"}
            for i in range(1, min(limit + 1, 4))
        ]


# =============================================================================
# Mock Crons Client
# =============================================================================


class MockCronsClient:
    """Mock LangGraph Crons client."""

    def __init__(self, crons: Optional[List[Dict]] = None):
        self._crons = crons or MOCK_CRONS.copy()

    async def search(
        self,
        assistant_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """Mock search crons."""
        filtered = self._crons
        if assistant_id:
            filtered = [c for c in filtered if c.get("assistant_id") == assistant_id]
        if thread_id:
            filtered = [c for c in filtered if c.get("thread_id") == thread_id]
        return filtered[offset : offset + limit]

    async def get(self, cron_id: str) -> Optional[Dict]:
        """Mock get cron."""
        for cron in self._crons:
            if cron["cron_id"] == cron_id:
                return cron
        raise Exception("Cron not found")

    async def create(
        self,
        assistant_id: str,
        schedule: str,
        thread_id: Optional[str] = None,
        input: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Mock create cron."""
        new_cron = {
            "cron_id": f"cron-{len(self._crons) + 1:03d}",
            "thread_id": thread_id or f"thread-{len(self._crons) + 1:03d}",
            "assistant_id": assistant_id,
            "schedule": schedule,
            "enabled": True,
            "input": input or {},
            "metadata": metadata or {},
            "next_run_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._crons.append(new_cron)
        return new_cron

    async def delete(self, cron_id: str) -> None:
        """Mock delete cron."""
        self._crons = [c for c in self._crons if c["cron_id"] != cron_id]

    async def update(
        self,
        cron_id: str,
        schedule: Optional[str] = None,
        input: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        enabled: Optional[bool] = None,
    ) -> Dict:
        """Mock update cron."""
        for cron in self._crons:
            if cron["cron_id"] == cron_id:
                if schedule:
                    cron["schedule"] = schedule
                if input:
                    cron["input"] = input
                if metadata:
                    cron["metadata"] = metadata
                if enabled is not None:
                    cron["enabled"] = enabled
                cron["updated_at"] = datetime.now().isoformat()
                return cron
        raise Exception("Cron not found")


# =============================================================================
# Mock LGCtlClient
# =============================================================================


class MockLGCtlClient:
    """Mock LGCtlClient with all sub-clients."""

    def __init__(self, url: str = "http://localhost:8123", api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key
        self.timeout = 30.0

        self._store = MockStoreClient()
        self._threads = MockThreadsClient()
        self._runs = MockRunsClient()
        self._assistants = MockAssistantsClient()
        self._crons = MockCronsClient()

    @property
    def store(self):
        return self._store

    @property
    def threads(self):
        return self._threads

    @property
    def runs(self):
        return self._runs

    @property
    def assistants(self):
        return self._assistants

    @property
    def crons(self):
        return self._crons

    def is_remote(self) -> bool:
        return not self.url.startswith("http://localhost")

    def __repr__(self) -> str:
        mode = "remote" if self.is_remote() else "local"
        return f"MockLGCtlClient({self.url}, mode={mode})"


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_client():
    """Provide a mock LGCtlClient."""
    return MockLGCtlClient()


@pytest.fixture
def mock_remote_client():
    """Provide a mock remote LGCtlClient."""
    return MockLGCtlClient(url="https://api.example.com")


@pytest.fixture
def table_formatter():
    """Provide a TableFormatter."""
    return TableFormatter()


@pytest.fixture
def json_formatter():
    """Provide a JsonFormatter."""
    return JsonFormatter()


@pytest.fixture
def raw_formatter():
    """Provide a RawFormatter."""
    return RawFormatter()


@pytest.fixture
def mock_store_client():
    """Provide a mock store client."""
    return MockStoreClient()


@pytest.fixture
def mock_threads_client():
    """Provide a mock threads client."""
    return MockThreadsClient()


@pytest.fixture
def mock_runs_client():
    """Provide a mock runs client."""
    return MockRunsClient()


@pytest.fixture
def mock_assistants_client():
    """Provide a mock assistants client."""
    return MockAssistantsClient()


@pytest.fixture
def mock_crons_client():
    """Provide a mock crons client."""
    return MockCronsClient()


@pytest.fixture
def sample_items():
    """Provide sample test items."""
    return MOCK_ITEMS.copy()


@pytest.fixture
def sample_threads():
    """Provide sample test threads."""
    return MOCK_THREADS.copy()


@pytest.fixture
def sample_runs():
    """Provide sample test runs."""
    return MOCK_RUNS.copy()


@pytest.fixture
def sample_assistants():
    """Provide sample test assistants."""
    return MOCK_ASSISTANTS.copy()


@pytest.fixture
def sample_crons():
    """Provide sample test crons."""
    return MOCK_CRONS.copy()
