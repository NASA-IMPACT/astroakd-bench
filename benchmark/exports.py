"""Optional human-readable and spreadsheet exports for canonical benchmark JSONL.

All exports are secondary views: no input JSONL bytes or canonical fingerprints
are changed. Writes are atomic, fail closed on output collisions, and never
execute spreadsheet formulas found in untrusted task text.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from .validator import ValidationError, atomic_json


CANDIDATE_COLUMNS = (
    "task_id", "module", "category", "target", "question", "ra_deg", "dec_deg",
    "radius_arcmin", "catalog", "mcp_tool", "mcp_function", "mcp_parameters_json",
    "validation_status",
)
REFERENCE_COLUMNS = (
    "task_id", "module", "question", "target", "disposition", "reason",
    "returned_rows", "reported_total_rows", "table_count", "truncated",
    "response_bytes", "response_sha256", "attempt_count", "error_message",
    "reference_call_json",
)


def check_destinations(input_path: Path | None, output: Path, report: Path | None,
                       pretty: Path | None, csv_path: Path | None, *,
                       replace: bool = False, extras: Iterable[Path] = ()) -> None:
    paths = {"output": output}
    if input_path is not None:
        paths["input"] = input_path
    if report is not None:
        paths["report"] = report
    if pretty is not None:
        if pretty.suffix.lower() != ".json":
            raise ValidationError("--pretty-output must end in .json")
        paths["pretty"] = pretty
    if csv_path is not None:
        if csv_path.suffix.lower() != ".csv":
            raise ValidationError("--csv-output must end in .csv")
        paths["csv"] = csv_path
    for i, extra in enumerate(extras):
        paths[f"reserved_{i}"] = extra
    seen = {}
    for name, path in paths.items():
        absolute = path.resolve()
        if absolute in seen:
            raise ValidationError(f"Destination collision: {name} and {seen[absolute]} ({path})")
        seen[absolute] = name
        if name in {"pretty", "csv"} and path.exists() and not replace:
            raise ValidationError(f"Optional export exists: {path}; use --replace or a new filename")


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def candidate_csv_record(record: dict[str, Any]) -> dict[str, Any]:
    constraints = record.get("constraints", {})
    center = constraints.get("center_icrs", {})
    args = record.get("reference_call", {}).get("arguments", {})
    return dict(task_id=record.get("id"), module=record.get("module"),
                category=record.get("category"), target=record.get("target"),
                question=record.get("question"), ra_deg=center.get("ra_deg", ""),
                dec_deg=center.get("dec_deg", ""),
                radius_arcmin=constraints.get("radius", {}).get("value", ""),
                catalog=constraints.get("catalog", ""),
                mcp_tool=record.get("reference_call", {}).get("tool"),
                mcp_function=args.get("function_name"),
                mcp_parameters_json=json_compact(args.get("params", {})),
                validation_status=record.get("validation_status"))


def reference_csv_record(record: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    evidence = record.get("evaluation", {}).get("checks", {})
    attempts = record.get("attempts", [])
    last = attempts[-1] if attempts else {}
    return dict(task_id=record.get("task_id"), module=record.get("module"),
                question=task.get("question"), target=task.get("target"),
                disposition=record.get("disposition"),
                reason=record.get("evaluation", {}).get("reason", ""),
                returned_rows=evidence.get("returned_rows", ""),
                reported_total_rows=evidence.get("reported_total_rows", ""),
                table_count=evidence.get("table_count", ""),
                truncated=evidence.get("truncated", ""),
                response_bytes=last.get("response_bytes", ""),
                response_sha256=last.get("response_sha256", ""),
                attempt_count=len(attempts),
                error_message=record.get("error", {}).get("message", ""),
                reference_call_json=json_compact(record.get("reference_call", {})))


def _neutralize_csv_formula(value: Any) -> Any:
    # CSV is for human spreadsheet inspection: prevent formula injection.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def atomic_csv(path: Path, records: list[dict[str, Any]], columns: tuple[str, ...],
               *, replace: bool = False) -> None:
    if path.exists() and not replace:
        raise ValidationError(f"CSV already exists: {path}; use --replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".astroakd-",
                                         suffix=".tmp", delete=False, encoding="utf-8", newline="") as stream:
            temp = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow({c: _neutralize_csv_formula(record.get(c, "")) for c in columns})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def save_views(records: list[dict[str, Any]], *, pretty: Path | None = None,
               csv_path: Path | None = None, kind: str = "candidate",
               tasks: dict[str, dict[str, Any]] | None = None,
               replace: bool = False) -> None:
    if csv_path is not None:
        if kind == "candidate":
            rows = [candidate_csv_record(r) for r in records]
            cols = CANDIDATE_COLUMNS
        elif kind == "reference":
            tasks = tasks or {}
            rows = [reference_csv_record(r, tasks.get(r.get("task_id"), {})) for r in records]
            cols = REFERENCE_COLUMNS
        else:
            raise ValidationError("Unknown export kind")
        atomic_csv(csv_path, rows, cols, replace=replace)
    if pretty is not None:
        atomic_json(pretty, records, replace=replace, style="pretty")
