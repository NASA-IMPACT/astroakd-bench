"""AstroAKD-Bench: discovery, generation, validation and agent tracing."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

from . import DEFAULT_MCP_URL, __version__
from .client import AstroqueryMCPClient, normalize
from .diagnostics import doctor
from .errors import BenchmarkError
from .generator import GenerationError, SUPPORTED_MODULES, generate, parse_modules, write_jsonl
from .validator import ValidationError, validate, EXPECTED_ACCEPTED_020_SHA256
from .agent_runner import AgentRunError, run_agents
from .evaluator import EvaluationError, evaluate
from .formatting import json_text, inspect_file

DEFAULT_DATASET = Path("datasets/generated/synthetic_queries.jsonl")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astroakd-bench",
        description="AstroAKD-Bench 0.6.1 generation, reusable API, semantic replay and scoring.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mcp-url", default=os.environ.get("ASTROAKD_MCP_URL", DEFAULT_MCP_URL))
    common.add_argument("--timeout", type=float, default=180.0,
                        help="Timeout per MCP operation, seconds (default: 180)")
    common.add_argument('--json-format', choices=('compact','pretty'), default='compact',
                        help='JSON stdout and summary-report rendering (default: compact). JSONL stays one-record-per-line.')
    commands = parser.add_subparsers(dest="command", required=True)

    diag = commands.add_parser("doctor", parents=[common],
        help="Connection, tool catalog, module and signature checks")
    diag.add_argument("--output", type=Path, help="Save JSON report to this file")
    diag.add_argument("--fast", action="store_true", help="Skip expensive function introspection")
    diag.add_argument("--smoke", action="store_true", help="Also run a live SIMBAD object query")
    diag.add_argument("--object", default="M31", help="SIMBAD object for --smoke (default: M31)")
    for cmd, help_text in (
        ("tools", "Discover MCP tool catalog"),
        ("modules", "List available Astroquery modules"),
    ):
        sub = commands.add_parser(cmd, parents=[common], help=help_text)
        sub.add_argument("--output", type=Path, help="Save JSON report to this file")
    funcs = commands.add_parser("functions", parents=[common], help="Discover functions in a module")
    funcs.add_argument("--output", type=Path)
    funcs.add_argument("--module", default="simbad")
    info = commands.add_parser("info", parents=[common], help="Get one function's signature")
    info.add_argument("--output", type=Path)
    info.add_argument("--module", default="simbad")
    info.add_argument("--function", default="query_object")
    smoke = commands.add_parser("simbad", parents=[common], help="Run a single live read-only SIMBAD query")
    smoke.add_argument("--output", type=Path)
    smoke.add_argument("--object", default="M31")

    gen = commands.add_parser("generate", parents=[common],
                              help="Generate schema-checked candidates; NO archive queries")
    gen.add_argument("--count", type=int, default=50, help="Number of candidates, 1..500 (default: 50)")
    gen.add_argument("--seed", type=int, default=42, help="Deterministic seed (default: 42)")
    gen.add_argument("--modules", default=",".join(SUPPORTED_MODULES),
                     help="Comma-separated subset of simbad,mast,heasarc,gaia,vizier")
    gen.add_argument("--output", type=Path, default=DEFAULT_DATASET,
                     help="JSONL destination (default: %(default)s)")
    gen.add_argument("--replace", action="store_true", help="Overwrite existing JSONL dataset")
    gen.add_argument("--report", type=Path, help="Save JSON generation summary separately")
    validation = commands.add_parser("validate", parents=[common],
        help="Run accepted candidate calls through live MCP, retaining all outcomes")
    validation.add_argument("--input", type=Path, default=DEFAULT_DATASET,
        help="0.2.0 candidate JSONL dataset")
    validation.add_argument("--output", type=Path, default=Path("datasets/validated/reference_answers.jsonl"),
        help="Validated reference JSONL destination")
    validation.add_argument("--report", type=Path, default=Path("datasets/validated/validation_report.json"),
        help="Summary report path")
    validation.add_argument("--attempts", type=int, default=2,
        help="Maximum attempts per reference query (default: 2)")
    validation.add_argument("--delay", type=float, default=2.0,
        help="Seconds between queries, exponential between retries (default: 2)")
    validation.add_argument("--max-rows", type=int, default=20,
        help="Limit rows returned by MAST query_region (default: 20)")
    validation.add_argument("--max-response-bytes", type=int, default=8 * 1024 * 1024)
    validation.add_argument("--limit", type=int,
        help="Process at most N remaining tasks in this invocation")
    validation.add_argument("--resume", action="store_true",
        help="Continue from fsynced per-task journal; do not re-execute completed IDs")
    validation.add_argument("--replace", action="store_true",
        help="Discard previous output and journal, and start a new run")
    validation.add_argument("--strict-accepted-020", action="store_true",
        help="Require SHA256 of the formally accepted 50-task seed=42 dataset")
    run = commands.add_parser("run", parents=[common],
        help="Execute agent with question-derived routing and auditable MCP traces")
    run.add_argument("--tasks", type=Path, default=DEFAULT_DATASET,
        help="0.2.0 generated candidate JSONL")
    run.add_argument("--references", type=Path,
        default=Path("datasets/validated/reference_answers.jsonl"),
        help="0.3.0 accepted reference JSONL (not passed to the agent)")
    run.add_argument("--output", type=Path,
        default=Path("datasets/agent/agent_runs.jsonl"),
        help="Agent results and tool traces JSONL")
    run.add_argument("--report", type=Path,
        default=Path("datasets/agent/run_report.json"))
    run.add_argument("--agent", choices=("openai", "external", "echo"), default="openai",
        help="openai=real optional LLM, external=user adapter, echo=harness check ONLY")
    run.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model name")
    run.add_argument("--adapter", help="External async adapter, e.g. my_agent.adapter:run")
    run.add_argument("--max-turns", type=int, default=8)
    run.add_argument("--max-calls", type=int, default=12)
    run.add_argument("--max-tool-bytes", type=int, default=65536)
    run.add_argument("--task-timeout", type=float, default=600)
    run.add_argument("--limit", type=int, help="Number of remaining tasks to run")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--replace", action="store_true")
    run.add_argument("--mcp-mode", choices=("live", "record", "replay"), default="live",
        help="live MCP HTTP, record MCP calls into a fixture, or replay offline")
    run.add_argument("--fixtures", type=Path,
        help="Replay fixture JSON file; required for record and replay modes")
    run.add_argument("--strict-accepted-020", action="store_true",
        help="Require frozen accepted 50-task candidate dataset")
    score = commands.add_parser('evaluate', parents=[common],
        help='Score recorded agent traces against validated reference responses; no API calls')
    score.add_argument('--tasks', type=Path, default=DEFAULT_DATASET)
    score.add_argument('--references', type=Path, default=Path('datasets/validated/reference_answers.jsonl'))
    score.add_argument('--runs', type=Path, default=Path('datasets/agent/openai_041_runs.jsonl.progress.jsonl'))
    score.add_argument('--output', type=Path, default=Path('datasets/evaluation/task_scores.jsonl'))
    score.add_argument('--report', type=Path, default=Path('datasets/evaluation/evaluation_report.json'))
    score.add_argument('--csv', type=Path, default=Path('datasets/evaluation/task_scores.csv'))
    score.add_argument('--pretty-output', type=Path,
        help='Save all per-task scores as an indented JSON array (.json) alongside compact JSONL')
    score.add_argument('--strict-accepted-020', action='store_true')
    score.add_argument('--replace', action='store_true')
    fixture = commands.add_parser('build-fixtures', parents=[common],
        help='Construct offline MCP fixtures from accepted reference responses; NO network calls')
    fixture.add_argument('--tasks', type=Path, default=DEFAULT_DATASET)
    fixture.add_argument('--references', type=Path, default=Path('datasets/validated/reference_answers.jsonl'))
    fixture.add_argument('--output', type=Path, default=Path('datasets/replay/reference_fixtures.json'))
    fixture.add_argument('--strict-accepted-020', action='store_true')
    fixture.add_argument('--replace', action='store_true')
    inspect = commands.add_parser('inspect', parents=[common],
        help='Render a bounded JSONL sample or a JSON report for inspection')
    inspect.add_argument('--input', required=True, type=Path)
    inspect.add_argument('--limit', type=int, default=3)
    inspect.add_argument('--output', type=Path)
    return parser


async def _execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == 'build-fixtures':
        from .replay import build_reference_fixtures
        return build_reference_fixtures(args.tasks, args.references, args.output,
                                       strict_accepted_020=args.strict_accepted_020,
                                       replace=args.replace)
    if args.command == 'inspect':
        return inspect_file(args.input, args.limit)
    if args.command == 'evaluate':
        return evaluate(args.tasks,args.references,args.runs,args.output,args.report,
                        csv_path=args.csv,pretty_output=args.pretty_output,
                        strict_accepted_020=args.strict_accepted_020,
                        json_format=args.json_format,replace=args.replace)
    if args.command == "doctor":
        return await doctor(
            args.mcp_url, timeout=args.timeout, fast=args.fast,
            smoke=args.smoke, object_name=args.object,
        )
    if args.command == "validate":
        return await validate(
            args.input, args.output, args.report, url=args.mcp_url,
            timeout=args.timeout, attempts=args.attempts, delay=args.delay,
            max_rows=args.max_rows, max_response_bytes=args.max_response_bytes,
            limit=args.limit, resume=args.resume, replace=args.replace,
            strict_sha256=(EXPECTED_ACCEPTED_020_SHA256
                           if args.strict_accepted_020 else None), json_format=args.json_format,
        )
    if args.command == "run":
        return await run_agents(
            args.tasks, args.references, args.output, args.report,
            url=args.mcp_url, timeout=args.timeout, agent_name=args.agent,
            model=args.model, adapter=args.adapter, max_turns=args.max_turns,
            max_calls=args.max_calls, max_tool_bytes=args.max_tool_bytes,
            task_timeout=args.task_timeout, limit=args.limit,
            resume=args.resume, replace=args.replace,
            strict_accepted_020=args.strict_accepted_020, json_format=args.json_format,
            mcp_mode=args.mcp_mode, fixtures=args.fixtures,
        )
    if args.command == "generate":
        if args.output.exists() and not args.replace:
            raise GenerationError(f"Output exists: {args.output}; pass --replace to overwrite")
        modules = parse_modules(args.modules)
        candidates, summary = await generate(
            args.mcp_url, count=args.count, seed=args.seed, modules=modules,
            timeout=args.timeout,
        )
        summary["dataset_sha256"] = write_jsonl(args.output, candidates, replace=args.replace)
        summary["output"] = str(args.output)
        return summary

    async with AstroqueryMCPClient(args.mcp_url, timeout=args.timeout) as client:
        if args.command == "tools":
            result = await client.list_tools()
        elif args.command == "modules":
            result = await client.list_modules()
        elif args.command == "functions":
            result = await client.list_functions(args.module)
        elif args.command == "info":
            result = await client.function_info(args.module, args.function)
        elif args.command == "simbad":
            result = await client.simbad_object(args.object)
        else:
            raise ValueError(f"Unknown command: {args.command}")
    return {"status": "PASS", "endpoint": args.mcp_url,
            "command": args.command, "data": normalize(result)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = asyncio.run(_execute(args))
    except (BenchmarkError, GenerationError, ValidationError, AgentRunError, EvaluationError, ValueError, OSError) as exc:
        payload = {"status": "FAIL", "command": args.command,
                   "endpoint": args.mcp_url, "error": {"type": type(exc).__name__,
                   "message": str(exc)}}
    output = json_text(payload, args.json_format)
    print(output)
    report_destination = (None if args.command in {"validate", "run", "evaluate", "build-fixtures"} else
                          args.report if args.command == "generate" else args.output)
    if report_destination is not None:
        try:
            report_destination.parent.mkdir(parents=True, exist_ok=True)
            report_destination.write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Could not save report {report_destination}: {exc}", file=sys.stderr)
            return 2
    return 0 if payload.get("status") in {"PASS", "PARTIAL", "COMPLETE"} or (args.command == "inspect" and "data" in payload or args.command == "inspect" and "records" in payload) else 1


if __name__ == "__main__":
    raise SystemExit(main())
