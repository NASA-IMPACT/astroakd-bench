"""Offline diversity and returned-table redundancy audit (0.6.3).

Hashes are advisory on *returned subsets*. No empty result is called a
redundant scientific observation, and result equivalence does not imply
that two astrophysical selections were semantically identical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _groups(groups: dict[Any, list[str]], *, key_name: str) -> list[dict[str, Any]]:
    return [{key_name: k, "task_ids": ids, "redundant_records": len(ids)-1}
            for k, ids in sorted(groups.items(), key=lambda pair: str(pair[0])) if len(ids) > 1]


def analyze_candidates(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    questions: dict[str, list[str]] = defaultdict(list)
    calls: dict[str, list[str]] = defaultdict(list)
    pairs: dict[str, list[str]] = defaultdict(list)
    global_targets: dict[str, list[str]] = defaultdict(list)
    intents = Counter()
    for task in tasks:
        ident = task.get("id", "")
        module = task.get("module", "")
        target = _norm(task.get("target"))
        questions[_norm(task.get("question"))].append(ident)
        calls[_digest(task.get("reference_call", {}))].append(ident)
        pairs[f"{module}|{target}"].append(ident)
        global_targets[target].append(ident)
        intents[str(task.get("intent", task.get("category", "unspecified")))]+=1
    q = _groups(questions, key_name="normalized_question")
    c = _groups(calls, key_name="call_sha256")
    p = _groups(pairs, key_name="archive_target")
    gt = _groups(global_targets, key_name="target")
    return {
        "total_queries": len(tasks),
        "distinct_targets": len(global_targets),
        "distinct_archive_target_pairs": len(pairs),
        "by_intent": dict(sorted(intents.items())),
        "duplicate_questions": q,
        "duplicate_mcp_calls": c,
        "reused_archive_targets": p,
        "reused_global_targets": gt,
        "counts": {"duplicate_question_records": sum(g["redundant_records"] for g in q),
                   "duplicate_call_records": sum(g["redundant_records"] for g in c),
                   "reused_archive_target_records": sum(g["redundant_records"] for g in p)},
    }


def _returned_table_signature(response: Any) -> tuple[str, int, bool] | None:
    if not isinstance(response, dict) or response.get("success") is not True:
        return None
    result = response.get("result")
    tables = result if isinstance(result, list) else [result]
    if not tables or not all(isinstance(table, dict) and isinstance(table.get("data"), list)
                             for table in tables):
        return None
    returned_rows = sum(len(table["data"]) for table in tables)
    if not returned_rows:
        return None  # empty tables are common, NOT evidence of duplicated data
    signature = [{"columns": [col.get("name") for col in table.get("columns", [])
                              if isinstance(col, dict)], "data": table["data"]}
                 for table in tables]
    truncated = any(table.get("truncated") is True or
                    isinstance(table.get("total_rows"), int) and
                    table["total_rows"] > len(table["data"]) for table in tables)
    return _digest(signature), returned_rows, truncated


def analyze_reference_redundancy(references: list[dict[str, Any]],
                                 tasks: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {t.get("id"): t for t in tasks}
    fingerprints: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    analyzed = 0
    for ref in references:
        sig = _returned_table_signature(ref.get("response"))
        if sig is None:
            continue
        ident = ref.get("task_id")
        task = by_id.get(ident, {})
        module = str(ref.get("module") or task.get("module") or "")
        row_hash, rows, truncated = sig
        analyzed += 1
        fingerprints[(module, row_hash)].append({"task_id": ident,
            "target": task.get("target"), "returned_rows": rows,
            "truncated_or_limited": truncated})
    groups = [{"module": module, "returned_table_sha256": digest,
               "tasks": members, "redundant_records": len(members)-1,
               "any_truncated_or_limited": any(m["truncated_or_limited"] for m in members),
               "interpretation": "identical_returned_subset_not_proven_identical_complete_archive_result"}
              for (module, digest), members in sorted(fingerprints.items()) if len(members) > 1]
    return {"analyzed_nonempty_responses": analyzed,
            "distinct_nonempty_returned_tables": len(fingerprints),
            "redundant_returned_table_records": sum(g["redundant_records"] for g in groups),
            "groups": groups,
            "note": "Compare serialized table column names and returned row data only; exclude query metadata. "
                    "Empty results are excluded. Equal truncated subsets do not prove equal full archive responses."}


def analyze_answerability(tasks: list[dict[str, Any]],
                          references: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {r.get("task_id"): r for r in references}
    rows = []
    for task in tasks:
        spec = task.get("answer_spec")
        if not isinstance(spec, dict) or not spec.get("expected_columns"):
            continue  # legacy discovery-style questions: no answer field contract
        reference = lookup.get(task.get("id"))
        if reference is None:
            continue
        response = reference.get("response") or {}
        result = response.get("result") if isinstance(response, dict) else None
        tables = result if isinstance(result, list) else [result]
        columns = {c.get("name") for table in tables if isinstance(table, dict)
                   for c in table.get("columns", []) if isinstance(c, dict)}
        expected = set(spec["expected_columns"])
        available = sorted(expected & columns)
        missing = sorted(expected - columns)
        rows.append({"task_id": task.get("id"), "intent": task.get("intent"),
                     "reference_disposition": reference.get("disposition"),
                     "expected_columns": sorted(expected), "present_columns": available,
                     "missing_columns": missing,
                     "schema_fields_available": not missing,
                     "note": "Column availability is not verification of expected answer values"})
    return {"assessed": len(rows), "schema_compatible": sum(r["schema_fields_available"] for r in rows),
            "schema_incompatible": sum(not r["schema_fields_available"] for r in rows),
            "checks": rows}


def audit(tasks: list[dict[str, Any]], references: list[dict[str, Any]] | None = None,
          *, candidate_sha256: str | None = None) -> dict[str, Any]:
    candidate = analyze_candidates(tasks)
    output = {"milestone": "0.6.3 — QUERY_DIVERSITY_AND_DEDUPLICATION_CLOSURE",
              "task_count": len(tasks), "candidate_diversity": candidate,
              "scientific_truth_verified": False}
    if references is not None:
        by_id = {task.get("id"): task for task in tasks}
        for reference in references:
            ident = reference.get("task_id")
            task = by_id.get(ident)
            if task is None:
                raise ValueError(f"Reference task ID absent from candidates: {ident}")
            if reference.get("reference_call") != task.get("reference_call"):
                raise ValueError(f"Reference call does not match candidate task: {ident}")
        hashes = sorted({reference.get("input_dataset_sha256") for reference in references
                         if isinstance(reference.get("input_dataset_sha256"), str)})
        provenance_matches = candidate_sha256 is None or not hashes or hashes == [candidate_sha256]
        output["reference_provenance"] = {
            "candidate_dataset_sha256": candidate_sha256,
            "reference_input_dataset_sha256_values": hashes,
            "byte_exact_input_hash_match": provenance_matches if candidate_sha256 is not None else None,
            "note": "Task calls are checked for exact equality; a different dataset SHA256 "
                    "cannot qualify as a byte-exact validation run."}
        output["reference_redundancy"] = analyze_reference_redundancy(references, tasks)
        output["answerability_advisory"] = analyze_answerability(tasks, references)
    defects = candidate["counts"]
    output["status"] = ("REVIEW" if any(defects.values()) or
                        references is not None and output["reference_redundancy"]["groups"]
                        else "PASS")
    return output
