# Slack Excel Workflow

A Slack bot that processes Excel files using the AI agent. Mention the bot with an attached `.xlsx` file and describe the task.

## Setup

1. Create a Slack App at https://api.slack.com/apps
2. Enable Socket Mode and generate an App-Level Token
3. Add Bot Token Scopes: `app_mentions:read`, `chat:write`, `files:read`, `files:write`
4. Subscribe to bot events: `app_mention`
5. Set environment variables in `SlackExcelWorkflow/.env`
   ```bash
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   EXCEL_AGENT_MODEL=openrouter:...
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

## Run
Assuming you've set up the `excel` conda environment:
```bash
conda activate excel
python excel_agent_bot.py
```

## Usage

In Slack, mention the bot with an attached Excel file:

> @ExcelBot Please add a SUM formula in cell E2 that totals A2:D2
