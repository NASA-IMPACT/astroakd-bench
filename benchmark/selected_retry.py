#!/usr/bin/env python3
"""One-off, non-destructive retry of failed mcp_only records in AstroAKD-Bench.

Execute from the AstroAKD-Bench repository root. Uses original questions and
existing runner components; runs only the selected failed MCP-only records.
The original 300-run journal is never modified. Re-tried runs get separate
provenance and an optional derived 300-run journal for operational comparison.
This is a diagnostic with different budgets, not part of the original frozen trial.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from .agent_runner import OpenAIAgent, TracedMCPGateway
from .client import AstroqueryMCPClient
from .gold import _read_tasks
from .mcp_config import resolve_mcp_url
from .three_arm import MINIMAL, _parse_answer
from .validator import now_utc

def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def _write_new(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')


async def _retry_one(task, digest, old, *, args, sdk, client_factory=None):
    start = time.monotonic()
    trace, usage, error = [], {}, None
    answer = {'answer':'', 'answer_values':None, 'unit':None, 'sources':[],
              'abstained':True, 'parse_status':'unstructured'}
    status='error'
    try:
        async with asyncio.timeout(args.task_timeout):
            factory = client_factory or (lambda: AstroqueryMCPClient(resolve_mcp_url(args.mcp_url), timeout=args.timeout))
            async with factory() as conn:
                tools=await conn.list_tools()
                gate=TracedMCPGateway(conn, max_calls=args.max_calls,
                    max_tool_bytes=args.max_tool_bytes, available=tools,
                    question=task['question'], extended_tools=True)
                trace=gate.events
                agent=OpenAIAgent(model=args.model, sdk_client=sdk, system_prompt=MINIMAL)
                result=await agent.run(task['question'], gate, args.max_turns)
                answer=_parse_answer(result['answer'])
                usage=result.get('token_usage',{})
                status='completed'
    except Exception as exc:
        error={'type':type(exc).__name__, 'message':str(exc)[:500]}
    return {'task_id':task['id'], 'task_type':task.get('task_type'), 'arm':'mcp_only',
        'model':args.model, 'status':status, 'answer':answer, 'trace':trace,
        'token_usage':usage, 'duration_seconds':round(time.monotonic()-start,4),
        'error':error, 'successful_mcp_queries':sum(1 for e in trace
            if e.get('tool') in ('astroquery_execute','ads_query_compact','ads_get_paper','simbad_query_bibobj')
            and e.get('status')=='ok' and (e.get('response_success') is True
            if e.get('tool')=='astroquery_execute' else True)),
        'candidate_sha256':digest, 'agent_instruction_sha256':None,
        'timestamp_utc':now_utc(), 'diagnostic_retry':{
            'original_error':old.get('error'), 'original_status':old.get('status'),
            'max_turns':args.max_turns, 'max_calls':args.max_calls,
            'timeout':args.timeout, 'task_timeout':args.task_timeout,
            'note':'CHANGED-BUDGET DIAGNOSTIC, NOT ORIGINAL A/B/C EXPERIMENT'}}


async def retry_failed_mcp(*, tasks_path:Path, runs_path:Path, output_dir:Path,
        model:str='gpt-5.2', mcp_url:str|None=None, timeout:float=900,
        task_timeout:float=2400, max_turns:int=16, max_calls:int=20,
        max_tool_bytes:int=65536, task_ids:list[str]|None=None,
        dry_run:bool=False, sdk=None, run_one=None, progress=None):
    """Retry *only* error-status mcp_only records in a separate immutable diagnostic.

    A completed 300-run experiment is never overwritten or resumed. Differing
    budgets are declared and all original records retain their provenance.
    """
    if not 1<=max_turns<=32 or not 1<=max_calls<=100 or timeout<=0 or task_timeout<=0:
        raise ValueError('Invalid retry budget')
    tasks,digest=_read_tasks(Path(tasks_path))
    original=_read_jsonl(Path(runs_path))
    byid={t['id']:t for t in tasks}
    keys={(r.get('task_id'),r.get('arm')) for r in original}
    if len(original)!=len(tasks)*3 or len(keys)!=len(original) or any(
        r.get('candidate_sha256')!=digest or r.get('task_id') not in byid or
        r.get('arm') not in ('mcp_only','mcp_instruction','web_only') for r in original):
        raise ValueError('Source 300-run journal is incomplete or fingerprint mismatched')
    if any(r.get('model')!=model for r in original):
        raise ValueError('Retry model differs from original A/B/C experiment')
    failed=[r for r in original if r['arm']=='mcp_only' and r.get('status')=='error']
    if task_ids is not None:
        if len(set(task_ids))!=len(task_ids) or any(t not in byid for t in task_ids):
            raise ValueError('Invalid or duplicate retry task IDs')
        if set(task_ids)-{r['task_id'] for r in failed}:
            raise ValueError('Some requested IDs are not failed MCP-only runs')
        failed=[r for r in failed if r['task_id'] in set(task_ids)]
    if not failed:
        raise ValueError('No failed MCP-only records selected')
    output_dir=Path(output_dir)
    prefix=Path(runs_path).stem.replace('_ABC_runs','')
    retries=output_dir/(prefix+f'_mcp_only_turn{max_turns}_retries.jsonl')
    derived=output_dir/(prefix+f'_ABC_runs_turn{max_turns}_diagnostic.jsonl')
    report_path=output_dir/(prefix+f'_mcp_only_turn{max_turns}_retry_report.json')
    if any(p.exists() for p in (retries,derived,report_path)):
        raise FileExistsError('Diagnostic retry output already exists; never overwrite existing evidence')
    result={'status':'PASS' if dry_run else 'COMPLETE', 'dry_run':dry_run,
        'retry_count':len(failed), 'task_ids':[r['task_id'] for r in failed],
        'baseline_runs_sha256':hashlib.sha256(Path(runs_path).read_bytes()).hexdigest(),
        'dataset_sha256':digest, 'original_runs':str(runs_path),
        'retry_output':str(retries),'diagnostic_runs':str(derived),
        'changed_budget':{'max_turns':max_turns,'max_calls':max_calls,
                          'timeout':timeout,'task_timeout':task_timeout},
        'scientific_accuracy':'NOT_ASSESSED',
        'warning':'Diagnostics with changed limits must not replace the baseline'}
    if dry_run:
        return result
    if sdk is None:
        if not os.environ.get('OPENAI_API_KEY'):
            raise RuntimeError('OPENAI_API_KEY not set')
        from openai import AsyncOpenAI
        sdk=AsyncOpenAI(timeout=min(task_timeout,120),max_retries=0)
    from types import SimpleNamespace
    args=SimpleNamespace(model=model,mcp_url=mcp_url,timeout=timeout,
        task_timeout=task_timeout,max_turns=max_turns,max_calls=max_calls,
        max_tool_bytes=max_tool_bytes)
    new=[]
    for old in failed:
        tid=old['task_id']
        if progress: progress(f'RETRY {tid} mcp_only')
        runner=run_one or _retry_one
        rec=await runner(byid[tid],digest,old,args=args,sdk=sdk)
        if rec.get('task_id')!=tid or rec.get('arm')!='mcp_only' or rec.get('candidate_sha256')!=digest:
            raise ValueError('Retry runner returned mismatched task/arm/hash')
        new.append(rec)
        if progress: progress(f'DONE {tid} {rec.get("status")}')
    _write_new(retries,new)
    replacement={(r['task_id'],r['arm']):r for r in new if r['status']=='completed'}
    _write_new(derived,[replacement.get((r['task_id'],r['arm']),r) for r in original])
    result['retry_completed']=sum(r['status']=='completed' for r in new)
    result['retry_errors']=len(new)-result['retry_completed']
    report_path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
