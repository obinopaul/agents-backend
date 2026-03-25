# Excel Agent Evaluation

This directory contains the evaluation harness for testing the Excel Agent against spreadsheet manipulation tasks.

## Usage

### Running Evaluations

Run the evaluation script with:

```bash
python run_eval.py
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset` | `data/dataset.json` | Path to the dataset JSON file |
| `--output-dir` | `eval_outputs` | Directory for evaluation outputs |
| `--model` | `openrouter:openai/gpt-5.1` | Model identifier to use |
| `--timeout` | `600.0` | Timeout per task in seconds |
| `--max-cases` | None | Limit number of cases to run |
| `--subset-ids` | None | Run only specific case IDs |
| `--eval-id` | None | Re-evaluate existing outputs (comparison mode) |

### Examples

Run evaluation on all cases:
```bash
python run_eval.py
```

Run with a specific model and limit to 10 cases:
```bash
python run_eval.py --model anthropic:claude-sonnet-4-20250514 --max-cases 10
```

Run specific test cases by ID:
```bash
python run_eval.py --subset-ids CF_12518 52763 6698
```

Re-evaluate outputs from a previous run (without re-running the agent):
```bash
python run_eval.py --eval-id eval_20251209_16:00:24
```

### Output

Results are saved to `eval_outputs/eval_<timestamp>/` containing:
- `*_output.xlsx` - Agent-generated output files
- `report.json` - Evaluation config and execution traces

## Data

The evaluation dataset consists of **50 random examples** from [SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench) which have been manually examined and vetted for quality and correctness.

### Pulling Data

The spreadsheet files are stored using Git LFS. To pull the data:

```bash
git lfs pull
```

### Dataset Structure

- `data/dataset.json` - Contains task metadata, instructions, and notes on any alterations from the original SpreadsheetBench dataset
- `data/sb_verified/<id>/` - Verified spreadsheet pairs:
  - `1_<id>_input.xlsx` - Input spreadsheet
  - `1_<id>_answer.xlsx` - Ground truth answer

### Dataset Fields

Each entry in `dataset.json` includes:

| Field | Description |
|-------|-------------|
| `id` | Unique task identifier |
| `instruction` | Natural language task description |
| `instruction_type` | Category (Cell-Level or Sheet-Level Manipulation) |
| `answer_position` | Cell range(s) to compare against ground truth |
| `answer_sheet` | Sheet name for answer (if applicable) |
| `formatting` | Whether to check conditional formatting |
| `notes` | Documentation of any fixes or alterations from original dataset |
