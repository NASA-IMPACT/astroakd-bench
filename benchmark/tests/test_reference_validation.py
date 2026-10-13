"""0.3.0 qualification: mock HTTP/MCP execution and real accepted input safety."""
import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import contextlib
import io

from benchmark.tests.test_generator import FixtureSession, run_fixture
from benchmark.validator import (
    EXPECTED_ACCEPTED_020_SHA256, ValidationError, atomic_jsonl,
    check_dataset, classify_failure, evaluate_response, execute_task,
    journal_records, load_jsonl, validate,
)
from benchmark.errors import MCPToolError, MCPTransportError


REAL_ACCEPTED = (Path(__file__).resolve().parent / "fixtures" /
                 "accepted_0_2_0_seed42.jsonl")


def tab(rows=None, *, total=None, truncate=False):
    rows = rows if rows is not None else [{"ra": 10.68, "dec": 41.27, "name": "M31"}]
    obj = {"columns": [{"name": "ra", "dtype": "float64"}],
           "data": rows, "row_count": len(rows), "meta": {}}
    if total is not None:
        obj.update(total_rows=total, truncated=truncate)
    return obj


def reply(task, result=None):
    args = task["reference_call"]["arguments"]
    return {"success": True, "module": args["module_name"],
            "function": args["function_name"],
            "result": tab() if result is None else result}


class ValidatingSession(FixtureSession):
    def __init__(self, url, *, outcomes=None, counts=None):
        super().__init__(url)
        self.outcomes = outcomes or {}
        self.counts = counts if counts is not None else Counter()

    async def call_tool(self, name, args, *, timeout=None):
        if name != "astroquery_execute":
            return await super().call_tool(name, args, timeout=timeout)
        self.counts[args["module_name"]] += 1
        outcome = self.outcomes.get(args["module_name"], "ok")
        if outcome == "timeout" and self.counts[args["module_name"]] == 1:
            raise RuntimeError("HTTP connection reset")
        if outcome in {"service", "invalid"}:
            return SimpleNamespace(data={"error": True,
                "code": "SERVICE_ERROR" if outcome == "service" else "VALIDATION_ERROR",
                "recoverable": outcome == "service", "message": "upstream unavailable"},
                structured_content=None, content=[], is_error=False)
        payload = {"success": True, "module": args["module_name"],
                   "function": args["function_name"], "result": tab()}
        if outcome == "empty":
            payload["result"] = tab([])
        if outcome == "malformed":
            payload["result"] = {"data": [{}], "row_count": 2}
        return SimpleNamespace(data=payload, structured_content=None,
                               content=[], is_error=False)


def fake_factory(*, outcomes=None, counts=None):
    return lambda url: ValidatingSession(url, outcomes=outcomes, counts=counts)


async def no_wait(seconds):
    return None


def make_test_dataset(root, count=5):
    cases, _ = run_fixture(count=count)[0]
    path = root / "synthetic_queries.jsonl"
    atomic_jsonl(path, cases)
    return path, cases


class AcceptedDatasetTests(unittest.TestCase):
    def test_user_supplied_accepted_50_task_dataset(self):
        records, observed_hash = load_jsonl(REAL_ACCEPTED)
        self.assertEqual(observed_hash, EXPECTED_ACCEPTED_020_SHA256)
        self.assertEqual(len(records), 50)
        schema, modules = check_dataset(records)
        self.assertEqual(len(schema), 64)
        self.assertEqual(set(modules), {"simbad", "mast", "heasarc", "gaia", "vizier"})

    def test_reject_mutated_reference_calls(self):
        with TemporaryDirectory() as directory:
            _, records = make_test_dataset(Path(directory))
            for altered in ("delete", "arbitrary_service", "large_radius", "bad_catalog", "bad_units"):
                bad = copy.deepcopy(records)
                args = bad[0]["reference_call"]["arguments"]
                if altered == "delete":
                    bad[0]["reference_call"]["tool"] = "delete_user_tables"
                elif altered == "arbitrary_service":
                    args["module_name"] = "ads"
                else:
                    task = bad[1]
                    params = task["reference_call"]["arguments"]["params"]
                    if altered == "large_radius":
                        params["radius"]["value"] = 180
                    elif altered == "bad_catalog":
                        task = bad[2]
                        task["reference_call"]["arguments"]["params"]["catalog"] = "secrets"
                    elif altered == "bad_units":
                        params["radius"]["unit"] = "deg"
                with self.subTest(altered=altered), self.assertRaises(ValidationError):
                    check_dataset(bad)

    def test_duplicate_ids_or_mixed_schema(self):
        with TemporaryDirectory() as directory:
            _, records = make_test_dataset(Path(directory))
            records[1]["id"] = records[0]["id"]
            with self.assertRaisesRegex(ValidationError, "duplicate"):
                check_dataset(records)


class ReferenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.task = run_fixture(count=3)[0][0][2]  # HEASARC region search

    def test_accepted_nonempty_and_geometry_advisory(self):
        result = evaluate_response(self.task, reply(self.task, tab([{"ra": 10.6847, "dec": 41.2688}])))
        self.assertEqual(result["disposition"], "accepted_nonempty")
        self.assertEqual(result["checks"]["returned_rows"], 1)
        self.assertEqual(result["checks"]["catalog_check"], "not_independently_verified")
        self.assertEqual(result["checks"]["coordinate_evidence"]["status"], "advisory_only")

    def test_empty_structured_table(self):
        result = evaluate_response(self.task, reply(self.task, tab([])))
        self.assertEqual(result["disposition"], "accepted_empty")

    def test_empty_table_list(self):
        self.assertEqual(evaluate_response(self.task, reply(self.task, []))["disposition"], "accepted_empty")

    def test_table_list_aggregate(self):
        res = evaluate_response(self.task, reply(self.task, [tab(), tab()]))
        self.assertEqual(res["checks"]["returned_rows"], 2)
        self.assertEqual(res["checks"]["table_count"], 2)

    def test_truncation_metadata_is_preserved(self):
        res = evaluate_response(self.task, reply(self.task, tab([{"ra": 1}], total=100, truncate=True)))
        self.assertEqual(res["disposition"], "accepted_nonempty")
        self.assertEqual(res["checks"]["reported_total_rows"], 100)
        self.assertTrue(res["checks"]["truncated"])

    def test_declared_bad_rows_malformed(self):
        result = tab()
        result["row_count"] = 42
        self.assertEqual(evaluate_response(self.task, reply(self.task, result))["disposition"], "rejected_malformed")

    def test_inconsistent_truncation_malformed(self):
        result = tab(total=1, truncate=True)
        self.assertEqual(evaluate_response(self.task, reply(self.task, result))["disposition"], "rejected_malformed")

    def test_missing_or_mismatched_envelope(self):
        self.assertEqual(evaluate_response(self.task, {"success": False})["disposition"], "rejected_malformed")
        result = reply(self.task)
        result["module"] = "other"
        self.assertEqual(evaluate_response(self.task, result)["disposition"], "rejected_malformed")

    def test_unfamiliar_response_requires_review(self):
        self.assertEqual(evaluate_response(self.task, reply(self.task, {"unexpected": "payload"}))["disposition"], "review_required")

    def test_error_recoverability(self):
        exc = MCPToolError("astroquery_execute", "bad", code="VALIDATION_ERROR", payload={"recoverable": True})
        disposition, retry, _ = classify_failure(exc)
        self.assertEqual(disposition, "rejected_arguments")
        self.assertFalse(retry)
        exc = MCPToolError("astroquery_execute", "oops", code="SERVICE_ERROR", payload={"recoverable": True})
        self.assertTrue(classify_failure(exc)[1])
        self.assertTrue(classify_failure(MCPTransportError("dropped"))[1])

    def test_retry_transport_then_accept(self):
        counts = Counter()
        output = asyncio.run(execute_task(self.task, url="http://127.0.0.1:8000/mcp",
            timeout=10, attempts=2, delay=0, max_rows=20, max_response_bytes=100000,
            session_factory=fake_factory(outcomes={"heasarc": "timeout"}, counts=counts), sleep=no_wait))
        self.assertEqual(output["disposition"], "accepted_nonempty")
        self.assertEqual(len(output["attempts"]), 2)
        self.assertEqual(counts["heasarc"], 2)
        self.assertIn("response_sha256", output["attempts"][1])

    def test_invalid_tool_error_no_retry(self):
        counts = Counter()
        output = asyncio.run(execute_task(self.task, url="http://127.0.0.1:8000/mcp",
            timeout=10, attempts=3, delay=0, max_rows=20, max_response_bytes=100000,
            session_factory=fake_factory(outcomes={"heasarc": "invalid"}, counts=counts), sleep=no_wait))
        self.assertEqual(output["disposition"], "rejected_arguments")
        self.assertEqual(counts["heasarc"], 1)

    def test_recoverable_service_error_is_recorded(self):
        counts = Counter()
        output = asyncio.run(execute_task(self.task, url="http://127.0.0.1:8000/mcp",
            timeout=10, attempts=2, delay=0, max_rows=20, max_response_bytes=100000,
            session_factory=fake_factory(outcomes={"heasarc": "service"}, counts=counts), sleep=no_wait))
        self.assertEqual(output["disposition"], "archive_error")
        self.assertEqual(counts["heasarc"], 2)

    def test_oversize_never_saves_truncated_raw_response(self):
        output = asyncio.run(execute_task(self.task, url="http://127.0.0.1:8000/mcp",
            timeout=10, attempts=1, delay=0, max_rows=20, max_response_bytes=100,
            session_factory=fake_factory(), sleep=no_wait))
        self.assertEqual(output["disposition"], "rejected_oversize")
        self.assertIsNone(output["response"])


class ReferenceCLITests(unittest.TestCase):
    def test_validate_options_and_version(self):
        from benchmark.cli import build_parser
        args = build_parser().parse_args(["validate", "--strict-accepted-020",
            "--limit", "5", "--attempts", "3", "--resume", "--max-rows", "15"])
        self.assertEqual(args.input, Path("benchmark/datasets/generated/synthetic_queries.jsonl"))
        self.assertEqual(args.attempts, 3)
        self.assertTrue(args.resume)
        self.assertTrue(args.strict_accepted_020)

    def test_cli_success_exit_code_for_partial(self):
        from benchmark.cli import main
        async def fake_validate(*args, **kwargs):
            return {"status": "PARTIAL", "processed": 3}
        with patch("benchmark.cli.validate", fake_validate):
            with contextlib.redirect_stdout(io.StringIO()) as capture:
                code = main(["validate", "--limit", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(capture.getvalue())["processed"], 3)


class EndToEndMockMCPTests(unittest.TestCase):
    def test_empty_journal_is_safe_to_resume(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            output, report = root / "ref.jsonl", root / "report.json"
            # The previous run published its manifest, then crashed before
            # writing the first successful response.
            from benchmark.validator import atomic_json
            _, source_hash = load_jsonl(dataset)
            schema_hash, _ = check_dataset(load_jsonl(dataset)[0])
            atomic_json(output.with_name(output.name + ".manifest.json"), {
                "context": {"input_dataset_sha256": source_hash,
                            "endpoint": "http://127.0.0.1:8000/mcp",
                            "max_rows": 20, "max_response_bytes": 8 * 1024 * 1024,
                            "discovered_schema_sha256": schema_hash}})
            summary = asyncio.run(validate(dataset, output, report,
                limit=1, resume=True, attempts=1, delay=0,
                session_factory=fake_factory(), sleep=no_wait))
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["status"], "PARTIAL")

    def test_all_50_accepted_input_completed_in_input_order(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output, report_path = root / "reference.jsonl", root / "report.json"
            dataset_schema, _ = check_dataset(load_jsonl(REAL_ACCEPTED)[0])
            from benchmark.validator import validate as run_validation
            original, _ = load_jsonl(REAL_ACCEPTED)
            by_module = {task["module"]: task["reference_call"]["arguments"]["function_name"]
                         for task in original}
            async def matching_bindings(client, modules):
                return {mod: SimpleNamespace(method=by_module[mod]) for mod in modules}
            def matching_schema(bindings, **kwargs):
                return [{"provenance": {"discovered_schema_sha256": dataset_schema}}]
            with patch("benchmark.validator.discover_bindings", matching_bindings), \
                 patch("benchmark.validator.generate_candidates", matching_schema):
                result = asyncio.run(run_validation(REAL_ACCEPTED, output, report_path,
                    attempts=1, delay=0, session_factory=fake_factory(), sleep=no_wait,
                    strict_sha256=EXPECTED_ACCEPTED_020_SHA256))
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["accepted_reference_count"], 50)
            self.assertEqual(result["dispositions"], {"accepted_nonempty": 50})
            rows, _ = load_jsonl(output)
            self.assertEqual([item["task_id"] for item in rows],
                             [item["id"] for item in original])
            self.assertEqual(len({item["task_id"] for item in rows}), 50)

    def test_signature_drift_preserves_existing_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            output, report = root / "ref.jsonl", root / "report.json"
            output.write_text("PREVIOUS RESULT", encoding="utf-8")
            report.write_text("PREVIOUS REPORT", encoding="utf-8")
            async def changed_schema(client, modules):
                return {mod: SimpleNamespace(method="different_method") for mod in modules}
            with patch("benchmark.validator.discover_bindings", changed_schema), \
                 patch("benchmark.validator.generate_candidates", lambda *a, **k: [
                     {"provenance": {"discovered_schema_sha256": "0" * 64}}]):
                with self.assertRaises(ValidationError):
                    asyncio.run(validate(dataset, output, report, attempts=1, delay=0,
                        replace=True, session_factory=fake_factory(), sleep=no_wait))
            self.assertEqual(output.read_text(), "PREVIOUS RESULT")
            self.assertEqual(report.read_text(), "PREVIOUS REPORT")

    def test_resumable_five_tasks_and_no_reexecution(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            output, report = root / "references.jsonl", root / "report.json"
            counts = Counter()
            params = dict(url="http://127.0.0.1:8000/mcp", timeout=10,
                          attempts=1, delay=0, session_factory=fake_factory(counts=counts), sleep=no_wait)
            first = asyncio.run(validate(dataset, output, report, limit=2, **params))
            self.assertEqual(first["status"], "PARTIAL")
            self.assertEqual(first["processed"], 2)
            self.assertFalse(output.exists())
            self.assertEqual(len(journal_records(output.with_name(output.name + ".progress.jsonl"),
                                                 dataset_hash=first["input_dataset_sha256"])), 2)
            final = asyncio.run(validate(dataset, output, report, resume=True, **params))
            self.assertEqual(final["status"], "COMPLETE")
            self.assertEqual(final["processed"], 5)
            self.assertEqual(final["accepted_reference_count"], 5)
            self.assertEqual(sum(counts.values()), 5)
            results, _ = load_jsonl(output)
            self.assertEqual([x["task_id"] for x in results],
                             [f"ASTROAKD-020-{i:05d}" for i in range(1, 6)])
            self.assertEqual(final["reference_answers_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_reject_resume_context_changed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            output, report = root / "ref.jsonl", root / "report.json"
            params = dict(url="http://127.0.0.1:8000/mcp", attempts=1, delay=0,
                          session_factory=fake_factory(), sleep=no_wait)
            asyncio.run(validate(dataset, output, report, limit=1, **params))
            with self.assertRaisesRegex(ValidationError, "context mismatch"):
                asyncio.run(validate(dataset, output, report, resume=True, max_rows=21, **params))

    def test_report_keeps_rejected_and_empty(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            report = asyncio.run(validate(dataset, root / "ref.jsonl", root / "report.json",
                attempts=1, delay=0, session_factory=fake_factory(outcomes={"mast": "empty", "heasarc": "invalid"}),
                sleep=no_wait))
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(report["dispositions"]["accepted_empty"], 1)
            self.assertEqual(report["dispositions"]["rejected_arguments"], 1)
            self.assertEqual(report["quality_gate"], "REVIEW")
            self.assertEqual(sum(report["dispositions"].values()), 5)

    def test_reject_overwrite_and_wrong_hash_without_mcp(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, _ = make_test_dataset(root, 5)
            output, report = root / "ref.jsonl", root / "report.json"
            with self.assertRaisesRegex(ValidationError, "SHA256 mismatch"):
                asyncio.run(validate(dataset, output, report,
                                     strict_sha256=EXPECTED_ACCEPTED_020_SHA256))
            self.assertFalse(output.exists())
            asyncio.run(validate(dataset, output, report, attempts=1, delay=0,
                                 limit=1, session_factory=fake_factory(), sleep=no_wait))
            with self.assertRaisesRegex(ValidationError, "already exists"):
                asyncio.run(validate(dataset, output, report, attempts=1, delay=0,
                                     session_factory=fake_factory(), sleep=no_wait))


if __name__ == "__main__":
    unittest.main()
