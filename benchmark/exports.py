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
    "task_id", "module", "category", "intent", "target", "question", "expected_answer_type", "expected_columns", "answer_verification_status", "ra_deg", "dec_deg",
    "radius_arcmin", "catalog", "mcp_tool", "mcp_function", "mcp_parameters_json",
    "validation_status", "execution_track", "generation_backend", "web_search_sources",
)
REFERENCE_COLUMNS = (
    "task_id", "module", "question", "target", "intent", "expected_columns", "disposition", "reason",
    "returned_rows", "reported_total_rows", "table_count", "truncated",
    "response_bytes", "response_sha256", "attempt_count", "error_message",
    "reference_call_json", "reference_answer_status", "reference_answer_values_json",
    "matched_fields", "matching_values_count", "returned_table_columns", "observed_first_row_json",
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
    args = (record.get("reference_call") or {}).get("arguments", {})
    return dict(task_id=record.get("id"), module=record.get("module"),
                category=record.get("category"), intent=record.get("intent", ""), target=record.get("target"),
                question=record.get("question"),
                expected_answer_type=record.get("answer_spec", {}).get("answer_type", ""),
                expected_columns=";".join(record.get("answer_spec", {}).get("expected_columns", [])),
                answer_verification_status=record.get("answer_spec", {}).get("expected_answer_status", ""),
                ra_deg=center.get("ra_deg", ""),
                dec_deg=center.get("dec_deg", ""),
                radius_arcmin=constraints.get("radius", {}).get("value", ""),
                catalog=constraints.get("catalog", ""),
                mcp_tool=(record.get("reference_call") or {}).get("tool"),
                mcp_function=args.get("function_name"),
                mcp_parameters_json=json_compact(args.get("params", {})),
                validation_status=record.get("validation_status"),
                execution_track=record.get("execution_track", "astroquery_mcp"),
                generation_backend=record.get("provenance", {}).get("generation_backend", "template"),
                web_search_sources=";".join(record.get("research_sources", [])))


def observed_reference_values(record: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Extract field observations only when requested columns actually occur.

    A structural MCP result is NOT a scientifically reviewed expected answer.
    No model-written values or best-effort field substitutions are allowed.
    """
    disposition = record.get("disposition", "")
    if disposition != "accepted_nonempty":
        return {"status": "NO_NONEMPTY_REFERENCE", "values": [], "fields": [], "count": 0}
    expected = task.get("answer_spec", {}).get("expected_columns", [])
    if not isinstance(expected, list):
        expected = []
    wanted = {c.strip().casefold() for c in expected if isinstance(c, str) and c.strip()}
    response = record.get("response") or {}
    from .validator import _tables
    tables, _ = _tables(response.get("result"))
    values, fields, count = [], set(), 0
    for ti, table in enumerate(tables):
        for ri, row in enumerate(table.get("data", [])):
            if not isinstance(row, dict):
                continue
            for field, value in row.items():
                if isinstance(field, str) and field.strip().casefold() in wanted:
                    count += 1
                    fields.add(field)
                    if len(values) < 100:
                        values.append({"table_index": ti, "row_index": ri,
                                       "field": field, "value": value})
    return {"status": ("OBSERVED_FIELD_VALUES_UNREVIEWED" if count else
                        "NO_EXPECTED_FIELD_MATCH_REVIEW_REQUIRED"),
            "values": values, "fields": sorted(fields), "count": count}


def reference_csv_record(record: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    evidence = record.get("evaluation", {}).get("checks", {})
    attempts = record.get("attempts", [])
    last = attempts[-1] if attempts else {}
    observed = observed_reference_values(record, task)
    response = record.get("response") or {}
    from .validator import _tables
    tables, _ = _tables(response.get("result"))
    first = next((r for t in tables for r in t.get("data", []) if isinstance(r, dict)), {})
    preview = {k: first[k] for k in list(first)[:12]}
    known_columns = sorted(set(k for t in tables for r in t.get("data", [])[:1]
                               if isinstance(r, dict) for k in r))
    return dict(task_id=record.get("task_id"), module=record.get("module"),
                question=task.get("question"), target=task.get("target"),
                intent=task.get("intent", ""),
                expected_columns=";".join(task.get("answer_spec", {}).get("expected_columns", [])),
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
                reference_call_json=json_compact(record.get("reference_call", {})),
                reference_answer_status=observed["status"],
                reference_answer_values_json=json_compact(observed["values"]),
                matched_fields=";".join(observed["fields"]),
                matching_values_count=observed["count"],
                returned_table_columns=";".join(known_columns[:120]),
                observed_first_row_json=json_compact(preview))


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
