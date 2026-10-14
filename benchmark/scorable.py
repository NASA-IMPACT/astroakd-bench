"""Derive narrowly scorable questions from recorded Astroquery archive rows.

These are snapshot-reference keys, NOT independently reviewed scientific gold.
Question construction is deterministic and NEVER uses agent outputs as evidence.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any
import hashlib
import json
import math

from . import __version__
from .gold import _path_safety, _read_tasks
from .validator import ValidationError, load_jsonl, atomic_jsonl, atomic_json
from .exports import atomic_csv, json_compact
from .three_arm import ARMS, _score_one
from .scorable_diagnostics import export_detailed, plot_paths

MILESTONE = '0.6.7 - REFERENCE_ANCHORED_SCORABLE_QUERIES'
ARM_LABELS = {'mcp_only':'A - MCP only','mcp_instruction':'B - MCP + Instruction','web_only':'C - Web only'}


def _data_tables(rec):
    response=rec.get('response') or {}
    result=response.get('result')
    return [t for t in (result if isinstance(result,list) else [result]) if isinstance(t,dict) and isinstance(t.get('data'),list)]


def _choose(rec,source,variant):
    module=source.get('module')
    calls=source.get('reference_call',{}).get('arguments',{})
    params=calls.get('params',{})
    tables=_data_tables(rec)
    if not tables: raise ValidationError('No table for '+source['id'])
    cols={'simbad': [('ra','deg',0.001),('dec','deg',0.001),('coo_bibcode',None,None)],
          'mast':[('instrument_name',None,None),('t_exptime','s',1.0),('obs_collection',None,None),('dataproduct_type',None,None),('filters',None,None)],
          'heasarc':[('detector',None,None),('exposure','s',1.0),('status',None,None),('duration','s',1.0),('grating',None,None)],
          'gaia':[('phot_g_mean_mag','mag',0.05),('ra','deg',0.001),('dec','deg',0.001)],
          'vizier':[('Gmag','mag',0.05),('Jmag','mag',0.05),('Plx','mas',0.1),('RAJ2000','deg',0.001),('RA_ICRS','deg',0.001),('Kmag','mag',0.05)]}
    if module not in cols: raise ValidationError('Unsupported reference module '+str(module))
    for tidx,table in enumerate(tables):
        rows=table.get('data',[])
        for key_col in ((None,) if module=='simbad' else {'mast':('obsid',),'heasarc':('obsid',), 'gaia':('source_id',),'vizier':('Source','2MASS')}[module]):
            for ridx,row in enumerate(rows):
                if not isinstance(row,dict): continue
                ident=row.get(key_col) if key_col else source['target']
                if ident is None or str(ident).strip()=='':continue
                # All matching records in the returned data must agree on the target field.
                matches=[r for tab in tables for r in tab.get('data',[]) if isinstance(r,dict) and (key_col is None or str(r.get(key_col))==str(ident))]
                choices=cols[module]
                offset=(int(source['id'][-5:])+variant-1)%len(choices)
                preferred=choices[offset:]+choices[:offset]
                primary_field=_choose(rec,source,0)[4] if variant else None
                for field,unit,tol in preferred:
                    v=row.get(field)
                    if v is None or v=='' or isinstance(v,bool):continue
                    if not isinstance(v,(int,float,str)):continue
                    if isinstance(v,float) and not math.isfinite(v):continue
                    if len({str(m.get(field)) for m in matches if m.get(field) is not None})!=1:continue
                    if variant and field==primary_field:continue
                    return tidx,ridx,key_col,str(ident),field,v,unit,tol,params
    raise ValidationError('No unambiguous nonnull answer field for '+source['id']+' variant '+str(variant))


def _describe(source, key, ident, params):
    mod=source['module'];target=source['target']
    if mod=='simbad':return 'the object '+target
    region=params.get('coordinates') or params.get('coordinate') or params.get('position')
    radius=params.get('radius',{})
    if not isinstance(region,dict):raise ValidationError('Region not explicit for '+source['id'])
    loc=f"ICRS RA {region['ra']} deg, Dec {region['dec']} deg within {radius.get('value')} {radius.get('unit')}"
    if mod=='mast':return f'MAST observation obsid {ident} in the region {loc}'
    if mod=='heasarc':return f"HEASARC catalog {params.get('catalog')} observation obsid {ident} in the region {loc}"
    if mod=='gaia':return f'Gaia DR3 source_id {ident} in the region {loc}'
    if mod=='vizier':return f"VizieR catalog {params.get('catalog')} source identifier {key}={ident} in the region {loc}"
    raise AssertionError(mod)


def _question(source,key,ident,field,unit,params):
    area=_describe(source,key,ident,params)
    suffix=f' in {unit}' if unit else ''
    return f"Using {source['module'].upper()} archive records, what is the value of {field}{suffix} for {area}? Return only this one value in answer_values (JSON array); include the unit and source in your response."


def build_scorable(source_tasks:Path,references:Path,tasks_out:Path,oracle_out:Path,csv_out:Path,report_out:Path,*,count:int=50,replace:bool=False):
    if not 1<=count<=200:raise ValidationError('count must be 1..200')
    _path_safety([source_tasks,references],[tasks_out,oracle_out,csv_out,report_out],replace)
    tasks,sourcehash=_read_tasks(source_tasks)
    records,refhash=load_jsonl(references,max_bytes=512*1024*1024)
    seen={}; references_ok=[]
    for rec in records:
        tid=rec.get('task_id')
        if tid in seen or rec.get('input_dataset_sha256')!=sourcehash or rec.get('disposition')!='accepted_nonempty':
            raise ValidationError('Reference hash/status mismatch: '+str(tid))
        seen[tid]=rec
    if set(seen)!={t['id'] for t in tasks}:raise ValidationError('Expected a completed one-to-one reference dataset')
    rows=[]; errors=[]
    for variant in (0,1):
        for t in tasks:
            if len(rows)>=count:break
            rec=seen[t['id']]
            try: info=_choose(rec,t,variant)
            except ValidationError as e:
                errors.append(str(e));continue
            tidx,ridx,key,ident,field,value,unit,tol,params=info
            question=_question(t,key,ident,field,unit,params)
            if any(prev['question']==question for prev,_,_ in rows):continue
            ident_new=f"ASTROAKD-SCORE-{len(rows)+1:05d}"
            kinds='numeric' if type(value) in (int,float) else 'text'
            gold={'kind':kinds,'values':[float(value) if kinds=='numeric' else str(value)]}
            if kinds=='numeric':gold.update({'unit':unit,'absolute_tolerance':tol})
            row={'id':ident_new,'question':question,'task_type':t.get('task_type','archive_driven'),
                 'module':t['module'],'target':t['target'],'intent':f'single_value_{field}',
                 'constraints':t.get('constraints'), 'reference_call':t['reference_call'],
                 'answer_spec':{'answer_type':'scalar','field':field,'unit':unit,'format':'answer_values array containing one value',
                                'expected_answer_status':'reference_anchored_not_independent_gold'},
                 'provenance':{'source_task_id':t['id'],'source_reference_dataset_sha256':refhash,
                               'source_reference_record_sha256':hashlib.sha256(json.dumps(rec,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
                               'table_index':tidx,'row_index':ridx,'row_key_field':key,'row_key_value':ident,'source_field':field}}
            if rows and ident_new==rows[-1][0]['id']:raise AssertionError('Duplicate')
            rows.append((row,gold,(rec,tidx,ridx)))
        if len(rows)>=count:break
    if len(rows)!=count: raise ValidationError(f'Only {len(rows)} unambiguous field-level questions from source evidence; need {count}. Sample errors: '+str(errors[:4]))
    atomic_jsonl(tasks_out,[t for t,_,_ in rows],replace=replace)
    _,taskhash=_read_tasks(tasks_out)
    oracle=[]; summary=[]
    for t,g,(rec,tidx,ridx) in rows:
        o={'task_id':t['id'],'question':t['question'],'input_dataset_sha256':taskhash,
           'oracle_status':'reference_anchored_unreviewed','gold':g,'reference_provenance':t['provenance']}
        oracle.append(o)
        summary.append({'task_id':t['id'],'archive':t['module'],'source_task_id':t['provenance']['source_task_id'],
                        'question':t['question'],'answer_kind':g['kind'],'reference_answer':str(g['values'][0]),
                        'unit':g.get('unit') or '', 'absolute_tolerance':g.get('absolute_tolerance') or '',
                        'reference_status':'reference_anchored_unreviewed','reviewer_status':'PENDING'})
    atomic_jsonl(oracle_out,oracle,replace=replace)
    atomic_csv(csv_out,summary,tuple(summary[0]),replace=replace)
    report={'milestone':MILESTONE,'benchmark_version':__version__,'status':'REFERENCE_ANCHORED_UNREVIEWED',
            'count':len(rows),'source_reference_count':len(records),'by_archive':dict(Counter(t['module'] for t,_,_ in rows)),
            'tasks_sha256':taskhash,'reference_sha256':refhash,'source_tasks_sha256':sourcehash,
            'independently_verified_gold':0,'reference_anchored_answer_keys':len(oracle),
            'model_for_agent_experiment':'gpt-5.2','limitations':['Snapshot answers reflect recorded MCP table values; not independently verified scientific truth.',
              'Only one-field single-source questions; literature-driven multistep tasks require their own separately verified oracle.',
              'Results from live archives may evolve; preserve archive snapshot and source hashes.'],
            'tasks_output':str(tasks_out),'oracle_output':str(oracle_out),'csv_output':str(csv_out)}
    atomic_json(report_out,report,replace=replace,style='pretty')
    return report


def _normalize_equivalent_unit(answer:dict,gold:dict)->dict:
    """Accept harmless unit spelling variants; never convert units without evidence."""
    if gold.get('kind')!='numeric' or not isinstance(answer,dict):return answer
    synonyms={
        'deg': {'degree','degrees','deg','°'},
        'mag': {'mag','magnitude','magnitudes'},
        'mas': {'mas','milliarcsecond','milliarcseconds'},
        's': {'s','sec','secs','second','seconds'},
    }
    expected=gold.get('unit')
    observed=str(answer.get('unit') or '').strip().lower()
    if expected in synonyms and observed in synonyms[expected]:
        return {**answer,'unit':expected}
    return answer


def score_scorable(tasks_path:Path,oracle_path:Path,runs_path:Path,comparison_csv:Path,summary_csv:Path,report_out:Path,*,
                   detail_csv:Path|None=None,performance_csv:Path|None=None,
                   task_performance_csv:Path|None=None, plots_dir:Path|None=None,
                   mcp_calls_csv:Path|None=None,mcp_tool_frequency_csv:Path|None=None,replace:bool=False):
    # Preflight every destination before writing a single output.
    plot_outputs=plot_paths(plots_dir) if plots_dir is not None else []
    _path_safety([tasks_path,oracle_path,runs_path],
                 [comparison_csv,summary_csv,report_out,detail_csv,performance_csv,task_performance_csv,
                  mcp_calls_csv,mcp_tool_frequency_csv,*plot_outputs],replace)
    tasks,digest=_read_tasks(tasks_path)
    oracle,hashoracle=load_jsonl(oracle_path)
    runs,hashruns=load_jsonl(runs_path,max_bytes=512*1024*1024)
    if [x.get('task_id') for x in oracle]!=[t['id'] for t in tasks]:raise ValidationError('Oracle task order mismatch')
    if any(o.get('input_dataset_sha256')!=digest or o.get('question')!=t['question'] or o.get('oracle_status')!='reference_anchored_unreviewed' for o,t in zip(oracle,tasks)):
        raise ValidationError('Oracle source digest/question/status mismatch')
    mapping={}; taskids={t['id'] for t in tasks}
    for r in runs:
        key=(r.get('task_id'),r.get('arm'))
        if key[0] not in taskids or key[1] not in ARMS or key in mapping or r.get('candidate_sha256')!=digest:
            raise ValidationError('Mismatched/duplicate model run')
        if r.get('model')!='gpt-5.2':raise ValidationError('Expected all arms to use gpt-5.2; refuse model-mixed scores')
        trace=r.get('trace',[])
        if not isinstance(trace,list) or (key[1]=='web_only' and any(x.get('tool')!='openai_web_search' for x in trace)) or (key[1]!='web_only' and any(x.get('tool')=='openai_web_search' for x in trace)):
            raise ValidationError('Tool-arm separation violated')
        mapping[key]=r
    comparisons=[]
    for task,oracle_record in zip(tasks,oracle):
        out={'task_id':task['id'],'task_type':task['task_type'],'archive':task['module'],'question':task['question'],
             'reference_answer':str(oracle_record['gold']['values'][0]),'answer_kind':oracle_record['gold']['kind'],
             'unit':oracle_record['gold'].get('unit') or '', 'tolerance':oracle_record['gold'].get('absolute_tolerance') or '',
             'reference_status':oracle_record['oracle_status']}
        for a,prefix in zip(ARMS,('A','B','C')):
            record=mapping.get((task['id'],a))
            ans=(record or {}).get('answer') or {}
            if record is None: st='NOT_RUN'
            elif record.get('status')!='completed':st='RUN_ERROR'
            else:
                st,_=_score_one(oracle_record['gold'],_normalize_equivalent_unit(ans,oracle_record['gold']))
                if st in ('REVIEW_UNSTRUCTURED','REVIEW_DUPLICATE_VALUES'):st='INCORRECT_FORMAT'
            out.update({prefix+'_status':st,prefix+'_correct':st=='CORRECT' if record is not None else '',
                        prefix+'_answer':ans.get('answer',''),
                        prefix+'_answer_values':json_compact(ans.get('answer_values')) if ans.get('answer_values') is not None else '',
                        prefix+'_sources':json_compact(ans.get('sources') or []),
                        prefix+'_run_status':record.get('status') if record else 'not_run',
                        prefix+'_duration_seconds':record.get('duration_seconds') if record else ''})
        comparisons.append(out)
    summaries=[]
    for arm,prefix in zip(ARMS,('A','B','C')):
        attempted=[x for x in comparisons if x[prefix+'_status']!='NOT_RUN']
        correct=sum(x[prefix+'_status']=='CORRECT' for x in attempted)
        scored=len(attempted)
        summaries.append({'arm':arm,'arm_label':ARM_LABELS[arm],'model':'gpt-5.2',
                          'total_questions':len(tasks),'attempted':scored,'correct':correct,
                          'reference_match_pct_attempted':round(100*correct/scored,2) if scored else '',
                          'reference_match_pct_all_questions':round(100*correct/len(tasks),2),
                          'unattempted':len(tasks)-scored,
                          'incorrect_format':sum(x[prefix+'_status']=='INCORRECT_FORMAT' for x in attempted),
                          'errors':sum(x[prefix+'_status']=='RUN_ERROR' for x in attempted),
                          'independently_verified_scientific_success_pct':'',
                          'answer_key_status':'reference_anchored_unreviewed'})
    diagnostics=export_detailed(comparisons,summaries,mapping,detail_csv=detail_csv,
        performance_csv=performance_csv,task_performance_csv=task_performance_csv,
        plots_dir=plots_dir,mcp_calls_csv=mcp_calls_csv,
        mcp_tool_frequency_csv=mcp_tool_frequency_csv,replace=replace)
    atomic_csv(comparison_csv,comparisons,tuple(comparisons[0]),replace=replace)
    atomic_csv(summary_csv,summaries,tuple(summaries[0]),replace=replace)
    report={'milestone':MILESTONE,'benchmark_version':__version__,'status':'PASS' if len(mapping)==len(tasks)*3 else 'PARTIAL',
            'tasks':len(tasks),'runs_recorded':len(mapping),'model':'gpt-5.2','dataset_sha256':digest,
            'oracle_sha256':hashoracle,'runs_sha256':hashruns,'arms':{s['arm']:s for s in summaries},
            'note':'Reference-snapshot exact-match percentages, not independently verified scientific accuracy. All answers, including wrong/free-form/error replies, retained in CSV.',
            'comparison_csv':str(comparison_csv),'summary_csv':str(summary_csv),
            **diagnostics}
    atomic_json(report_out,report,replace=replace,style='pretty')
    return report
