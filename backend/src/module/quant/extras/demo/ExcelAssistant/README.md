# Excel Assistant

A web app for editing spreadsheets with an AI assistant that modifies your files via natural language.

## Quick Start
Setup environment variables in `ExcelAssistant/.env`
```bash
EXCEL_ASSISTANT_MODEL=openrouter:...
OPENROUTER_API_KEY=sk-or-v1-...
```

Then, assuming you've already setup the `excel` conda environment:
```bash
# Terminal 1: Backend
conda activate excel
python server.py

# Terminal 2: Frontend
npm install
npm run dev
```

Open http://localhost:3000, upload an Excel file, and use the chat sidebar to give instructions like:

- "Sum column A and put the result in B1"
- "Add a formula to calculate the average of C1:C10"
