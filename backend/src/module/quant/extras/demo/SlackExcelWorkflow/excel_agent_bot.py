"""
Slack bot that processes Excel files using an AI agent.

Mention the bot with an attached .xlsx file and describe the task.
The bot will process the file using the AI Excel agent and return the result.

Example:
    @ExcelBot Please add a SUM formula in cell E2 that totals A2:D2

Setup:
    1. Create a Slack App at https://api.slack.com/apps
    2. Enable Socket Mode and generate an App-Level Token (xapp-...)
    3. Add Bot Token Scopes: app_mentions:read, chat:write, files:read, files:write
    4. Subscribe to bot events: app_mention
    5. Install the app to your workspace
    6. Set environment variables:
       - SLACK_BOT_TOKEN=xoxb-...
       - SLACK_APP_TOKEN=xapp-...
       - EXCEL_AGENT_MODEL=openrouter:...
       - OPENROUTER_API_KEY=sk-or-v1-...

Run:
    conda activate excel
    python excel_agent_bot.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import dotenv
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

dotenv.load_dotenv()

from excel_mcp.excel_server import mcp
from excel_agent.agent_runner import ExcelAgentRunner, TaskInput
from excel_agent.config import ExperimentConfig

# Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# MCP server config
MCP_HOST, MCP_PORT = "127.0.0.1", 8765
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"

# Model (configurable via env)
MODEL = os.getenv("EXCEL_AGENT_MODEL")


async def run_mcp_server():
    """Start the MCP server in the background."""
    await mcp.run_sse_async(host=MCP_HOST, port=MCP_PORT, log_level="warning")


def download_slack_file(file_info: dict, token: str) -> bytes:
    """Download a file from Slack."""
    url = file_info.get("url_private_download") or file_info.get("url_private")
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.content


async def process_excel_task(
    input_path: Path, output_path: Path, instruction: str
) -> str:
    """Run the Excel AI agent on the file with the given instruction."""
    # Create config and runner
    config = ExperimentConfig(model=MODEL)
    runner = ExcelAgentRunner(
        config=config,
        mcp_server_url=MCP_URL,
    )

    # Create task input
    task_input = TaskInput(
        instruction=instruction,
        input_file=str(input_path),
        output_file=str(output_path),
    )

    # Run the agent
    return await runner.run_excel_agent(task_input)


def extract_xlsx_file(event: dict, client) -> dict | None:
    """Extract the first .xlsx file from a Slack message."""
    files = event.get("files", [])
    for f in files:
        if f.get("filetype") == "xlsx" or f.get("name", "").endswith(".xlsx"):
            return f
    return None


def extract_instruction(text: str) -> str:
    """Extract the instruction from the message (remove bot mention)."""
    # Remove <@BOTID> mention pattern
    import re

    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


@app.event("app_mention")
def handle_mention(event, say, client):
    """Handle @mentions - process attached Excel files with AI."""
    channel = event["channel"]
    user = event["user"]
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Extract instruction
    instruction = extract_instruction(text)
    if not instruction:
        say(
            text=f"<@{user}> Please describe what you'd like me to do with the Excel file.",
            thread_ts=thread_ts,
        )
        return

    # Look for attached Excel file
    xlsx_file = extract_xlsx_file(event, client)
    if not xlsx_file:
        say(
            text=f"<@{user}> Please attach an .xlsx file to your message.",
            thread_ts=thread_ts,
        )
        return

    # Acknowledge receipt
    say(text=f"<@{user}> Processing your Excel file... 🔄", thread_ts=thread_ts)

    try:
        # Download the file
        token = os.environ.get("SLACK_BOT_TOKEN")
        file_content = download_slack_file(xlsx_file, token)

        # Create temp files for input/output
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.xlsx"
            output_path = Path(tmpdir) / "output.xlsx"

            # Write input file
            input_path.write_bytes(file_content)
            # Copy to output (agent will modify it)
            output_path.write_bytes(file_content)

            # Run the AI agent
            agent_response = asyncio.run(
                process_excel_task(input_path, output_path, instruction)
            )

            # Upload the result
            client.files_upload_v2(
                channel=channel,
                file=str(output_path),
                filename=xlsx_file.get("name", "result.xlsx").replace(
                    ".xlsx", "_processed.xlsx"
                ),
                initial_comment=f"<@{user}> Done! ✅\n\n{agent_response}",
                thread_ts=thread_ts,
            )

    except asyncio.TimeoutError:
        say(
            text=f"<@{user}> Sorry, the task timed out. Try simplifying your request.",
            thread_ts=thread_ts,
        )
    except Exception as e:
        say(
            text=f"<@{user}> Error processing file: {str(e)[:200]}", thread_ts=thread_ts
        )


def main():
    # Check required tokens
    if not os.environ.get("SLACK_BOT_TOKEN"):
        print("Error: SLACK_BOT_TOKEN not set")
        sys.exit(1)
    if not os.environ.get("SLACK_APP_TOKEN"):
        print("Error: SLACK_APP_TOKEN not set")
        sys.exit(1)

    # Start MCP server in background
    import threading

    def start_mcp():
        asyncio.run(run_mcp_server())

    mcp_thread = threading.Thread(target=start_mcp, daemon=True)
    mcp_thread.start()

    # Give MCP server time to start
    import time

    time.sleep(2)

    print("🤖 Excel Agent Bot is running!")
    print("   Mention me with an .xlsx file and describe what you want.")
    print(f"   Model: {MODEL}")

    # Start Slack bot
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()


if __name__ == "__main__":
    main()
