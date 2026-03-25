"""Backend API server for Excel Assistant chat with AI agent."""

import asyncio
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

import dotenv

dotenv.load_dotenv()

from excel_mcp.excel_server import mcp
from excel_agent.agent_runner import ExcelAgentRunner, TaskInput
from excel_agent.config import ExperimentConfig

app = FastAPI(title="Excel Assistant API")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP server configuration
MCP_SERVER_HOST = "127.0.0.1"
MCP_SERVER_PORT = 8765
MCP_SERVER_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"

# Global state for MCP server task
mcp_server_task: Optional[asyncio.Task] = None

# Store for uploaded files and outputs
UPLOAD_DIR = Path(__file__).parent / "uploads"
OUTPUT_DIR = Path(__file__).parent / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


async def ensure_mcp_server_running():
    """Ensure the MCP server is running."""
    global mcp_server_task
    if mcp_server_task is None or mcp_server_task.done():
        mcp_server_task = asyncio.create_task(
            mcp.run_sse_async(
                host=MCP_SERVER_HOST, port=MCP_SERVER_PORT, log_level="warning"
            )
        )
        await asyncio.sleep(1)  # Wait for server to start


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the MCP server lifecycle."""
    # Startup
    await ensure_mcp_server_running()
    yield
    # Shutdown
    global mcp_server_task
    if mcp_server_task:
        mcp_server_task.cancel()
        try:
            await mcp_server_task
        except asyncio.CancelledError:
            pass


@app.post("/api/chat")
async def chat(
    message: str = Form(...),
    file: UploadFile = File(...),
    history: str = Form(default="[]"),
):
    """
    Process a chat message with the Excel agent.

    Args:
        message: The user's instruction/message
        file: The current Excel file to operate on
        history: JSON string of chat history (for context, currently unused in agent)

    Returns:
        JSON with agent response and path to download the modified file
    """
    await ensure_mcp_server_running()

    # Generate unique session ID
    session_id = f"chat_{uuid.uuid4().hex[:8]}"

    # Save uploaded file
    input_path = UPLOAD_DIR / f"{session_id}_input.xlsx"
    output_path = OUTPUT_DIR / f"{session_id}_output.xlsx"

    try:
        # Save the uploaded file
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)

        # Copy input to output (agent will modify the output)
        shutil.copy(input_path, output_path)

        # Model to use - can be configured via environment variable
        model_string = os.getenv("EXCEL_ASSISTANT_MODEL")

        # Create config and runner
        config = ExperimentConfig(model=model_string)
        runner = ExcelAgentRunner(
            config=config,
            mcp_server_url=MCP_SERVER_URL,
        )

        # Create task input
        task_input = TaskInput(
            instruction=message,
            input_file=str(input_path),
            output_file=str(output_path),
        )

        # Run the agent
        agent_response = await runner.run_excel_agent(task_input)

        # Check for errors
        if agent_response.startswith("error:") or agent_response.startswith(
            "Session init failed"
        ):
            return JSONResponse(
                {
                    "success": False,
                    "error": agent_response,
                },
                status_code=500,
            )

        return JSONResponse(
            {
                "success": True,
                "response": agent_response,
                "output_file": f"/api/download/{session_id}",
                "session_id": session_id,
            }
        )

    except asyncio.TimeoutError:
        return JSONResponse(
            {
                "success": False,
                "error": "Agent timed out after 120 seconds",
            },
            status_code=504,
        )
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "error": str(e),
            },
            status_code=500,
        )
    finally:
        # Clean up input file
        if input_path.exists():
            input_path.unlink()


@app.get("/api/download/{session_id}")
async def download_output(session_id: str):
    """Download the modified Excel file."""
    output_path = OUTPUT_DIR / f"{session_id}_output.xlsx"

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="output.xlsx",
    )


@app.delete("/api/cleanup/{session_id}")
async def cleanup(session_id: str):
    """Clean up output files for a session."""
    output_path = OUTPUT_DIR / f"{session_id}_output.xlsx"
    if output_path.exists():
        output_path.unlink()
    return {"status": "cleaned"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
