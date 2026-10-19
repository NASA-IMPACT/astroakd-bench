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


def _payload_diagnostics(payload):
    """Keep bounded schema diagnostics, not a possibly sensitive raw MCP payload."""
    result=payload.get('result') if isinstance(payload,dict) else None
    tables=result if isinstance(result,list) else ([result] if isinstance(result,dict) else [])
    return {'result_kind':type(result).__name__, 'table_count':len(tables),
            'tables':[{'columns':[str(c.get('name',''))[:80] for c in t.get('columns',[]) if isinstance(c,dict)][:60],
                       'returned_rows':len(t.get('data',[])) if isinstance(t.get('data'),list) else None,
                       'reported_rows':t.get('total_rows',t.get('row_count')) if isinstance(t.get('total_rows',t.get('row_count')),int) else None,
                       'truncated':t.get('truncated') is True}
                      for t in tables[:8] if isinstance(t,dict)]}


def _extract(payload, fields, module):
    """Normalize singular and VizieR-style table lists without guessing at missing rows."""
    if not isinstance(payload,dict) or payload.get('success') is False:
        return None,'mcp_unsuccessful'
    raw=payload.get('result')
    if isinstance(raw,dict):tables=[raw]
    elif isinstance(raw,list):tables=raw
    else:return None,'not_structured_table'
    if not tables or not all(isinstance(t,dict) for t in tables):
        return None,'not_structured_table'
    if len(tables)>12:return None,'too_many_tables'
    if payload.get('truncated') is True:return None,'truncated_reference'
    evidence=[];row_total=0
    for ti,t in enumerate(tables):
        if t.get('truncated') is True:return None,'truncated_reference'
        rows=t.get('data')
        if not isinstance(rows,list):return None,'not_structured_table'
        total=t.get('total_rows',t.get('row_count'))
        if isinstance(total,int) and total>len(rows):return None,'truncated_reference'
        row_total+=len(rows)
        if row_total>100:return None,'oversized_reference'
        cols={c.get('name') for c in t.get('columns',[]) if isinstance(c,dict)}
        if any(f not in cols for f in fields):return None,'missing_expected_field'
        for ri,row in enumerate(rows):
            if not isinstance(row,dict):return None,'invalid_row'
            for field in fields:
                if row.get(field) is None:return None,'null_expected_value'
                evidence.append({'field':module+':'+field,'row_index':ri,
                                 'table_index':ti,'value':row[field]})
    if not evidence:return None,'empty_reference'
    return evidence,None


def _literature_draft(task):
    """Create a *bounded candidate plan*, never an asserted paper-to-ObsID association."""
    import re
    target=str(task.get('target','')).strip()
    required=str(task.get('constraints',{}).get('required_result','')).lower()
    named=bool(re.fullmatch(r'(?:NGC\s*\d{1,5}|Haro\s*\d{1,5}|PG\s*\d{3,5}\+\d{2,4})',target,re.I))
    if 'chandra' in required:archive,catalog='heasarc','chanmaster'
    elif 'xmm' in required:archive,catalog='heasarc','xmmmaster'
    elif 'nicer' in required:archive,catalog='heasarc','nicermaster'
    elif 'hst' in required or 'cos' in required:archive,catalog='mast',None
    elif 'simbad' in required:archive,catalog='simbad',None
    else:archive,catalog=None,None
    resolve_call=({'tool':'astroquery_execute','arguments':{
        'module_name':'simbad','function_name':'query_object','params':{'object_name':target}}}
        if named else None)
    archive_template=({'tool':'astroquery_execute','arguments':{
        'module_name':archive,'function_name':'query_region',
        'params_template':{'position':'COORDINATES_FROM_VERIFIED_SIMBAD',
                           'radius':{'value':0.2,'unit':'arcmin'},
                           **({'catalog':catalog} if catalog else {})},
        'max_rows':20}} if named and archive in ('heasarc','mast') else None)
    return {'task_id':task['id'],'target':target,'archive':archive,'catalog':catalog,
            'read_only_target_resolution_call':resolve_call,
            'dependent_archive_query_template':archive_template,
            'radius_arcmin':0.2,'max_rows':20,'bibcodes_are_candidate_only':True,
            'candidate_bibcodes':(task.get('research_evidence') or {}).get('bibcodes',[])[:10],
            'steps_required':['resolve_target_coordinates','bounded_observation_archive_query','verify_paper_to_observation_association'],
            'status':'DRAFT_UNVERIFIED' if named and archive else 'REQUIRES_TARGET_OR_ARCHIVE_RESOLUTION',
            'note':'No observational IDs or literature association may be inferred from a candidate bibcode. This draft is not an executable or scorable reference.'}


def write_literature_drafts(name,output_dir='datasets',*,replace=False):
    """Offline reproducible query-plan drafting, independent of any agent answer."""
    paths=dataset_paths(name=name,output_dir=output_dir)
    tasks=[json.loads(line) for line in paths['multistep'].read_text().splitlines() if line.strip()]
    output=paths['references'].with_name(name+'_literature_plan_drafts.jsonl')
    if output.exists() and not replace:raise FileExistsError(f'{output} exists; use --replace')
    drafts=[_literature_draft(t) for t in tasks if t.get('task_type')=='literature_driven']
    _atomic_jsonl(output,drafts)
    return {'status':'DRAFT_ONLY_NOT_REFERENCE','total':len(drafts),'draft_ready':sum(x['status']=='DRAFT_UNVERIFIED' for x in drafts),
            'requires_resolution':sum(x['status']!='DRAFT_UNVERIFIED' for x in drafts),'output':str(output)}


async def collect_multistep(*,name='synthetic_100',output_dir='datasets',url=None,
                            timeout=900,attempts=2,resume=False,replace=False,limit=None,
                            literature_plans=None,client_factory=None,progress=None,
                            retry_incomplete=False,retry_task_ids=None,dry_run=False):
    paths=dataset_paths(name=name,output_dir=output_dir)
    tasks_path=paths['tasks'];digest=hashlib.sha256(tasks_path.read_bytes()).hexdigest()
    tasks=[json.loads(line) for line in paths['multistep'].read_text().splitlines() if line.strip()]
    expected={t['id']:t for t in tasks}
    if len(expected)!=len(tasks):raise ValueError('Duplicate multi-step task IDs')
    output=paths['references'].with_name(name+'_multistep_references.jsonl')
    journal=output.with_suffix('.progress.jsonl')
    backup=output.with_name(name+'_multistep_references_preretry.jsonl')
    plan_map={}
    if literature_plans is not None:
        for x in [json.loads(l) for l in Path(literature_plans).read_text().splitlines() if l.strip()]:
            tid=x.get('task_id')
            if tid not in expected or expected[tid]['task_type']!='literature_driven':raise ValueError('Unknown literature plan task_id')
            if tid in plan_map:raise ValueError('Duplicate literature plan task_id')
            plan_map[tid]=x.get('steps',[])
    if retry_incomplete and (not resume or replace):
        raise ValueError('--retry-incomplete requires --resume and must not use --replace')
    if retry_task_ids and not retry_incomplete:
        raise ValueError('--retry-task-ids requires --retry-incomplete')
    if (output.exists() or journal.exists()) and not (resume or replace):
        raise FileExistsError('Multi-step reference output exists; use --resume or --replace')
    if resume and not journal.exists() and not output.exists():
        raise FileNotFoundError('No multi-step reference journal to resume')
    if replace and not dry_run:
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
    pending=[]
    for t in tasks:
        tid=t['id'];old=saved.get(tid)
        if old is None:
            if retry_incomplete:continue
            pending.append(t)
        elif retry_incomplete and (old.get('status')=='incomplete_step_evidence' or
                (tid in plan_map and old.get('status') in ('needs_independent_archive_query_plan','literature_association_not_verified'))):
            pending.append(t)
        elif not retry_incomplete and tid in plan_map and old.get('status')=='needs_independent_archive_query_plan':
            pending.append(t)
    if retry_task_ids:
        chosen=set(retry_task_ids)
        if chosen-set(expected):raise ValueError('Unknown retry task ID(s)')
        pending=[t for t in pending if t['id'] in chosen]
    if limit is not None:pending=pending[:limit]
    selection={'status':'PASS' if dry_run else 'RUNNING','dry_run':dry_run,'selected_task_ids':[t['id'] for t in pending],
               'selected_count':len(pending),'completed_preserved':sum(r.get('status')=='complete' for r in existing),
               'dataset_sha256':digest,'previous_journal_sha256':hashlib.sha256(origin.read_bytes()).hexdigest() if origin else None}
    if dry_run:return selection
    # Immutable copy of the previous journal before any retry writes; original task,
    # single-call reference and agent run files are never modified.
    if retry_incomplete and pending and origin and not backup.exists():
        _atomic_jsonl(backup,existing)
    mkclient=client_factory or (lambda:AstroqueryMCPClient(url,timeout=timeout))
    async with mkclient() as client:
        for task in pending:
            tid=task['id'];steps=_specify_steps(task,plan_map);old=saved.get(tid)
            result={'task_id':tid,'task_type':task['task_type'], 'dataset_sha256':digest,
                    'status':'partial', 'steps':[], 'answer_evidence':[], 'answer_shape':'multi_archive_values'}
            if old:
                result['previous_status']=old.get('status')
                result['retry_history']=list(old.get('retry_history',[]))+[{'status':old.get('status'),
                    'step_statuses':[s.get('status') for s in old.get('steps',[])]}]
            if progress:progress('START '+tid)
            if task['task_type']=='literature_driven':
                research=task.get('research_evidence') or {}
                result['ads_research_bibcodes']=research.get('bibcodes',[])
                result['literature_plan_draft']=_literature_draft(task)
                if not steps:result['status']='needs_independent_archive_query_plan'
            else:result['status']='incomplete'
            # Reuse complete earlier steps only when module, function, and
            # expected field sequence agree. Incomplete steps are retried alone.
            previous_steps=old.get('steps',[]) if old else []
            previous_values=old.get('answer_evidence',[]) if old else []
            for step in steps:
                args,fields=_check_step(step);module=step['module']
                entry={'module':module,'function':args['function_name'],'expected_columns':fields}
                cached=next((e for e in previous_steps if e.get('module')==module and
                    e.get('function')==args['function_name'] and e.get('expected_columns')==fields and
                    e.get('status')=='complete'),None)
                prior=[v for v in previous_values if str(v.get('field','')).startswith(module+':')]
                if cached and prior:
                    entry=dict(cached);entry['reused_prior_evidence']=True
                    result['answer_evidence'].extend(prior)
                else:
                    evidence=None;reason='no_response'
                    for attempt in range(1,attempts+1):
                        try:
                            payload=await client.call('astroquery_execute',args)
                            evidence,reason=_extract(payload,fields,module)
                            entry['response_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
                            if evidence is None:entry['response_diagnostics']=_payload_diagnostics(payload)
                            if evidence is not None:break
                        except Exception as exc:
                            reason=type(exc).__name__
                    entry['status']='complete' if evidence is not None else reason
                    entry['attempts']=attempt
                    if evidence is not None:result['answer_evidence'].extend(evidence)
                result['steps'].append(entry)
                if entry['status']!='complete':result['status']='incomplete_step_evidence'
            if steps and len(result['steps'])==len(steps) and all(x['status']=='complete' for x in result['steps']):
                # ADS candidate papers alone do not certify a paper--ObsID link.
                result['status']='complete' if task['task_type']=='multi_archive' else 'literature_association_not_verified'
            saved[tid]=result
            _atomic_jsonl(journal,[saved[t['id']] for t in tasks if t['id'] in saved])
            if progress:progress('DONE '+tid+' '+result['status'])
    if len(saved)==len(tasks):_atomic_jsonl(output,[saved[t['id']] for t in tasks])
    statuses=Counter(r['status'] for r in saved.values())
    report={'milestone':'0.6.7.11.12 - MULTISTEP_REFERENCE_AND_SCORING_CLOSURE',
            'status':'COMPLETE' if len(saved)==len(tasks) else 'PARTIAL',
            'dataset_sha256':digest,'tasks_total':len(tasks),'tasks_recorded':len(saved),
            'reference_complete':statuses.get('complete',0),'dispositions':dict(statuses),
            'retry_selection':selection['selected_task_ids'] if retry_incomplete else None,
            'preretry_snapshot':str(backup) if backup.exists() else None,
            'journal':str(journal),'output':str(output) if output.exists() else None,
            'note':'Only complete, independently retrieved step evidence is scorable; paper association remains unverified without explicit evidence.'}
    return report
