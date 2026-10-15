"""Offline science-review worksheets: observed archive rows are NOT verified gold.

This module only reads frozen candidates and existing MCP evidence. It never
connects to archives, calls a language model, or invents a reference value.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .exports import atomic_csv, json_compact, observed_reference_values
from .gold import _path_safety, _read_tasks
from .validator import ValidationError, atomic_json, atomic_jsonl, load_jsonl, _tables

MILESTONE = '0.6.7.10 - ARCHIVE_REFERENCE_POLICY_AND_SCIENCE_REVIEW'
REVIEW_COLUMNS = (
    'task_id', 'archive', 'target', 'question', 'intent', 'requested_fields',
    'answer_shape', 'observed_answer_preview', 'reference_answer_values_json',
    'reference_answer_status', 'reference_disposition', 'returned_rows',
    'reported_total_rows', 'truncated', 'value_count', 'nonnull_value_count',
    'null_value_count', 'matched_fields', 'review_flags', 'gold_status',
    'question_review', 'reviewer', 'review_notes', 'reference_response_sha256',
)

_COORD_PAIRS = (
    frozenset(('ra', 'dec')),
    frozenset(('ra_icrs', 'de_icrs')),
    frozenset(('ra_icrs', 'dec_icrs')),
    frozenset(('raj2000', 'dej2000')),
    frozenset(('_raj2000', '_dej2000')),
)


def review_detail(task: dict[str, Any], reference: dict[str, Any] | None) -> dict[str, Any]:
    """Classify cardinality and record structure conservatively; never pick rows."""
    expected = task.get('answer_spec', {}).get('expected_columns', []) or []
    names = [str(x).strip().casefold() for x in expected if isinstance(x, str) and x.strip()]
    record = reference or {}
    evidence = record.get('evaluation', {}).get('checks', {})
    observed = observed_reference_values(record, task)
    full_count = 0
    null_count = 0
    nonnull_count = 0
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    actual_names: set[str] = set()
    tables, _ = _tables((record.get('response') or {}).get('result'))
    for ti, table in enumerate(tables):
        for ri, row in enumerate(table.get('data', [])):
            if not isinstance(row, dict):
                continue
            for field, value in row.items():
                if isinstance(field, str) and field.casefold().strip() in names:
                    actual_names.add(field.casefold().strip())
                    full_count += 1
                    if value is None or value == '':
                        null_count += 1
                    else:
                        nonnull_count += 1
                        grouped.setdefault((ti, ri), {})[field] = value
    rows_with_values = len(grouped)
    coordinate = len(names) == 2 and frozenset(names) in _COORD_PAIRS
    if not nonnull_count:
        shape = 'no_answer'
    elif coordinate:
        shape = 'coordinate_pair' if rows_with_values == 1 and nonnull_count == 2 else 'coordinate_pair_list'
    elif len(names) > 1:
        shape = 'vector' if rows_with_values == 1 and nonnull_count == len(names) else 'vector_list'
    elif rows_with_values == 1 and nonnull_count == 1:
        shape = 'single_value'
    else:
        shape = 'record_list'
    flags = []
    if record.get('disposition') != 'accepted_nonempty':
        flags.append('missing_or_empty_reference')
    if any(name not in actual_names for name in names):
        flags.append('missing_expected_field')
    if null_count:
        flags.append('null_measurements')
    if rows_with_values > 1:
        flags.append('multiple_matching_rows')
    if shape in {'coordinate_pair_list', 'vector_list'}:
        flags.append('structured_multi_field_response')
    if evidence.get('truncated') is True or (
        isinstance(evidence.get('reported_total_rows'), int) and
        evidence.get('reported_total_rows') > evidence.get('returned_rows', 0)
    ):
        flags.append('incomplete_truncated_response')
    if observed['count'] > len(observed['values']):
        flags.append('observed_values_preview_capped_at_100')
    if len(tables) > 1:
        flags.append('multiple_tables')
    samples = [
        ', '.join(f'{k}={v!s}' for k, v in row.items())
        for row in list(grouped.values())[:3]
    ]
    return {
        'answer_shape': shape, 'review_flags': flags,
        'reference_answer_status': observed['status'],
        'reference_answer_values': observed['values'],
        'value_count': full_count, 'nonnull_value_count': nonnull_count,
        'null_value_count': null_count, 'rows_with_values': rows_with_values,
        'observed_answer_preview': ' | '.join(samples)[:500],
        'matched_fields': observed['fields'],
        'checks': evidence,
    }


def _make_review(task: dict[str, Any], record: dict[str, Any] | None,
                 task_sha: str, reference_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    detail = review_detail(task, record)
    checks = detail['checks']
    response = (record or {}).get('response')
    response_sha = (hashlib.sha256(json_compact(response).encode()).hexdigest()
                    if response is not None else None)
    reference_evidence = {
        'disposition': (record or {}).get('disposition', 'not_collected'),
        'returned_rows': checks.get('returned_rows'),
        'reported_total_rows': checks.get('reported_total_rows'),
        'truncated': checks.get('truncated'),
        'reference_response_sha256': response_sha,
        'reference_file_sha256': reference_sha,
        'reference_answer_status': detail['reference_answer_status'],
        'observed_answer_values': detail['reference_answer_values'],
        'matched_fields': detail['matched_fields'],
        'observed_answer_preview': detail['observed_answer_preview'],
        'value_count': detail['value_count'],
        'nonnull_value_count': detail['nonnull_value_count'],
        'null_value_count': detail['null_value_count'],
        'review_flags': detail['review_flags'],
    }
    draft = {
        'task_id': task['id'], 'task_type': task.get('task_type', 'archive_driven'),
        'question': task['question'], 'module': task['module'],
        'target': task.get('target'), 'answer_spec': task.get('answer_spec', {}),
        'answer_shape': detail['answer_shape'], 'input_dataset_sha256': task_sha,
        'reference_evidence': reference_evidence,
        'question_review': 'pending', 'gold_status': 'pending', 'gold': None,
        'sources': [], 'reviewer': None, 'review_notes': '',
    }
    csv_row = {
        'task_id': task['id'], 'archive': task['module'],
        'target': task.get('target', ''), 'question': task['question'],
        'intent': task.get('intent', ''),
        'requested_fields': ';'.join(task.get('answer_spec', {}).get('expected_columns', [])),
        'answer_shape': detail['answer_shape'],
        'observed_answer_preview': detail['observed_answer_preview'],
        'reference_answer_values_json': json_compact(detail['reference_answer_values']),
        'reference_answer_status': detail['reference_answer_status'],
        'reference_disposition': reference_evidence['disposition'],
        'returned_rows': checks.get('returned_rows', ''),
        'reported_total_rows': checks.get('reported_total_rows', ''),
        'truncated': checks.get('truncated', ''),
        'value_count': detail['value_count'], 'nonnull_value_count': detail['nonnull_value_count'],
        'null_value_count': detail['null_value_count'],
        'matched_fields': ';'.join(detail['matched_fields']),
        'review_flags': ';'.join(detail['review_flags']),
        'gold_status': 'pending', 'question_review': 'pending',
        'reviewer': '', 'review_notes': '',
        'reference_response_sha256': response_sha or '',
    }
    return draft, csv_row


def load_review_evidence(tasks_path: Path, references_path: Path):
    tasks, dataset_sha = _read_tasks(tasks_path)
    refs, refs_sha = load_jsonl(references_path, max_bytes=512 * 1024 * 1024)
    valid = {t['id'] for t in tasks}
    seen: dict[str, dict[str, Any]] = {}
    for reference in refs:
        tid = reference.get('task_id')
        if tid not in valid or tid in seen or reference.get('input_dataset_sha256') != dataset_sha:
            raise ValidationError(f'Reference ID/duplicate/dataset mismatch: {tid}')
        seen[tid] = reference
    return tasks, dataset_sha, seen, refs_sha


def write_consolidated_csv(tasks: list[dict[str, Any]], references: list[dict[str, Any]],
                           path: Path, *, replace: bool = False) -> None:
    """For validate pilot/resume; no network, no answer approval, one row per task."""
    records = {r['task_id']: r for r in references}
    rows = [_make_review(t, records.get(t['id']), '', '')[1] for t in tasks if t['id'] in records]
    atomic_csv(path, rows, REVIEW_COLUMNS, replace=replace)


def reference_review_draft(tasks_path: Path, references_path: Path, output: Path,
                           report: Path, *, csv_output: Path | None = None,
                           replace: bool = False) -> dict[str, Any]:
    """Prepare an editable gold-finalize-compatible worksheet from saved evidence."""
    if csv_output is not None and csv_output.suffix.lower() != '.csv':
        raise ValidationError('--csv-output must end in .csv')
    _path_safety([tasks_path, references_path], [output, report, csv_output], replace)
    tasks, task_sha, refs, refs_sha = load_review_evidence(tasks_path, references_path)
    drafts, csv_rows = [], []
    for task in tasks:
        draft, csv_row = _make_review(task, refs.get(task['id']), task_sha, refs_sha)
        drafts.append(draft)
        csv_rows.append(csv_row)
    # Reject collisions and malformed reference journals BEFORE publishing anything.
    status_tally = Counter(r['reference_evidence']['reference_answer_status'] for r in drafts)
    shape_tally = Counter(r['answer_shape'] for r in drafts)
    flags = Counter(f for r in drafts for f in r['reference_evidence']['review_flags'])
    report_data = {
        'milestone': MILESTONE, 'benchmark_version': __version__, 'status': 'REVIEW',
        'questions': len(tasks), 'reference_records': len(refs),
        'input_dataset_sha256': task_sha, 'references_sha256': refs_sha,
        'reference_answer_status_counts': dict(sorted(status_tally.items())),
        'answer_shape_counts': dict(sorted(shape_tally.items())),
        'review_flag_counts': dict(sorted(flags.items())),
        'gold_verified': 0, 'scientific_accuracy_ready': False,
        'output': str(output), 'csv_output': str(csv_output) if csv_output else None,
        'note': 'Observed values are evidence only. All entries remain pending until independent review and gold-finalize.'
    }
    atomic_jsonl(output, drafts, replace=replace)
    if csv_output is not None:
        atomic_csv(csv_output, csv_rows, REVIEW_COLUMNS, replace=replace)
    atomic_json(report, report_data, replace=replace, style='pretty')
    return report_data
