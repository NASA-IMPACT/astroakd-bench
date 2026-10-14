"""Human-readable 50-question/three-arm CSV review with explicit evidence status.

A successful tool call or a completed language-model run is NOT a scientifically
correct answer.  Independent gold is required to compute science success rates.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import json
from typing import Any

from . import __version__
from .exports import atomic_csv, json_compact
from .gold import _path_safety, _read_tasks
from .three_arm import ARMS, _score_one
from .validator import ValidationError, atomic_json, load_jsonl

MILESTONE = '0.6.6.1 - ANSWER_INSPECTION_AND_SUCCESS_RATE_CSV'
ARM_LABELS = {'mcp_only':'A - MCP only', 'mcp_instruction':'B - MCP + AstroAKD Instruction', 'web_only':'C - Web search only'}

QUESTION_COLUMNS = (
    'task_id','task_type','archive','target','intent','question','expected_columns',
    'reference_status','reference_returned_rows','reference_total_rows','reference_truncated',
    'reference_candidate_values_json','reference_candidate_value_count','reference_answer_status',
    'gold_status','verified_gold_values_json','gold_sources',
    'A_answer','A_answer_values_json','A_run_status','A_scientific_status','A_scientific_success',
    'B_answer','B_answer_values_json','B_run_status','B_scientific_status','B_scientific_success',
    'C_answer','C_answer_values_json','C_run_status','C_scientific_status','C_scientific_success',
    'review_notes'
)
ARM_COLUMNS = (
    'task_id','task_type','archive','question','arm','arm_label','was_run','run_status','operational_success',
    'answer','answer_values_json','answer_format','abstained','sources_json','duration_seconds',
    'input_tokens','output_tokens','total_tokens','successful_mcp_queries','web_search_calls',
    'error','gold_status','scientific_status','scientific_fraction','scientific_success','scientific_review_notes'
)
SUMMARY_COLUMNS = (
    'arm','arm_label','total_questions','runs_attempted','runs_completed','run_errors','questions_not_run',
    'completion_rate_attempted_pct','coverage_all_questions_pct',
    'structured_answers','structured_answer_rate_completed_pct',
    'nonempty_answers','nonempty_answer_rate_completed_pct','mcp_queries_succeeded',
    'web_search_calls','verified_gold_tasks','scientifically_scored','scientifically_correct',
    'scientific_success_rate_pct','mean_scientific_fraction','assessment'
)
VALUE_COLUMNS = ('task_id','archive','target','question','expected_field','table_index','row_index',
                 'observed_value','reference_truncated','value_status')


def _score_str(value: Any) -> str:
    return '' if value is None else str(value)


def _load_runs(path: Path|None, dataset_hash: str, ids: set[str]) -> tuple[dict[tuple[str,str],dict],str|None]:
    if path is None: return {}, None
    records, sha = load_jsonl(path, max_bytes=512*1024*1024)
    output = {}
    for rec in records:
        key = (rec.get('task_id'), rec.get('arm'))
        if key[0] not in ids or key[1] not in ARMS or key in output or rec.get('candidate_sha256') != dataset_hash:
            raise ValidationError('Three-arm runs do not match the candidate dataset or contain duplicate IDs')
        if not isinstance(rec.get('answer'),dict) or not isinstance(rec.get('trace',[]),list):
            raise ValidationError('Malformed run record')
        if key[1] == 'web_only' and any(ev.get('tool') != 'openai_web_search' for ev in rec['trace']):
            raise ValidationError('Web arm contains non-web tools')
        if key[1] != 'web_only' and any(ev.get('tool') == 'openai_web_search' for ev in rec['trace']):
            raise ValidationError('MCP arm contains web search')
        output[key] = rec
    return output, sha


def _load_references(path: Path|None, reference_tasks: Path|None, ids: set[str]) -> tuple[dict[str,dict],str|None]:
    if path is None: return {},None
    if reference_tasks is None:
        raise ValidationError('--reference-tasks required when --references is provided')
    subset, subset_sha = _read_tasks(reference_tasks)
    subsetids={t['id'] for t in subset}
    if not subsetids.issubset(ids):
        raise ValidationError('Reference task IDs are not a subset of mixed task IDs')
    records, sha=load_jsonl(path,max_bytes=512*1024*1024)
    output={}
    for rec in records:
        ident=rec.get('task_id')
        if ident not in subsetids or ident in output or rec.get('input_dataset_sha256')!=subset_sha:
            raise ValidationError('Reference dataset/hash/IDs invalid or duplicated')
        output[ident]=rec
    return output,sha


def _load_gold(path:Path|None, tasks:list[dict], digest:str) -> tuple[dict[str,dict],str|None]:
    if path is None: return {},None
    rows, sha=load_jsonl(path,max_bytes=20*1024*1024)
    if [g.get('task_id') for g in rows]!=[t['id'] for t in tasks]:
        raise ValidationError('Gold rows do not match task order')
    if any(g.get('input_dataset_sha256')!=digest or g.get('question')!=t.get('question') for g,t in zip(rows,tasks)):
        raise ValidationError('Gold source question/hash mismatch')
    for g in rows:
        if g.get('gold_status')=='verified':
            sources=g.get('sources') or []
            hosts={urlparse(s.get('uri','')).netloc.casefold() for s in sources if isinstance(s,dict)}
            if (not isinstance(g.get('gold'),dict) or g.get('question_review')!='approved'
                or not g.get('reviewer') or len(hosts)<2 or '' in hosts):
                raise ValidationError('Verified gold must be reviewed with two independent citation hosts')
    return {g['task_id']:g for g in rows},sha


def _tables(response:Any) -> list[dict]:
    result = response.get('result') if isinstance(response,dict) else None
    if isinstance(result,dict): return [result]
    if isinstance(result,list): return [tab for tab in result if isinstance(tab,dict)]
    return []


def _reference_values(task:dict,rec:dict|None) -> tuple[list[dict],list[Any],str]:
    if not rec: return [],[], 'no_reference_data'
    fields=task.get('answer_spec',{}).get('expected_columns') or []
    if not fields: return [],[], 'no_expected_field_multistep'
    values=[]; details=[]; fields_seen=set()
    for index, tab in enumerate(_tables(rec.get('response'))):
        names={str(c.get('name')) for c in tab.get('columns',[]) if isinstance(c,dict)}
        for field in fields:
            exact=field if field in names else None
            if exact is None:
                matches=[n for n in names if n.casefold()==str(field).casefold()]
                exact=matches[0] if len(matches)==1 else None
            if exact is None: continue
            fields_seen.add(field)
            for row_index,row in enumerate(tab.get('data') or []):
                if not isinstance(row,dict): continue
                value=row.get(exact)
                if value is None or value == '': continue
                details.append({'task_id':task['id'],'archive':task.get('module'),
                                'target':task.get('target'),'question':task.get('question'),
                                'expected_field':field,'table_index':index,'row_index':row_index,
                                'observed_value':json_compact(value) if isinstance(value,(dict,list)) else _score_str(value),
                                'reference_truncated':(rec.get('evaluation') or {}).get('checks',{}).get('truncated'),
                                'value_status':'unverified_reference_observation_not_gold'})
                values.append({'field':field,'value':value,'table':index,'row':row_index})
    if set(fields)-fields_seen: return details,values,'expected_fields_missing_from_reference'
    if not values: return details,values,'expected_fields_present_but_no_nonnull_values'
    if (rec.get('evaluation') or {}).get('checks',{}).get('truncated') is True:
        return details,values,'partial_truncated_reference_not_gold'
    return details,values,'reference_values_unverified_not_gold'


def _scientific_status(gold:dict|None,run:dict|None) -> tuple[str, float|None, str]:
    if not gold or gold.get('gold_status')!='verified': return 'UNSCORABLE_NO_APPROVED_GOLD',None,''
    if not run: return 'NOT_RUN',None,''
    if run.get('status')!='completed': return 'RUN_ERROR',None,''
    status, fraction=_score_one(gold['gold'],run.get('answer') or {})
    return status,fraction, ('yes' if status=='CORRECT' else 'no' if fraction is not None else '')


def export_answer_csv(tasks_path:Path,questions_csv:Path,arms_csv:Path,summary_csv:Path,report_path:Path,
                      *,runs:Path|None=None,references:Path|None=None,reference_tasks:Path|None=None,
                      gold:Path|None=None,reference_values_csv:Path|None=None,per_arm_dir:Path|None=None,replace:bool=False) -> dict[str,Any]:
    """Export observed source values, actual agent replies, and separately qualified rates.

    Incomplete three-arm pilot journals are accepted, but all unrun cells stay blank.
    """
    per_arm_paths={arm:per_arm_dir / filename for arm,filename in (
        ('mcp_only','A_mcp_only_answers.csv'),
        ('mcp_instruction','B_mcp_instruction_answers.csv'),
        ('web_only','C_web_only_answers.csv'))} if per_arm_dir is not None else {}
    outputs=[questions_csv,arms_csv,summary_csv,report_path]+([reference_values_csv] if reference_values_csv else [])+list(per_arm_paths.values())
    for p in (questions_csv,arms_csv,summary_csv,reference_values_csv):
        if p is not None and p.suffix.lower()!='.csv': raise ValidationError('CSV outputs must end in .csv')
    _path_safety([tasks_path,runs,references,reference_tasks,gold],outputs,replace)
    tasks, digest=_read_tasks(tasks_path); ids={t['id'] for t in tasks}
    refmap,refsha=_load_references(references,reference_tasks,ids)
    runmap,runsha=_load_runs(runs,digest,ids)
    goldmap,goldsha=_load_gold(gold,tasks,digest)
    questions=[]; armrows=[]; values=[]
    for t in tasks:
        ident=t['id']; rec=refmap.get(ident); g=goldmap.get(ident)
        checks=(rec or {}).get('evaluation',{}).get('checks',{})
        detail, candidate_values,candidate_status=_reference_values(t,rec)
        values.extend(detail)
        gstatus=(g or {}).get('gold_status','not_provided')
        frozen_values=(g or {}).get('gold') if gstatus=='verified' else None
        row={'task_id':ident,'task_type':t.get('task_type',''),'archive':t.get('module',''),
             'target':t.get('target',''),'intent':t.get('intent',''),'question':t.get('question',''),
             'expected_columns':'; '.join(t.get('answer_spec',{}).get('expected_columns') or []),
             'reference_status':(rec or {}).get('disposition','not_collected'),
             'reference_returned_rows':checks.get('returned_rows'), 'reference_total_rows':checks.get('reported_total_rows'),
             'reference_truncated':checks.get('truncated'),
             'reference_candidate_values_json':json_compact(candidate_values),
             'reference_candidate_value_count':len(candidate_values),'reference_answer_status':candidate_status,
             'gold_status':gstatus, 'verified_gold_values_json':json_compact(frozen_values) if frozen_values else '',
             'gold_sources':json_compact((g or {}).get('sources',[])) if frozen_values else '',
             'review_notes':(g or {}).get('review_notes','')}
        for arm,prefix in zip(ARMS,('A','B','C')):
            run=runmap.get((ident,arm)); ans=run.get('answer') if run else {}
            sc_status, fraction,success=_scientific_status(g,run)
            row.update({f'{prefix}_answer':ans.get('answer',''),
                        f'{prefix}_answer_values_json':json_compact(ans['answer_values']) if ans.get('answer_values') is not None else '',
                        f'{prefix}_run_status':run.get('status','not_run') if run else 'not_run',
                        f'{prefix}_scientific_status':sc_status,
                        f'{prefix}_scientific_success':success})
            usage=run.get('token_usage') if run else {}
            trace=run.get('trace',[]) if run else []
            armrows.append({'task_id':ident,'task_type':t.get('task_type',''),'archive':t.get('module',''),
                'question':t.get('question',''),'arm':arm,'arm_label':ARM_LABELS[arm],
                'was_run':run is not None,'run_status':run.get('status') if run else 'not_run',
                'operational_success':(run.get('status')=='completed') if run else '',
                'answer':ans.get('answer',''),
                'answer_values_json':json_compact(ans['answer_values']) if ans.get('answer_values') is not None else '',
                'answer_format':ans.get('parse_status',''),
                'abstained':ans.get('abstained','') if run else '',
                'sources_json':json_compact(ans.get('sources',[])) if run else '',
                'duration_seconds':run.get('duration_seconds') if run else '',
                'input_tokens':usage.get('input_tokens',''), 'output_tokens':usage.get('output_tokens',''),
                'total_tokens':usage.get('total_tokens',''),
                'successful_mcp_queries':run.get('successful_mcp_queries',0) if run else '',
                'web_search_calls':sum(int(e.get('web_search_calls',0) or 0) for e in trace if e.get('tool')=='openai_web_search') if run else '',
                'error':json_compact(run['error']) if run and run.get('error') else '',
                'gold_status':gstatus,'scientific_status':sc_status,'scientific_fraction':fraction if fraction is not None else '',
                'scientific_success':success,'scientific_review_notes':'Requires independently verified gold answer' if not frozen_values else ''})
        questions.append(row)
    summary=[]
    for arm in ARMS:
        rs=[r for r in armrows if r['arm']==arm]
        attempted=[r for r in rs if r['was_run']]
        complete=[r for r in attempted if r['run_status']=='completed']
        structured=sum(r['answer_format']=='structured' for r in complete)
        nonempty=sum(bool(str(r['answer']).strip()) for r in complete)
        graded=[r for r in rs if r['scientific_fraction']!='']
        success=sum(r['scientific_success']=='yes' for r in graded)
        verified=sum((goldmap.get(t['id']) or {}).get('gold_status')=='verified' for t in tasks)
        def pct(n,d): return round(100*n/d,2) if d else None
        summary.append({'arm':arm,'arm_label':ARM_LABELS[arm],'total_questions':len(tasks),
                        'runs_attempted':len(attempted),'runs_completed':len(complete),
                        'run_errors':len(attempted)-len(complete),'questions_not_run':len(tasks)-len(attempted),
                        'completion_rate_attempted_pct':pct(len(complete),len(attempted)),
                        'coverage_all_questions_pct':pct(len(complete),len(tasks)),
                        'structured_answers':structured,'structured_answer_rate_completed_pct':pct(structured,len(complete)),
                        'nonempty_answers':nonempty,'nonempty_answer_rate_completed_pct':pct(nonempty,len(complete)),
                        'mcp_queries_succeeded':sum(int(r['successful_mcp_queries'] or 0) for r in attempted),
                        'web_search_calls':sum(int(r['web_search_calls'] or 0) for r in attempted),
                        'verified_gold_tasks':verified,'scientifically_scored':len(graded),
                        'scientifically_correct':success,
                        'scientific_success_rate_pct':pct(success,len(graded)),
                        'mean_scientific_fraction':round(sum(float(r['scientific_fraction']) for r in graded)/len(graded),5) if graded else None,
                        'assessment':'Scientific success unavailable until independently approved gold answers exist' if not graded else 'Scores available for gold-scored subset only'})
    atomic_csv(questions_csv,questions,QUESTION_COLUMNS,replace=replace)
    atomic_csv(arms_csv,armrows,ARM_COLUMNS,replace=replace)
    atomic_csv(summary_csv,summary,SUMMARY_COLUMNS,replace=replace)
    if reference_values_csv is not None:
        atomic_csv(reference_values_csv,values,VALUE_COLUMNS,replace=replace)
    for arm,path in per_arm_paths.items():
        atomic_csv(path,[r for r in armrows if r['arm']==arm],ARM_COLUMNS,replace=replace)
    result={'milestone':MILESTONE,'benchmark_version':__version__,'status':'PASS',
            'tasks':len(tasks),'reference_records':len(refmap),'three_arm_runs':len(runmap),
            'reference_observed_values':len(values),'verified_gold_answers':sum((g.get('gold_status')=='verified') for g in goldmap.values()),
            'dataset_sha256':digest,'references_sha256':refsha,'runs_sha256':runsha,'gold_sha256':goldsha,
            'arms':{r['arm']:r for r in summary},
            'questions_csv':str(questions_csv),'arms_csv':str(arms_csv),'summary_csv':str(summary_csv),
            'reference_values_csv':str(reference_values_csv) if reference_values_csv else None,
            'per_arm_csv':{arm:str(path) for arm,path in per_arm_paths.items()},
            'note':'CSV reference values are archive evidence NOT independently verified gold. Operational completion percentages are NOT scientific success rates. Missing science gold yields null percentage.'}
    atomic_json(report_path,result,replace=replace,style='pretty')
    return result
