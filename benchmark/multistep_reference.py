"""Resumable reference collection for planned two-archive and literature workflows.

Only independently specified read-only MCP calls are executed. Missing archive
calls for literature questions remain PARTIAL: a paper list is not an answer key.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from .client import AstroqueryMCPClient
from .simple_workflows import dataset_paths

MODULES={'simbad','gaia','mast','heasarc','vizier'}


def _atomic_jsonl(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as f:
        for x in rows:f.write(json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def _specify_steps(task, plans):
    if task['task_type']=='multi_archive':
        return task.get('constraints',{}).get('multi_archive_steps') or []
    return plans.get(task['id'],[])


def _check_step(spec):
    module=spec.get('module');call=spec.get('reference_call') or {}
    args=call.get('arguments',{});fields=spec.get('expected_columns',[])
    if (module not in MODULES or call.get('tool')!='astroquery_execute' or
        args.get('module_name')!=module or args.get('function_name') not in {'query_object','query_region'} or
        not isinstance(args.get('params'),dict) or not isinstance(fields,list) or not fields or
        len(fields)>6 or not all(isinstance(f,str) and f and len(f)<80 for f in fields)):
        raise ValueError('Unsafe or incomplete multi-step MCP query plan')
    return args,fields


def _extract(payload, fields, module):
    if not isinstance(payload,dict) or payload.get('success') is False:
        return None,'mcp_unsuccessful'
    tables=payload.get('result')
    if not isinstance(tables,dict) or not isinstance(tables.get('data'),list):
        return None,'not_structured_table'
    if tables.get('truncated') is True or payload.get('truncated') is True:
        return None,'truncated_reference'
    rows=tables['data']
    if not rows:return None,'empty_reference'
    total=tables.get('total_rows',tables.get('row_count'))
    if isinstance(total,int) and total>len(rows):return None,'truncated_reference'
    if len(rows)>100:return None,'oversized_reference'
    cols={c.get('name') for c in tables.get('columns',[]) if isinstance(c,dict)}
    if any(f not in cols for f in fields):return None,'missing_expected_field'
    out=[]
    for ri,row in enumerate(rows):
        if not isinstance(row,dict):return None,'invalid_row'
        for field in fields:
            if row.get(field) is None:return None,'null_expected_value'
            out.append({'field':module+':'+field,'row_index':ri,'table_index':0,'value':row[field]})
    return out,None


async def collect_multistep(*,name='synthetic_100',output_dir='datasets',url=None,
                            timeout=900,attempts=2,resume=False,replace=False,limit=None,
                            literature_plans=None,client_factory=None,progress=None):
    paths=dataset_paths(name=name,output_dir=output_dir)
    tasks_path=paths['tasks'];task_data=tasks_path.read_bytes();digest=hashlib.sha256(task_data).hexdigest()
    tasks=[json.loads(line) for line in paths['multistep'].read_text().splitlines() if line.strip()]
    expected={t['id']:t for t in tasks}
    if len(expected)!=len(tasks):raise ValueError('Duplicate multi-step task IDs')
    output=paths['references'].with_name(name+'_multistep_references.jsonl')
    journal=output.with_suffix('.progress.jsonl')
    plan_map={}
    if literature_plans is not None:
        for x in [json.loads(l) for l in Path(literature_plans).read_text().splitlines() if l.strip()]:
            if x.get('task_id') not in expected:raise ValueError('Unknown literature plan task_id')
            if x['task_id'] in plan_map:raise ValueError('Duplicate literature plan task_id')
            plan_map[x['task_id']]=x.get('steps',[])
    if (output.exists() or journal.exists()) and not (resume or replace):
        raise FileExistsError('Multi-step reference output exists; use --resume or --replace')
    if resume and not journal.exists() and not output.exists():
        raise FileNotFoundError('No multi-step reference journal to resume')
    if replace:
        output.unlink(missing_ok=True);journal.unlink(missing_ok=True)
    existing=[]
    origin=journal if journal.exists() else (output if output.exists() else None)
    if origin:
        for line in origin.read_text().splitlines():
            if not line.strip():continue
            r=json.loads(line)
            if r.get('dataset_sha256')!=digest or r['task_id'] not in expected:
                raise ValueError('Multi-step journal dataset/ID mismatch')
            existing.append(r)
    if len({r['task_id'] for r in existing})!=len(existing):raise ValueError('Duplicate multi-step journal rows')
    saved={r['task_id']:r for r in existing}
    # A later independently supplied observation plan can reopen only previously
    # incomplete literature records; completed two-archive tasks stay frozen.
    pending=[t for t in tasks if (t['id'] not in saved or
             (t['id'] in plan_map and saved[t['id']].get('status')=='needs_independent_archive_query_plan'))]
    if limit is not None:pending=pending[:limit]
    mkclient=client_factory or (lambda:AstroqueryMCPClient(url,timeout=timeout))
    async with mkclient() as client:
        for task in pending:
            tid=task['id'];steps=_specify_steps(task,plan_map)
            result={'task_id':tid,'task_type':task['task_type'], 'dataset_sha256':digest,
                    'status':'partial', 'steps':[], 'answer_evidence':[], 'answer_shape':'multi_archive_values'}
            if progress:progress('START '+tid)
            if task['task_type']=='literature_driven':
                # Existing ADS search metadata is a literature candidate, not verified
                # evidence of the paper-to-observation relation requested by the task.
                research=task.get('research_evidence') or {}
                result['ads_research_bibcodes']=research.get('bibcodes',[])
                if not steps:result['status']='needs_independent_archive_query_plan'
            else:
                result['status']='incomplete'
            for step in steps:
                args,fields=_check_step(step)
                entry={'module':step['module'],'function':args['function_name'], 'expected_columns':fields}
                try:
                    evidence=None;reason='no_response'
                    for attempt in range(1,attempts+1):
                        try:
                            payload=await client.call('astroquery_execute',args)
                            evidence,reason=_extract(payload,fields,step['module'])
                            entry['response_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
                            if evidence is not None:break
                        except (Exception) as exc:
                            reason=type(exc).__name__
                    entry['status']='complete' if evidence is not None else reason
                    if evidence is not None:result['answer_evidence'].extend(evidence)
                except (ValueError,TypeError) as exc:
                    entry['status']='invalid_plan'
                result['steps'].append(entry)
                if entry['status']!='complete':result['status']='incomplete_step_evidence'
            if steps and all(x['status']=='complete' for x in result['steps']) and len(result['steps'])==len(steps):
                # Literature references additionally require literature-to-observation
                # association, not merely two independent sets of archive values.
                result['status']='complete' if task['task_type']=='multi_archive' else 'literature_association_not_verified'
            saved[tid]=result
            _atomic_jsonl(journal,[saved[t['id']] for t in tasks if t['id'] in saved])
            if progress:progress('DONE '+tid+' '+result['status'])
    if len(saved)==len(tasks):_atomic_jsonl(output,[saved[t['id']] for t in tasks])
    statuses=Counter(r['status'] for r in saved.values())
    report={'milestone':'0.6.7.11.11 - AUTOMATED_REFERENCE_ANSWER_SCORING',
            'status':'COMPLETE' if len(saved)==len(tasks) else 'PARTIAL',
            'dataset_sha256':digest,'tasks_total':len(tasks),'tasks_recorded':len(saved),
            'reference_complete':statuses.get('complete',0),'dispositions':dict(statuses),
            'journal':str(journal),'output':str(output) if output.exists() else None,
            'note':'Missing observational plans or unverified literature associations are excluded from scoring.'}
    return report
