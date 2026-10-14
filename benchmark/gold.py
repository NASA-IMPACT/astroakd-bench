"""0.6.6 gold-answer lifecycle. Evidence is not an independently verified answer."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import re
from typing import Any
from . import __version__
from .validator import load_jsonl, atomic_jsonl, atomic_json, now_utc, ValidationError

MILESTONE = '0.6.6 — GOLD_REFERENCE_AND_THREE_ARM_EVALUATION'


def _read_tasks(path: Path):
    tasks, digest = load_jsonl(path)
    ids = [x.get('id') for x in tasks]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) for i in ids):
        raise ValidationError('Task IDs must be unique strings')
    return tasks, digest


def _path_safety(inputs, outputs, replace):
    in_paths = {Path(p).resolve() for p in inputs if p is not None}
    out_paths = [Path(p).resolve() for p in outputs if p is not None]
    if len(out_paths) != len(set(out_paths)) or in_paths.intersection(out_paths):
        raise ValidationError('Gold input/output paths must be distinct')
    if not replace and any(Path(p).exists() for p in outputs if p is not None):
        raise ValidationError('Gold output already exists; pass --replace')


def gold_draft(tasks_path: Path, output: Path, report: Path, *, references: Path | None = None,
               reference_tasks: Path | None = None, replace: bool = False) -> dict[str, Any]:
    """Make an editable, unapproved 50-task rubric. Never synthesize gold values."""
    _path_safety([tasks_path, references, reference_tasks], [output, report], replace)
    tasks, task_hash = _read_tasks(tasks_path)
    refs = {}
    ref_hash = None
    ref_input_hash = None
    if references:
        if reference_tasks is None:
            raise ValidationError('--reference-tasks required to bind partial references to their own dataset')
        subset, ref_input_hash = _read_tasks(reference_tasks)
        subset_ids = {x['id'] for x in subset}
        if not subset_ids.issubset({t['id'] for t in tasks}):
            raise ValidationError('Reference-task subset contains IDs absent from mixed dataset')
        records, ref_hash = load_jsonl(references, max_bytes=512*1024*1024)
        for rec in records:
            tid = rec.get('task_id')
            if tid not in subset_ids or tid in refs or rec.get('input_dataset_sha256') != ref_input_hash:
                raise ValidationError(f'Reference journal ID/hash mismatch: {tid}')
            refs[tid] = rec
    draft = []
    for t in tasks:
        ident = t['id']; rec = refs.get(ident)
        checks = (rec or {}).get('evaluation', {}).get('checks', {})
        draft.append({
            'task_id': ident,
            'task_type': t.get('task_type', 'archive_driven'),
            'question': t.get('question'),
            'module': t.get('module'),
            'target': t.get('target'),
            'answer_spec': t.get('answer_spec', {}),
            'input_dataset_sha256': task_hash,
            'reference_evidence': {
                'disposition': rec.get('disposition') if rec else 'not_collected',
                'returned_rows': checks.get('returned_rows'),
                'reported_total_rows': checks.get('reported_total_rows'),
                'truncated': checks.get('truncated'),
                'reference_response_sha256': hashlib.sha256(json.dumps(rec.get('response'),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest() if rec and rec.get('response') else None,
                'partial_reference_file_sha256': ref_hash if rec else None,
            },
            'question_review': 'pending',  # approve or reject question before assigning truth
            'gold_status': 'pending',     # pending | verified | rejected
            'gold': None,                # reviewer edits: kind, values, optional tolerance
            'sources': [],              # >=2 independently reviewed sources with URLs/IDs
            'reviewer': None,
            'review_notes': '',
        })
    atomic_jsonl(output,draft,replace=replace)
    counts = dict(Counter(t['task_type'] for t in draft))
    result = {'milestone':MILESTONE,'benchmark_version':__version__, 'status':'REVIEW',
              'task_count':len(draft),'by_task_type':counts,'source_dataset_sha256':task_hash,
              'references_collected':len(refs),'gold_verified':0,
              'reference_source_sha256':ref_hash,'reference_tasks_sha256':ref_input_hash,
              'scientific_accuracy_ready':False,'output':str(output)}
    atomic_json(report,result,replace=replace,style='pretty')
    return result


def gold_finalize(tasks_path: Path, reviewed: Path, output: Path, report: Path, *,
                  allow_partial: bool = False, replace: bool = False) -> dict[str, Any]:
    """Freeze only human-verified values with >=2 independent source *origins*."""
    _path_safety([tasks_path, reviewed],[output, report],replace)
    tasks, original_hash = _read_tasks(tasks_path)
    rows, reviewed_hash = load_jsonl(reviewed,max_bytes=10*1024*1024)
    if len(rows) != len(tasks) or [r.get('task_id') for r in rows] != [t['id'] for t in tasks]:
        raise ValidationError('Reviewed gold IDs/order must match ALL source questions')
    frozen = []
    for task,row in zip(tasks, rows):
        tid = task['id']
        if row.get('input_dataset_sha256') != original_hash or row.get('question') != task.get('question'):
            raise ValidationError(f'Gold task/hash/question altered for {tid}')
        status = row.get('gold_status')
        if status not in ('pending', 'verified', 'rejected'):
            raise ValidationError(f'Unknown gold_status for {tid}')
        if status == 'verified':
            if row.get('question_review') != 'approved':
                raise ValidationError(f'Question is not approved: {tid}')
            gold = row.get('gold')
            if not isinstance(gold,dict) or gold.get('kind') not in ('set','numeric','text'):
                raise ValidationError(f'Gold kind must be set, numeric or text: {tid}')
            vals = gold.get('values')
            if not isinstance(vals,list) or not vals or any(not isinstance(v,(str,int,float)) or isinstance(v,bool) for v in vals):
                raise ValidationError(f'Gold values must be a nonempty scalar array: {tid}')
            if gold['kind'] == 'set' and row.get('reference_evidence',{}).get('truncated') is True:
                if gold.get('complete_scope_review') is not True or not isinstance(row.get('review_notes'),str) or len(row['review_notes'].strip()) < 15:
                    raise ValidationError(f'Truncated reference for {tid}: reviewer must independently confirm the COMPLETE requested set and document evidence')
            if gold['kind'] == 'numeric':
                if len(vals) != 1 or 'unit' not in gold:
                    raise ValidationError(f'Numeric gold needs one value and unit: {tid}')
                try:
                    number = float(vals[0]); tolerance = float(gold.get('absolute_tolerance',0))
                except (ValueError,TypeError):
                    raise ValidationError(f'Invalid numeric gold: {tid}')
                import math
                if not math.isfinite(number) or not math.isfinite(tolerance) or tolerance < 0:
                    raise ValidationError(f'Invalid numeric tolerance: {tid}')
            sources = row.get('sources')
            if not isinstance(sources,list) or len(sources)<2:
                raise ValidationError(f'Two independently reviewed source records required: {tid}')
            origins=set()
            for source in sources:
                if not isinstance(source,dict) or not isinstance(source.get('uri'),str) or not isinstance(source.get('description'),str) or not source['description'].strip():
                    raise ValidationError(f'Invalid source evidence record: {tid}')
                uri=source['uri']; parsed=urlparse(uri)
                if parsed.scheme not in ('https','http') or not parsed.netloc:
                    raise ValidationError(f'Source needs an HTTP(S) citation URI: {tid}')
                origins.add(parsed.netloc.lower())
            if len(origins)<2:
                raise ValidationError(f'Gold citations must use two distinct independent source hosts: {tid}')
            if not isinstance(row.get('reviewer'),str) or not row['reviewer'].strip():
                raise ValidationError(f'Gold reviewer attribution missing: {tid}')
        frozen.append(row)
    approved = sum(r['gold_status']=='verified' for r in frozen)
    if not allow_partial and approved != len(tasks):
        raise ValidationError(f'Only {approved}/{len(tasks)} gold answers verified; use --allow-partial to freeze partial review')
    atomic_jsonl(output,frozen,replace=replace)
    result={'milestone':MILESTONE,'benchmark_version':__version__,
            'status':'COMPLETE' if approved==len(tasks) else 'PARTIAL',
            'source_dataset_sha256':original_hash,'reviewed_sha256':reviewed_hash,
            'total_tasks':len(tasks),'verified_gold_answers':approved,
            'unscorable_tasks':len(tasks)-approved,
            'scientific_accuracy_ready':approved==len(tasks),
            'frozen_gold_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'note':'Two citation hosts and human approval are procedural checks, not automated scientific truth verification.',
            'output':str(output)}
    atomic_json(report,result,replace=replace,style='pretty')
    return result
