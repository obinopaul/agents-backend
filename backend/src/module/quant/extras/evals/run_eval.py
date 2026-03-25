"""Run Excel Agent evaluation from command line."""

from pathlib import Path
from dotenv import load_dotenv

import asyncio
import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    EvaluationReason,
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
)

from excel_agent.agent_runner import ExcelAgentRunner, TaskInput
from excel_agent.config import ExperimentConfig, TraceCollector
from excel_mcp.excel_server import mcp

from comparison import compare_workbooks

env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    print(f"⚠️  Warning: .env file not found at {env_path}")
else:
    load_dotenv(env_path)
    print(f"✓ Loaded .env from {env_path}")

# Server configuration
MCP_SERVER_HOST = "127.0.0.1"
MCP_SERVER_PORT = 8765
MCP_SERVER_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"


@dataclass
class TaskMetadata:
    """Metadata for evaluating an Excel task."""

    id: str
    instruction_type: str
    answer_position: str
    answer_file: str
    check_style: bool = False


class ExcelEvaluator(Evaluator[TaskInput, str, TaskMetadata]):
    """Compares output Excel file against ground truth using cell-level comparison."""

    def evaluate(
        self, ctx: EvaluatorContext[TaskInput, str, TaskMetadata]
    ) -> EvaluatorOutput:
        if not ctx.metadata or not Path(ctx.inputs.output_file).exists():
            return {
                "pass": EvaluationReason(
                    value=False, reason="Missing metadata or output file"
                )
            }

        try:
            result = compare_workbooks(
                ctx.metadata.answer_file,
                ctx.inputs.output_file,
                ctx.metadata.answer_position,
                check_style=ctx.metadata.check_style,
            )
            reason = str(result) if not result.is_match else "Cells match"
            return {
                "correct_count": result.correct_count,
                "total_count": result.total_count,
                "reason": reason,
                "pass": EvaluationReason(value=result.is_match, reason=reason),
            }
        except Exception as e:
            return {"pass": EvaluationReason(value=False, reason=str(e))}


def load_case(
    data: dict,
    dataset_dir: Path,
    output_file: Path,
    copy_input: bool = True,
) -> Case:
    """Load a single test case from dataset entry."""
    data_id = str(data["id"])
    spread_dir = dataset_dir / "sb_verified" / data_id
    
    # Extract test index from output filename (e.g., "1_CF_9945_output.xlsx" -> 1)
    test_idx = output_file.stem.split("_")[0] if output_file.stem[0].isdigit() else "1"
    
    input_file = spread_dir / f"{test_idx}_{data_id}_input.xlsx"
    answer_file = spread_dir / f"{test_idx}_{data_id}_answer.xlsx"

    if copy_input:
        output_file.parent.mkdir(exist_ok=True)
        shutil.copy(input_file, output_file)

    answer_pos = data["answer_position"]
    if "answer_sheet" in data and "," not in answer_pos and "!" not in answer_pos:
        answer_pos = f"{data['answer_sheet']}!{answer_pos}"

    return Case(
        name=f"{data_id}_test{test_idx}",
        inputs=TaskInput(data["instruction"], str(input_file), str(output_file)),
        metadata=TaskMetadata(
            data_id,
            data["instruction_type"],
            answer_pos,
            str(answer_file),
            check_style=data.get("formatting", False),
        ),
    )


async def start_mcp_server(host: str = MCP_SERVER_HOST, port: int = MCP_SERVER_PORT):
    """Start the FastMCP server as an SSE HTTP server."""
    await mcp.run_sse_async(host=host, port=port, log_level="warning")


def parse_case_id_from_filename(filename: str) -> str | None:
    """Parse case ID from output filename (e.g., '1_CF_29431_output' -> 'CF_29431')."""
    parts = filename.replace("_output", "").split("_", 1)
    return parts[1] if len(parts) >= 2 else None


def load_dataset(dataset_path: Path) -> tuple[Path, list[dict], dict[str, dict]]:
    """Load dataset and return (dataset_dir, all_data, data_by_id)."""
    with open(dataset_path) as f:
        all_data = json.load(f)
    data_by_id = {str(item["id"]): item for item in all_data}
    return dataset_path.parent, all_data, data_by_id


def select_cases(
    all_data: list[dict],
    data_by_id: dict[str, dict],
    subset_ids: list[str] | None,
    max_cases: int | None,
) -> list[dict]:
    """Select which cases to run based on filters."""
    if subset_ids:
        selected = []
        for case_id in subset_ids:
            if case_id in data_by_id:
                selected.append(data_by_id[case_id])
            else:
                print(f"⚠️  Warning: case ID '{case_id}' not found in dataset")
        return selected
    
    selected = all_data
    if max_cases:
        selected = selected[:max_cases]
    return selected


async def run_evaluation(args):
    """Run agent evaluation on new cases."""
    dataset_dir, all_data, data_by_id = load_dataset(Path(args.dataset))
    selected_data = select_cases(all_data, data_by_id, args.subset_ids, args.max_cases)

    pacific_tz = timezone(timedelta(hours=-8))
    output_path = Path(args.output_dir) / f"eval_{datetime.now(pacific_tz).strftime('%Y%m%d_%H:%M:%S')}"
    output_path.mkdir(parents=True, exist_ok=True)

    cases = [
        load_case(data, dataset_dir, output_path / f"1_{data['id']}_output.xlsx")
        for data in selected_data
    ]
    print(f"📊 Evaluating {len(cases)} cases: {[c.name for c in cases][:5]}{'...' if len(cases) > 5 else ''}")
    dataset: Dataset[TaskInput, str, TaskMetadata] = Dataset(
        name="excel_eval", cases=cases, evaluators=[ExcelEvaluator()]
    )

    config = ExperimentConfig(model=args.model, timeout=args.timeout)
    trace_collector = TraceCollector()
    server_task = asyncio.create_task(start_mcp_server())
    await asyncio.sleep(1)

    agent_runner = ExcelAgentRunner(
        config=config, trace_collector=trace_collector, mcp_server_url=MCP_SERVER_URL
    )

    async def debug_runner(inputs: TaskInput) -> str:
        result = await agent_runner.run_excel_agent(inputs)
        print(f"\n🤖 Agent output for {inputs.output_file}:\n{result[:500]}{'...' if len(result) > 500 else ''}\n")
        return result

    try:
        report = await dataset.evaluate(debug_runner, metadata=config.model_dump())
        report.print()
        with open(output_path / "report.json", "w") as f:
            json.dump({"config": config.model_dump(), "traces": trace_collector.traces}, f, indent=2)
        print(f"\n📁 Results saved to: {output_path}")
    except KeyboardInterrupt:
        print("Keyboard interrupt received, shutting down...")
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


async def run_comparison(args):
    """Re-evaluate existing outputs without running agent."""
    eval_dir = Path(args.output_dir) / args.eval_id
    if not eval_dir.exists():
        print(f"❌ Eval directory not found: {eval_dir}")
        return

    print(f"📂 Re-evaluating outputs from: {eval_dir}")
    dataset_dir, all_data, data_by_id = load_dataset(Path(args.dataset))

    # Get all valid output files
    all_output_files = []
    for f in sorted(eval_dir.glob("*_output.xlsx")):
        if f.name.startswith("~$"):
            continue
        case_id = parse_case_id_from_filename(f.stem)
        if case_id and case_id in data_by_id:
            all_output_files.append((case_id, f))
    
    # Apply same filters as run_evaluation (subset_ids, max_cases)
    if args.subset_ids:
        all_output_files = [(cid, f) for cid, f in all_output_files if cid in args.subset_ids]
    if args.max_cases:
        all_output_files = all_output_files[:args.max_cases]
    
    if not all_output_files:
        print(f"❌ No valid output files found in {eval_dir}")
        return

    cases = [
        load_case(data_by_id[case_id], dataset_dir, f, copy_input=False)
        for case_id, f in all_output_files
    ]
    print(f"📊 Re-evaluating {len(cases)} cases: {[c.name for c in cases][:5]}{'...' if len(cases) > 5 else ''}")

    dataset: Dataset[TaskInput, str, TaskMetadata] = Dataset(
        name="excel_eval", cases=cases, evaluators=[ExcelEvaluator()]
    )
    report = await dataset.evaluate(lambda _: "")
    report.print()


async def main():
    parser = argparse.ArgumentParser(description="Run Excel agent evaluation")
    parser.add_argument("--dataset", default="data/dataset.json")
    parser.add_argument("--output-dir", default="eval_outputs")
    parser.add_argument("--model", default="openrouter:openai/gpt-5.1")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--subset-ids", nargs="+", default=None)
    parser.add_argument("--eval-id", default=None, help="Re-evaluate existing eval outputs")
    args = parser.parse_args()

    if args.eval_id:
        await run_comparison(args)
    else:
        await run_evaluation(args)


if __name__ == "__main__":
    asyncio.run(main())
