"""0.5.1 deterministic, auditable scoring of recorded MCP agent runs.

Scoring verifies observable archive/function/parameter execution, reference
structure and a restricted set of answer claims. It DOES NOT establish general
astrophysical truth or evaluate arbitrary natural-language assertions.
"""
from __future__ import annotations
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Any

from . import __version__
from .agent_runner import load_run_inputs
from .formatting import json_text
from .validator import (ValidationError, atomic_json, atomic_jsonl, load_jsonl,
                        now_utc, EXPECTED_ACCEPTED_020_SHA256)

MILESTONE = '0.5.1 — PRETTY_SCORE_EXPORT_CLOSURE'
WEIGHTS = {'archive_selection': 20, 'function_selection': 15,
           'parameter_correctness': 25, 'successful_execution': 15,
           'reference_result_agreement': 15, 'answer_claim_check': 10}

class EvaluationError(ValidationError):
    pass


def _close_number(a: Any, b: Any, *, tolerance: float = 0.0001) -> bool:
    return (not isinstance(a, bool) and not isinstance(b, bool) and
            isinstance(a, (int, float)) and isinstance(b, (int, float)) and
            math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance)


def _param_check(expected: dict, observed: Any) -> dict[str, Any]:
    if not isinstance(observed, dict):
        return {'fraction': 0.0, 'matched': 0, 'total': 1, 'differences': ['params absent']}
    diff = []
    def eq(path: str, a: Any, b: Any) -> bool:
        if isinstance(a, dict):
            if not isinstance(b, dict):
                diff.append(path)
                return False
            keys = set(a) | set(b)
            if path.endswith(('coordinates','coordinate','position')) and b.get('frame', 'icrs') == 'icrs':
                keys.discard('frame')
            ok = True
            for key in sorted(keys):
                if key in a and key in b:
                    ok = eq(f'{path}.{key}', a[key], b[key]) and ok
                elif key == 'frame' and a.get('frame') == 'icrs' and key not in b:
                    continue
                else:
                    diff.append(f'{path}.{key}')
                    ok = False
            return ok
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            matched = _close_number(a,b)
        elif isinstance(a, str) and isinstance(b, str):
            matched = a.strip().casefold() == b.strip().casefold()
        else:
            matched = a == b
        if not matched:
            diff.append(path)
        return matched
    # Weight semantic arguments rather than every individual numeric key.
    matched = sum(eq(f'params.{key}', val, observed.get(key)) for key,val in expected.items())
    unexpected = sorted(set(observed)-set(expected))
    diff.extend(f'params.{key}' for key in unexpected)
    total = len(expected) + len(unexpected)
    return {'fraction': round(matched/total,6) if total else 1.0,
            'matched': matched, 'total': total, 'differences': diff}


def _result_counts(response: Any) -> tuple[int | None, int | None]:
    """Return (returned_rows, total_rows) from serialized MCP table(s)."""
    if not isinstance(response, dict) or response.get('success') is not True:
        return None, None
    result = response.get('result')
    if isinstance(result, dict):
        rows = result.get('row_count')
        total = result.get('total_rows', rows)
        if isinstance(rows, int) and isinstance(total, int) and rows >= 0 and total >= rows:
            return rows, total
    if isinstance(result, list):
        counts = [t.get('row_count') for t in result if isinstance(t, dict)]
        if len(counts) == len(result) and all(isinstance(v,int) and v>=0 for v in counts):
            return sum(counts), sum(counts)
    return None, None


def _answer_claim(answer: str, reference: dict, agent_response: Any, truncated: bool) -> dict:
    """Check a narrow, auditable set of numeric claims; otherwise abstain."""
    if not answer.strip():
        return {'status': 'NO_ANSWER', 'score': 0, 'checked': []}
    if truncated:
        # Acknowledging truncation is honest but does not validate the answer.
        acknowledged = bool(re.search(r'limit|truncat|exceed|too (?:large|many)', answer, re.I))
        return {'status': 'TRUNCATION_DISCLOSED' if acknowledged else 'TRUNCATED_UNVERIFIABLE',
                'score': 5 if acknowledged else 0, 'checked': []}
    checks = []
    _, ref_total = _result_counts(reference)
    _, live_total = _result_counts(agent_response)
    # Do not use counts to judge agent correctness when the archive has drifted.
    if ref_total is not None and live_total == ref_total:
        patterns = [r'\b(?:there are|there were|returned|found|contains?|retrieved)\s+([\d,]+)\s+(?:\w+\s+){0,3}?(?:observations|sources|objects|records|rows)\b',
                    r'\b([\d,]+)\s+(?:observations|sources|objects|records|rows)\s+(?:were|was)\s+found\b']
        claims = []
        for pat in patterns:
            claims += [int(m.replace(',','')) for m in re.findall(pat, answer, re.I)]
        if claims:
            checks.append({'claim': 'result_count', 'asserted': claims, 'reference': ref_total,
                           'status': 'MATCH' if all(n == ref_total for n in claims) else 'MISMATCH'})
    if ref_total == 0 and live_total == 0:
        negative = bool(re.search(r'no (?:matching |available )?(?:observations|results|sources|rows|records)|(?:zero|0) (?:results|sources|rows|records)', answer, re.I))
        checks.append({'claim': 'empty_result', 'status': 'MATCH' if negative else 'NOT_CONFIRMED'})
    # For SIMBAD, verify explicitly stated RA/Dec against returned reference row.
    if isinstance(reference, dict) and reference.get('module') == 'simbad':
        first = (reference.get('result') or {}).get('data') if isinstance(reference.get('result'),dict) else None
        if isinstance(first, list) and first:
            ra = re.search(r'(?:Right Ascension|\bRA\b)\s*(?:\([^)]*\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)', answer, re.I)
            dec = re.search(r'(?:Declination|\bDec\b)\s*(?:\([^)]*\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)', answer, re.I)
            if ra and dec:
                data=first[0]
                match = (_close_number(float(ra.group(1)),data.get('ra'),tolerance=0.001) and
                         _close_number(float(dec.group(1)),data.get('dec'),tolerance=0.001))
                checks.append({'claim': 'object_coordinates_degrees', 'status': 'MATCH' if match else 'MISMATCH',
                               'asserted': [float(ra.group(1)),float(dec.group(1))],
                               'reference': [data.get('ra'),data.get('dec')]})
    if any(x['status']=='MISMATCH' for x in checks):
        status,score = 'CONTRADICTED',0
    elif checks and all(x['status']=='MATCH' for x in checks):
        status,score = 'LIMITED_CHECK_PASS',10
    else:
        status,score = 'NOT_ASSESSED',0
    return {'status':status, 'score':score, 'checked':checks}


def score_task(task: dict, reference: dict, run: dict) -> dict:
    expected = task['reference_call']['arguments']
    calls = [event for event in run.get('trace', [])
             if isinstance(event, dict) and event.get('tool') == 'astroquery_execute']
    chosen = None
    best = (-1,-1,-1,-1)
    for event in calls:
        args=event.get('arguments',{})
        if not isinstance(args,dict):
            continue
        mod = args.get('module_name') == expected['module_name']
        func = mod and args.get('function_name') == expected['function_name']
        param = _param_check(expected['params'], args.get('params')) if func else {'fraction':0.,'matched':0,'total':1,'differences':['archive_or_function_mismatch']}
        rank = (int(mod),int(func),param['fraction'], int(event.get('status')=='ok' and event.get('response_success') is True))
        if rank > best:
            best=rank
            chosen=(event,mod,func,param)
    if chosen is None:
        e,mod,func,par = None,False,False,{'fraction':0.,'matched':0,'total':1,'differences':['no_execute_call']}
    else:
        e,mod,func,par=chosen
    # Tool success must be independently present in the event, not just the
    # top-level per-task status or query_evidence summary.
    success=bool(e and e.get('status')=='ok' and e.get('response_success') is True)
    response=e.get('response') if success else None
    truncated=bool(e and e.get('response_truncated'))
    ref_returned,ref_total=_result_counts(reference['response'])
    agent_returned,agent_total=_result_counts(response)
    if not success:
        consistency='NO_SUCCESSFUL_QUERY'
    elif truncated:
        consistency='INDETERMINATE_TRUNCATED'
    elif ref_total is None or agent_total is None:
        consistency='INDETERMINATE_RESPONSE'
    elif ref_total!=agent_total:
        consistency='ARCHIVE_DRIFT_OR_MISMATCH'
    elif (ref_returned==0)!=(agent_returned==0):
        consistency='EMPTY_NONEMPTY_MISMATCH'
    else:
        consistency='MATCH'
    answer=run.get('answer','') if run.get('status')=='completed' else ''
    claim=_answer_claim(answer,reference['response'],response,truncated)
    scores={
        'archive_selection': 20 if mod else 0,
        'function_selection': 15 if func else 0,
        'parameter_correctness': round(25*par['fraction'],2) if func else 0,
        'successful_execution': 15 if success and mod and func else 0,
        'reference_result_agreement': 15 if consistency=='MATCH' else 0,
        'answer_claim_check': claim['score'],
    }
    score=round(sum(scores.values()),2)
    if run.get('agent')=='echo':
        technical='HARNESS_ONLY'
    elif (run.get('status')!='completed' or not answer.strip() or
          not (mod and func and par['fraction'] == 1 and success) or
          claim['status']=='CONTRADICTED' or
          consistency in ('NO_SUCCESSFUL_QUERY','EMPTY_NONEMPTY_MISMATCH')):
        technical='FAIL'
    elif consistency != 'MATCH' or claim['status'] in ('NOT_ASSESSED','TRUNCATION_DISCLOSED','TRUNCATED_UNVERIFIABLE'):
        technical='REVIEW'
    else:
        technical='PASS'
    return {
        'task_id':task['id'],'module':task['module'],'agent':run.get('agent'),
        'run_status':run.get('status'), 'score':score, 'max_score':100,
        'metric_scores':scores, 'parameter_comparison':par,
        'reference_result':{'disposition':reference['disposition'],'returned_rows':ref_returned,'total_rows':ref_total},
        'observed_result':{'successful_execute':success,'returned_rows':agent_returned,
                           'total_rows':agent_total,'response_truncated':truncated},
        'result_agreement':consistency, 'answer_claim_check':claim,
        'technical_gate':technical,'scientific_answer_gate':'INDEPENDENT_REVIEW_REQUIRED',
        'mcp_calls':len(run.get('trace',[])),
        'rejected_calls':sum(ev.get('status')=='rejected' for ev in run.get('trace',[])),
        'errors':sum(ev.get('status')=='error' for ev in run.get('trace',[])),
    }


def evaluate(tasks_path: Path, reference_path: Path, runs_path: Path, output: Path,
             report_path: Path, *, csv_path: Path | None = None,
             pretty_output: Path | None = None, strict_accepted_020: bool = False,
             json_format: str = 'compact', replace: bool = False) -> dict:
    if json_format not in ('compact','pretty'):
        raise EvaluationError('Invalid JSON format')
    if pretty_output is not None and pretty_output.suffix.lower() != '.json':
        raise EvaluationError('--pretty-output must be a .json path (not .jsonl)')
    destinations=[output,report_path]+([csv_path] if csv_path else [])+([pretty_output] if pretty_output else [])
    inputs=[tasks_path,reference_path,runs_path]
    if len({p.resolve() for p in destinations + inputs}) != len(destinations+inputs):
        raise EvaluationError('Input and output paths must all be distinct')
    if any(p.exists() for p in destinations) and not replace:
        raise EvaluationError('Evaluation artifacts already exist; use --replace')
    tasks,task_hash,ref_hash=load_run_inputs(tasks_path,reference_path,strict_sha=strict_accepted_020)
    references, _ = load_jsonl(reference_path,max_bytes=512*1024*1024)
    runs,run_hash=load_jsonl(runs_path,max_bytes=512*1024*1024)
    by_id={task['id']:task for task in tasks}
    ref_by_id={x['task_id']:x for x in references}
    seen=set(); scored=[]
    for record in runs:
        ident=record.get('task_id')
        if ident not in by_id or ident in seen:
            raise EvaluationError(f'Unknown or duplicate agent task: {ident}')
        if record.get('input_dataset_sha256') != task_hash or record.get('module') != by_id[ident]['module']:
            raise EvaluationError(f'Agent run context mismatch: {ident}')
        if record.get('agent') not in ('openai','external','echo'):
            raise EvaluationError(f'Unrecognized agent type for {ident}')
        if not isinstance(record.get('trace'),list):
            raise EvaluationError(f'Missing MCP trace for {ident}')
        # Verify untuncated trace payloads against their original SHA256.
        from .validator import json_bytes
        for event in record['trace']:
            if not isinstance(event,dict):
                raise EvaluationError(f'Malformed tool event for {ident}')
            if event.get('status')=='ok' and event.get('response_truncated') is False and 'response_sha256' in event:
                digest=hashlib.sha256(json_bytes(event.get('response'))).hexdigest()
                if digest!=event['response_sha256']:
                    raise EvaluationError(f'Tool response fingerprint mismatch: {ident}')
        seen.add(ident)
        scored.append(score_task(by_id[ident],ref_by_id[ident],record))
    if not scored:
        raise EvaluationError('Agent run file is empty')
    if len({x['agent'] for x in scored})!=1:
        raise EvaluationError('Mixed agent types in run')
    task_order={t['id']:i for i,t in enumerate(tasks)}
    scored.sort(key=lambda x: task_order[x['task_id']])
    agent=scored[0]['agent']
    tally=Counter(x['technical_gate'] for x in scored)
    by_module={}
    for mod in dict.fromkeys(x['module'] for x in scored):
        subset=[x for x in scored if x['module']==mod]
        by_module[mod]={'tasks':len(subset),'mean_technical_score':round(sum(x['score'] for x in subset)/len(subset),2),
                        'technical_gates':dict(sorted(Counter(x['technical_gate'] for x in subset).items()))}
    technical_gate = ('HARNESS_ONLY' if agent=='echo' else
                      'REVIEW' if any(x['technical_gate']=='REVIEW' for x in scored) and not tally.get('FAIL') else
                      'FAIL' if tally.get('FAIL') else 'PASS')
    report={'milestone':MILESTONE,'benchmark_version':__version__,'timestamp_utc':now_utc(),
            'agent':agent, 'total_tasks':len(tasks),'evaluated_tasks':len(scored),
            'remaining_tasks':len(tasks)-len(scored),'status':'COMPLETE' if len(scored)==len(tasks) else 'PARTIAL',
            'candidate_sha256':task_hash,'reference_sha256':ref_hash,'run_sha256':run_hash,
            'mean_technical_score':round(sum(x['score'] for x in scored)/len(scored),2),
            'metric_weights':WEIGHTS, 'technical_gates':dict(sorted(tally.items())),
            'technical_gate':technical_gate, 'scientific_answer_gate':'INDEPENDENT_REVIEW_REQUIRED',
            'by_module':by_module,
            'interpretation':('This score measures tool execution, argument alignment, live/reference row-count '
                              'agreement and a limited set of machine-checkable final-answer claims. '
                              'It is NOT a validated measure of general astrophysical answer correctness. '
                              'Truncated responses and archive changes require review.'),
            'output':str(output),'report':str(report_path)}
    if csv_path:
        report['csv']=str(csv_path)
    if pretty_output is not None:
        report['pretty_output']=str(pretty_output)
        report['pretty_output_format']='json_array_indented'
    # Compute all evidence and serialize before publishing any outputs.
    output.parent.mkdir(parents=True,exist_ok=True)
    atomic_jsonl(output,scored,replace=replace)
    if csv_path:
        csv_path.parent.mkdir(parents=True,exist_ok=True)
        if csv_path.exists() and not replace:
            raise EvaluationError(f'CSV already exists: {csv_path}')
        with csv_path.open('w',newline='',encoding='utf-8') as fp:
            writer=csv.writer(fp)
            writer.writerow(['task_id','module','score','technical_gate','result_agreement',
                             'answer_claim_status','archive_score','function_score','parameter_score',
                             'execution_score','result_score','answer_score'])
            for x in scored:
                s=x['metric_scores']
                writer.writerow([x['task_id'],x['module'],x['score'],x['technical_gate'],x['result_agreement'],
                                 x['answer_claim_check']['status'],*(s[k] for k in WEIGHTS)])
    if pretty_output is not None:
        # Export the exact scored dictionaries in input-task order. Do not
        # modify canonical JSONL, dataset hashes, or scientific judgments.
        atomic_json(pretty_output,scored,style='pretty',replace=replace)
    atomic_json(report_path,report,style=json_format)
    return report
