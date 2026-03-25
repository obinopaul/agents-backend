from typing import Any, Dict

from httpx import AsyncClient
from backend.src.tool_server.tools.base import BaseTool, ToolResult
from backend.src.tool_server.core.tool_server import get_tool_server_url, set_tool_server_url


# Name
NAME = "get_database_connection"
DISPLAY_NAME = "Get database connection"

# Tool description
DESCRIPTION = """Get a database connection for your application.

Dynamically provisions a new cloud database and returns the connection string.
Each call creates a fresh, isolated database instance.

Supported database types:
- **postgres** (default): PostgreSQL via Neon Cloud - serverless SQL database
- **redis**: Redis via Upstash - serverless key-value store
- **mysql**: MySQL via PlanetScale - serverless MySQL compatible database

The returned connection string can be used with any database library or ORM.
For example:
- PostgreSQL: Use with psycopg2, asyncpg, SQLAlchemy, Django ORM, etc.
- Redis: Use with redis-py, aioredis, etc.
- MySQL: Use with mysql-connector-python, aiomysql, SQLAlchemy, etc.
"""

# Input schema
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "database_type": {
            "type": "string",
            "description": "Type of database to provision. Defaults to 'postgres' (PostgreSQL).",
            "enum": ["postgres", "redis", "mysql"],
            "default": "postgres",
        },
    },
    "required": [],  # database_type has a default
}

DEFAULT_TIMEOUT = 120


class GetDatabaseConnection(BaseTool):
    name = NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    input_schema = INPUT_SCHEMA
    read_only = False

    def __init__(
        self,
        credential: Dict,
        tool_server_url: str | None = None,
    ) -> None:
        super().__init__()
        if tool_server_url:
            set_tool_server_url(tool_server_url)
        self.credential = credential
        
    async def execute(
        self,
        tool_input: dict[str, Any],
    ) -> ToolResult:
        # Check if credential is set for this tool
        if not self.credential or not self.credential.get('user_api_key'):
            return ToolResult(
                llm_content="Database connection requires user authentication. The sandbox credential has not been set. Please set credentials via POST /credential endpoint.",
                is_error=True,
            )
        
        # Get database type with default
        database_type = tool_input.get("database_type", "postgres")
        
        tool_server_url = get_tool_server_url()
        try:
            async with AsyncClient(
                base_url=tool_server_url,
            ) as client:
                response = await client.post(
                    f"{tool_server_url}/database",
                    json={
                        "database_type": database_type,
                        "session_id": self.credential['session_id'],
                    },
                    headers={
                        "Authorization": f"Bearer {self.credential['user_api_key']}",
                    },
                    timeout=DEFAULT_TIMEOUT,
                )
        except Exception as e:
            return ToolResult(
                llm_content=f"Failed to get database connection. Error: {str(e)}",
                user_display_content=f"Failed to get database connection. Error: {str(e)}",
                is_error=True,
            )

        if response.status_code != 200 or response.json().get("success") is False:
            return ToolResult(
                llm_content=f"Failed to get database connection. Error: {response.json().get('error')}",
                user_display_content=f"Failed to get database connection. Error: {response.json().get('error')}",
                is_error=True,
            )
        connection_string = response.json()["connection_string"]

        return ToolResult(
            llm_content=f"Successfully got database connection. Tool output: {connection_string}",
            user_display_content=f"Successfully got database connection. Tool output: {connection_string}",
            is_error=False,
        )

    async def execute_mcp_wrapper(
        self,
        database_type: str,
    ):
        return await self._mcp_wrapper(
            tool_input={
                "database_type": database_type,
            }
        )
