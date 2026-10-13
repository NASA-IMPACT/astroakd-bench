"""Milestone 0.3.0: bounded, resumable live reference validation over HTTP MCP.

This module deliberately does not import Astroquery, alter the server, or generate
new questions. It records the actual MCP result and evidence of its validation.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable

from . import __version__, DEFAULT_MCP_URL
from .client import AstroqueryMCPClient
from .errors import MCPConnectionError, MCPResponseError, MCPToolError, MCPTransportError
from .generator import SAFE_METHODS, discover_bindings, generate_candidates
from .seeds import RADII_ARCMIN, HEASARC_CATALOGS, VIZIER_CATALOGS, TARGETS

EXPECTED_ACCEPTED_020_SHA256 = "e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9"
SUCCESS_DISPOSITIONS = frozenset({"accepted_nonempty", "accepted_empty"})
RETRYABLE_ERRORS = (MCPTransportError, MCPConnectionError, TimeoutError)


class ValidationError(ValueError):
    """Invalid dataset, unsafe call, or inconsistent validation state."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def atomic_json(path: Path, value: Any, *, replace: bool = True, style: str = 'compact') -> None:
    if path.exists() and not replace:
        raise ValidationError(f"Output already exists: {path}")
    from .formatting import json_text
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".astroakd-",
                                         suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(json_text(value, style).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() and not replace:
            raise ValidationError(f"Output already exists: {path}")
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def atomic_jsonl(path: Path, records: list[dict[str, Any]], *, replace: bool = False) -> str:
    if path.exists() and not replace:
        raise ValidationError(f"Output already exists: {path}; use --replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = b"".join(json_bytes(record) + b"\n" for record in records)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".astroakd-",
                                         suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() and not replace:
            raise ValidationError(f"Output already exists: {path}; use --replace")
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return hashlib.sha256(blob).hexdigest()


def append_journal(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(json_bytes(record) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def load_jsonl(path: Path, *, max_bytes: int = 20 * 1024 * 1024) -> tuple[list[dict[str, Any]], str]:
    if not path.is_file():
        raise ValidationError(f"Dataset not found: {path}")
    if path.stat().st_size > max_bytes:
        raise ValidationError(f"Dataset is larger than {max_bytes} bytes")
    blob = path.read_bytes()
    if not blob.strip():
        raise ValidationError("Dataset is empty")
    records = []
    try:
        for i, line in enumerate(blob.splitlines(), start=1):
            if not line.strip():
                raise ValidationError(f"Blank line at {i} is not allowed")
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValidationError(f"Line {i} is not a JSON object")
            records.append(record)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid JSONL dataset: {exc}") from exc
    return records, hashlib.sha256(blob).hexdigest()


def check_dataset(records: list[dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    if not 1 <= len(records) <= 500:
        raise ValidationError("Dataset must contain 1..500 candidates")
    ids: set[str] = set()
    schema: set[str] = set()
    modules: set[str] = set()
    for index, record in enumerate(records, 1):
        ident = record.get("id")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValidationError(f"Invalid or duplicate task ID at record {index}")
        ids.add(ident)
        module = record.get("module")
        if module not in SAFE_METHODS:
            raise ValidationError(f"Unsafe/unsupported module in {ident}: {module}")
        modules.add(module)
        if record.get('execution_track') == 'openai_web_search_research':
            raise ValidationError(f'Task {ident} is a no-MCP web-search research candidate. '
                                  'The validate command accepts only MCP executable tasks; '
                                  'regenerate with --mcp to validate.')
        if record.get("validation_status") != "candidate_unvalidated":
            raise ValidationError(f"Task {ident} was not an unvalidated 0.2.0 candidate")
        call = record.get("reference_call")
        if not isinstance(call, dict) or call.get("tool") != "astroquery_execute":
            if record.get('execution_track') == 'openai_web_search_research':
                raise ValidationError(f"Task {ident} is a no-MCP web-search research candidate. "
                                      "The validate command only accepts MCP-bound executable tasks; "
                                      "regenerate with --mcp, then validate the new dataset.")
            raise ValidationError(f"Unexpected MCP operation for {ident}")
        args = call.get("arguments")
        if not isinstance(args, dict) or set(args) != {"module_name", "function_name", "params"}:
            raise ValidationError(f"Bad MCP argument schema for {ident}")
        if args["module_name"] != module or args["function_name"] not in SAFE_METHODS[module] or (module == "gaia" and args["function_name"] != "query_object"):
            raise ValidationError(f"Unsafe/discrepant module.method in {ident}")
        if not isinstance(args["params"], dict) or not args["params"]:
            raise ValidationError(f"Missing query arguments for {ident}")
        if not isinstance(record.get("question"), str) or not record["question"].strip():
            raise ValidationError(f"Missing question for {ident}")
        params = args["params"]
        if module == "simbad":
            if (set(params) != {"object_name"} or
                    params["object_name"] not in {target.name for target in TARGETS}):
                raise ValidationError(f"Unapproved SIMBAD target/parameters in {ident}")
        else:
            coordinate_name = {"mast": "coordinates", "heasarc": "position",
                               "gaia": "coordinate", "vizier": "coordinates"}[module]
            allowed_keys = {coordinate_name, "radius"}
            if module in {"heasarc", "vizier"}:
                allowed_keys.add("catalog")
            if set(params) != allowed_keys:
                raise ValidationError(f"Unexpected query parameters in {ident}")
            coords = params[coordinate_name]
            radius = params["radius"]
            if not isinstance(coords, dict) or set(coords) != {"ra", "dec", "frame"} or coords["frame"] != "icrs":
                raise ValidationError(f"Unexpected coordinates in {ident}")
            ra, dec = coords["ra"], coords["dec"]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                       for v in (ra, dec)) or not (0 <= ra < 360 and -90 <= dec <= 90):
                raise ValidationError(f"Invalid coordinate bounds in {ident}")
            if not isinstance(radius, dict) or set(radius) != {"value", "unit"} or radius["unit"] != "arcmin":
                raise ValidationError(f"Unexpected radius in {ident}")
            radius_values = {1, 2, 3} if module in {"gaia", "vizier"} else set(RADII_ARCMIN)
            if (isinstance(radius["value"], bool) or not isinstance(radius["value"], int)
                    or radius["value"] not in radius_values):
                raise ValidationError(f"Unbounded radius in {ident}")
            if module == "heasarc" and params["catalog"] not in HEASARC_CATALOGS:
                raise ValidationError(f"Unsupported HEASARC catalog in {ident}")
            if module == "vizier" and params["catalog"] not in VIZIER_CATALOGS:
                raise ValidationError(f"Unsupported VizieR catalog in {ident}")
            constraints = record.get("constraints", {})
            if (not isinstance(constraints, dict) or
                    constraints.get("radius") != radius or
                    constraints.get("center_icrs") != {"ra_deg": ra, "dec_deg": dec} or
                    ("catalog" in params and constraints.get("catalog") != params["catalog"])):
                raise ValidationError(f"Mismatch between task constraints and call in {ident}")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or not isinstance(provenance.get("discovered_schema_sha256"), str):
            raise ValidationError(f"Missing generator schema fingerprint in {ident}")
        schema.add(provenance["discovered_schema_sha256"])
    if len(schema) != 1:
        raise ValidationError("Input contains mixed generator schema fingerprints")
    return next(iter(schema)), tuple(m for m in SAFE_METHODS if m in modules)


def _tables(result: Any) -> tuple[list[dict[str, Any]], str]:
    """Return Astropy table payloads, or a reason that format is unverified.

    Empty list is a valid empty TableList. Single generic dict is not presumed to
    be a science table and is sent for review rather than accepted automatically.
    """
    if isinstance(result, dict) and "data" in result:
        return [result], "table"
    if isinstance(result, list):
        if not result:
            return [], "empty_table_list"
        if all(isinstance(t, dict) and "data" in t for t in result):
            return result, "table_list"
        if all(isinstance(t, dict) for t in result):
            return [{"data": result, "row_count": len(result)}], "row_list"
    return [], "unknown_shape"


def _coord_evidence(tables: list[dict[str, Any]], constraints: dict[str, Any]) -> dict[str, Any]:
    center = constraints.get("center_icrs")
    radius = constraints.get("radius", {})
    if not isinstance(center, dict) or not isinstance(radius, dict):
        return {"status": "not_applicable"}
    if radius.get("unit") != "arcmin":
        return {"status": "not_checked", "reason": "non-arcmin request"}
    pairs = (("ra", "dec"), ("raj2000", "dej2000"),
             ("_raj2000", "_dej2000"), ("ra_icrs", "de_icrs"),
             ("ra_icrs", "dec_icrs"), ("raj2000", "decj2000"))
    count, outside, max_sep = 0, 0, 0.0
    for tab in tables:
        for row in tab["data"][:50]:
            if not isinstance(row, dict):
                continue
            mapped = {key.lower(): key for key in row}
            found = next(((mapped[x], mapped[y]) for x, y in pairs
                          if x in mapped and y in mapped), None)
            if found is None:
                continue
            try:
                ra, dec = float(row[found[0]]), float(row[found[1]])
                target_ra, target_dec = float(center["ra_deg"]), float(center["dec_deg"])
                if not all(map(math.isfinite, (ra, dec, target_ra, target_dec))) or not -90 <= dec <= 90:
                    continue
                r1, d1, r2, d2 = map(math.radians, (ra, dec, target_ra, target_dec))
                a = math.sin((d1-d2)/2)**2 + math.cos(d1)*math.cos(d2)*math.sin((r1-r2)/2)**2
                separation = math.degrees(2 * math.asin(min(1.0, math.sqrt(max(0.0, a))))) * 60
                count += 1
                outside += separation > float(radius["value"]) + 0.25
                max_sep = max(max_sep, separation)
            except (ValueError, KeyError, TypeError, OverflowError):
                continue
    if not count:
        return {"status": "not_checked", "reason": "no confidently parsed degree coordinate columns"}
    return {"status": "advisory_only", "checked_rows": count,
            "outside_requested_radius": outside, "max_separation_arcmin": round(max_sep, 6),
            "note": "Observation footprints can overlap a region even when center positions lie outside it."}


def evaluate_response(task: dict[str, Any], response: Any) -> dict[str, Any]:
    """Assess response structure without mistaking a successful RPC for science truth."""
    if not isinstance(response, dict) or response.get("success") is not True:
        return {"disposition": "rejected_malformed", "reason": "Expected success=true response object"}
    args = task["reference_call"]["arguments"]
    if response.get("module") != args["module_name"] or response.get("function") != args["function_name"]:
        return {"disposition": "rejected_malformed", "reason": "Response module/function mismatch"}
    result = response.get("result")
    tables, shape = _tables(result)
    if shape == "unknown_shape":
        return {"disposition": "review_required", "reason": "Unrecognized result serialization",
                "shape": type(result).__name__}
    total = 0
    total_rows = 0
    is_truncated = False
    for table in tables:
        data = table.get("data")
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            return {"disposition": "rejected_malformed", "reason": "Invalid table rows"}
        actual = len(data)
        declared = table.get("row_count", actual)
        if isinstance(declared, bool) or not isinstance(declared, int) or declared != actual:
            return {"disposition": "rejected_malformed", "reason": "Declared row_count does not match returned data"}
        untruncated_total = table.get("total_rows", actual)
        if isinstance(untruncated_total, bool) or not isinstance(untruncated_total, int) or untruncated_total < actual:
            return {"disposition": "rejected_malformed", "reason": "Invalid total_rows"}
        if "columns" in table and not isinstance(table["columns"], list):
            return {"disposition": "rejected_malformed", "reason": "Invalid table column metadata"}
        if "meta" in table and not isinstance(table["meta"], dict):
            return {"disposition": "rejected_malformed", "reason": "Invalid table metadata"}
        if table.get("truncated") is True and untruncated_total <= actual:
            return {"disposition": "rejected_malformed", "reason": "Inconsistent truncation flag"}
        total += actual
        total_rows += untruncated_total
        is_truncated |= bool(table.get("truncated", False))
    checks = {"table_shape": shape, "table_count": len(tables),
              "returned_rows": total, "reported_total_rows": total_rows,
              "truncated": is_truncated,
              "coordinate_evidence": _coord_evidence(tables, task.get("constraints", {})),
              "catalog_check": "not_independently_verified" if "catalog" in task.get("constraints", {}) else "not_applicable"}
    disposition = "accepted_nonempty" if total else "accepted_empty"
    return {"disposition": disposition, "reason": "Serialized table structure is internally consistent",
            "checks": checks, "scientific_validation_level": "structural_with_advisory_geometry"}


def classify_failure(exc: Exception) -> tuple[str, bool, dict[str, Any]]:
    if isinstance(exc, MCPToolError):
        payload = exc.payload if isinstance(exc.payload, dict) else {}
        code = str(exc.code).upper()
        recoverable = payload.get("recoverable") is True
        if code in {"VALIDATION_ERROR", "INVALID_PARAMS", "INVALID_ARGUMENT"}:
            disp = "rejected_arguments"
        elif code in {"AUTH_ERROR", "AUTHENTICATION_ERROR", "PERMISSION_DENIED"}:
            disp = "rejected_auth"
        else:
            disp = "archive_error"
        return disp, recoverable and disp == "archive_error", {
            "type": "MCPToolError", "code": code, "message": exc.message[:1000],
            "recoverable": recoverable, "protocol_error": exc.protocol_error,
            "service": payload.get("service")}
    if isinstance(exc, RETRYABLE_ERRORS):
        return "transport_error", True, {"type": type(exc).__name__, "message": str(exc)[:1000]}
    return "rejected_malformed", False, {"type": type(exc).__name__, "message": str(exc)[:1000]}


async def execute_task(task: dict[str, Any], *, url: str, timeout: float,
                       attempts: int, delay: float, max_rows: int,
                       max_response_bytes: int,
                       session_factory: Callable[[str], Any] | None = None,
                       sleep: Callable[[float], Any] = asyncio.sleep) -> dict[str, Any]:
    call = task["reference_call"]
    params = {**call["arguments"], "max_rows": max_rows}
    traces: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            await sleep(min(delay * (2 ** (attempt - 2)), 30.0))
        start = time.monotonic()
        event: dict[str, Any] = {"attempt": attempt, "started_utc": now_utc(),
                                "tool": call["tool"], "arguments": params}
        try:
            # Fresh HTTP session per attempt: a request timeout cannot poison
            # a subsequent query and reference calls cannot share session state.
            # Bound the complete attempt including HTTP session teardown. A
            # stalled upstream archive must not block the entire benchmark.
            async with asyncio.timeout(timeout):
                async with AstroqueryMCPClient(url, timeout=timeout,
                                               session_factory=session_factory) as client:
                    response = await client.call(call["tool"], params)
            blob = json_bytes(response)
            if len(blob) > max_response_bytes:
                evaluation = {"disposition": "rejected_oversize",
                              "reason": f"Response is {len(blob)} bytes, limit {max_response_bytes}"}
                response_saved = None
            else:
                evaluation = evaluate_response(task, response)
                response_saved = response
            event.update({"elapsed_seconds": round(time.monotonic() - start, 5),
                          "response_sha256": hashlib.sha256(blob).hexdigest(),
                          "response_bytes": len(blob), "outcome": evaluation["disposition"]})
            traces.append(event)
            return {"disposition": evaluation["disposition"], "evaluation": evaluation,
                    "response": response_saved, "attempts": traces}
        except (MCPConnectionError, MCPToolError, MCPTransportError, MCPResponseError,
                ValueError, TypeError, OverflowError, TimeoutError) as exc:
            disposition, retryable, error = classify_failure(exc)
            if isinstance(exc, TimeoutError):
                error["message"] = f"MCP attempt timed out after {timeout:g}s"
            event.update({"elapsed_seconds": round(time.monotonic() - start, 5),
                          "outcome": disposition, "error": error})
            traces.append(event)
            if not retryable or attempt == attempts:
                return {"disposition": disposition, "evaluation": {"disposition": disposition,
                        "reason": error["message"]}, "error": error, "attempts": traces}
    raise AssertionError("Unreachable")


def journal_records(journal: Path, *, dataset_hash: str) -> dict[str, dict[str, Any]]:
    # A crash after publishing the manifest but before the first completed
    # task leaves no journal yet. This is a valid zero-progress resumption.
    if not journal.exists() or journal.stat().st_size == 0:
        return {}
    records, _ = load_jsonl(journal, max_bytes=1024 * 1024 * 512)
    found: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("input_dataset_sha256") != dataset_hash:
            raise ValidationError("Journal dataset fingerprint mismatch")
        ident = record.get("task_id")
        if not isinstance(ident, str) or ident in found:
            raise ValidationError("Corrupt journal: missing or duplicate task ID")
        found[ident] = record
    return found


async def validate(dataset: Path, output: Path, report_path: Path, *,
                   url: str = DEFAULT_MCP_URL, timeout: float = 180,
                   attempts: int = 2, delay: float = 2.0, max_rows: int = 20,
                   max_response_bytes: int = 8 * 1024 * 1024,
                   limit: int | None = None, resume: bool = False,
                   replace: bool = False, strict_sha256: str | None = None, json_format: str = 'compact',
                   pretty_output: Path | None = None, csv_output: Path | None = None,
                   progress: Callable[[str], None] | None = None,
                   session_factory: Callable[[str], Any] | None = None,
                   sleep: Callable[[float], Any] = asyncio.sleep,
                   ) -> dict[str, Any]:
    if not 1 <= attempts <= 5 or not 0 <= delay <= 60 or not 1 <= max_rows <= 1000:
        raise ValidationError("Require --attempts 1..5, --delay 0..60, --max-rows 1..1000")
    if not 1024 <= max_response_bytes <= 128 * 1024 * 1024 or timeout <= 0:
        raise ValidationError("Invalid response size limit or timeout")
    if limit is not None and limit < 1:
        raise ValidationError("--limit must be positive")
    if resume and replace:
        raise ValidationError("--resume and --replace are mutually exclusive")
    if dataset.resolve() in {output.resolve(), report_path.resolve()} or output.resolve() == report_path.resolve():
        raise ValidationError("Input, output, and report must have distinct paths")
    from .exports import check_destinations, save_views
    journal = output.with_name(output.name + ".progress.jsonl")
    manifest = output.with_name(output.name + ".manifest.json")
    check_destinations(dataset, output, report_path, pretty_output, csv_output,
                       replace=(replace or resume), extras=(journal, manifest))
    def notify(message: str) -> None:
        if progress is not None:
            progress(message)

    @asynccontextmanager
    async def waiting(activity: str):
        if progress is None:
            yield
            return
        started = time.monotonic()
        async def heartbeat():
            while True:
                await asyncio.sleep(15)
                notify(f"WAITING {activity}: {time.monotonic()-started:.0f}s "
                       "elapsed (upstream MCP/archive I/O)")
        watcher = asyncio.create_task(heartbeat())
        try:
            yield
        finally:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher

    notify(f"loading candidates: {dataset}")
    records, dataset_hash = load_jsonl(dataset)
    schema_hash, modules = check_dataset(records)
    if strict_sha256 is not None and strict_sha256.lower() != dataset_hash:
        raise ValidationError(f"Input dataset SHA256 mismatch: actual {dataset_hash}")

    context = {"input_dataset_sha256": dataset_hash, "endpoint": url,
               "max_rows": max_rows, "max_response_bytes": max_response_bytes,
               "discovered_schema_sha256": schema_hash}
    if resume:
        if output.exists():
            raise ValidationError("Completed output already exists; do not resume it")
        if not manifest.exists():
            raise ValidationError("Resume manifest not found")
        if json.loads(manifest.read_text(encoding="utf-8")).get("context") != context:
            raise ValidationError("Resume context mismatch; use original endpoint/limits/dataset")
        completed = journal_records(journal, dataset_hash=dataset_hash)
    else:
        if any(path.exists() for path in (output, report_path, journal, manifest)) and not replace:
            raise ValidationError("Output/report/journal/manifest already exists; use --replace or --resume")
        completed = {}

    valid_ids = {task["id"] for task in records}
    if set(completed) - valid_ids:
        raise ValidationError("Journal has IDs absent from input dataset")
    remaining = [task for task in records if task["id"] not in completed]
    if limit is not None:
        remaining = remaining[:limit]
    if remaining:
        notify(f"preflight: checking MCP endpoint and signatures for {len(modules)} modules")
        # Verify read-only candidate functions remain advertised. A drifted
        # signature fails closed rather than running a stale/dangerous call.
        async with waiting("MCP signature preflight"):
            async with AstroqueryMCPClient(url, timeout=timeout, session_factory=session_factory) as client:
                tools = {tool["name"] for tool in await client.list_tools()}
                if "astroquery_execute" not in tools:
                    raise ValidationError("Server no longer advertises astroquery_execute")
                bindings = await discover_bindings(client, modules)
                observed_hash = generate_candidates(bindings, count=1, seed=42,
                                                    modules=modules)[0]["provenance"]["discovered_schema_sha256"]
                if observed_hash != schema_hash:
                    raise ValidationError("MCP signature drift: regenerate 0.2.0 candidates or restore prior server")
                for task in remaining:
                    bound = bindings[task["module"]]
                    if task["reference_call"]["arguments"]["function_name"] != bound.method:
                        raise ValidationError("Selected function changed: " + task["id"])
        notify("preflight passed; beginning sequential reference queries")
        # Only publish/replace a run after live preflight has succeeded.
        # Connectivity and signature-drift failures must not destroy an older
        # reference dataset or leave a misleading new progress manifest.
    if not resume:
        if replace:
            for path in (output, report_path, journal, manifest):
                path.unlink(missing_ok=True)
        atomic_json(manifest, {"milestone": "0.6.3 — QUERY_DIVERSITY_AND_DEDUPLICATION_CLOSURE",
                               "created_utc": now_utc(), "context": context})
    if remaining:
        for index, task in enumerate(remaining):
            notify(f"START {len(completed)+1}/{len(records)} {task['module']} {task['id']} "
                   f"(up to {attempts} attempt(s), {timeout:g}s timeout per MCP operation)")
            started_task = time.monotonic()
            if index and delay:
                await sleep(delay)
            async with waiting(f"{task['module']} {task['id']}"):
                outcome = await execute_task(task, url=url, timeout=timeout, attempts=attempts,
                                             delay=delay, max_rows=max_rows,
                                             max_response_bytes=max_response_bytes,
                                             session_factory=session_factory, sleep=sleep)
            entry = {"task_id": task["id"], "module": task["module"],
                     "input_dataset_sha256": dataset_hash, "reference_call": task["reference_call"],
                     "evaluated_at_utc": now_utc(), **outcome}
            append_journal(journal, entry)
            completed[task["id"]] = entry
            notify(f"DONE {len(completed)}/{len(records)} {task['module']} {task['id']} "
                   f"{entry['disposition']} after {time.monotonic()-started_task:.1f}s")

    ordered = [completed[task["id"]] for task in records if task["id"] in completed]
    tally = Counter(item["disposition"] for item in ordered)
    by_module = {module: dict(Counter(item["disposition"] for item in ordered
                                     if item["module"] == module)) for module in modules}
    all_done = len(ordered) == len(records)
    result: dict[str, Any] = {
        "milestone": "0.6.3 — QUERY_DIVERSITY_AND_DEDUPLICATION_CLOSURE", "benchmark_version": __version__,
        "timestamp_utc": now_utc(), "endpoint": url,
        "input": str(dataset), "input_dataset_sha256": dataset_hash,
        "discovered_schema_sha256": schema_hash,
        "total_candidates": len(records), "processed": len(ordered),
        "remaining": len(records) - len(ordered), "dispositions": dict(sorted(tally.items())),
        "by_module": by_module,
        "accepted_reference_count": sum(tally.get(kind, 0) for kind in SUCCESS_DISPOSITIONS),
        "quality_gate": ("PENDING" if not all_done else
                         "REVIEW" if any(item["disposition"] not in SUCCESS_DISPOSITIONS for item in ordered) else "PASS"),
        "status": "COMPLETE" if all_done else "PARTIAL",
        "journal": str(journal), "manifest": str(manifest),
        "notes": ["Accepted means valid serialized table evidence, not independently verified astrophysical truth.",
                  "Only MAST query_region currently honors max_rows at the MCP server level.",
                  "Every attempted task is journaled, including errors and empty results."],
    }
    # Advisory data-redundancy audit: do not treat identical returned subsets
    # as independently verified identical astrophysical selections.
    from .diversity import analyze_reference_redundancy, analyze_answerability
    result["returned_data_redundancy"] = analyze_reference_redundancy(ordered, records)
    result["answerability_advisory"] = {
        key: value for key, value in analyze_answerability(records, ordered).items()
        if key != "checks"
    }
    result["diversity_gate"] = (
        "REVIEW" if result["returned_data_redundancy"]["redundant_returned_table_records"]
        else "PASS"
    )
    result["notes"].append("Diversity REVIEW flags identical returned data subsets, not necessarily identical complete archive searches.")
    # Secondary human-readable views also work for --limit pilot runs. They are
    # rewritten on --resume, while the canonical JSONL is published on completion.
    if pretty_output is not None or csv_output is not None:
        save_views(ordered, pretty=pretty_output, csv_path=csv_output,
                   kind="reference", tasks={r["id"]: r for r in records},
                   replace=(replace or resume))
        if pretty_output is not None:
            result["pretty_output"] = str(pretty_output)
        if csv_output is not None:
            result["csv_output"] = str(csv_output)
    if all_done:
        result["reference_answers_sha256"] = atomic_jsonl(output, ordered)
        result["output"] = str(output)
    atomic_json(report_path, result, style=json_format)
    notify(f"{result['status']}: {len(ordered)}/{len(records)} tasks, "
           f"accepted={result['accepted_reference_count']}; report={report_path}")
    return result
