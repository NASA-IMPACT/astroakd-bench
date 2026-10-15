"""0.6.7.11 convenience API: named datasets, not a separate science engine.

No model-generated answer is a gold reference. Multi-step candidates are
excluded from the independent single-call reference validator.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median, mean
from typing import Any

from . import __version__
from .generator import GenerationError, parse_modules, write_jsonl
from .mixed_generation import generate_mixed, parse_task_mix
from .exports import save_views
from .validator import load_jsonl, validate
from .reference_review import review_detail


def dataset_paths(root: str | Path = '.', name: str = 'synthetic_100',
                  output_dir: str | Path | None = None) -> dict[str, Path]:
    if not name or len(name) > 80 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in name):
        raise ValueError('Dataset name must use only ASCII letters, digits, _ or -')
    root = Path(root)
    data = (root / 'datasets') if output_dir is None else (root / Path(output_dir).expanduser())
    return {
        'tasks': data / 'generated' / (name + '.jsonl'),
        'tasks_csv': data / 'generated' / (name + '.csv'),
        'generation_report': data / 'generated' / (name + '_generation_report.json'),
        'single_calls': data / 'generated' / (name + '_single_call.jsonl'),
        'multistep': data / 'generated' / (name + '_multistep.jsonl'),
        'references': data / 'validated' / (name + '_references.jsonl'),
        'references_csv': data / 'validated' / (name + '_references.csv'),
        'references_report': data / 'validated' / (name + '_references_report.json'),
        'runs': data / 'agent' / (name + '_ABC_runs.jsonl'),
        'run_report': data / 'agent' / (name + '_ABC_report.json'),
        'plots': data / 'reports' / name,
    }


def _save_json(path: Path, obj: dict[str,Any], *, replace: bool = False) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f'{path} already exists; use --replace')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


async def create_queries(*, name: str | None = None, root: str | Path = '.',
                         output_dir: str | Path | None = None,
                         count: int = 100, seed: int = 20261018, model: str = 'gpt-5.2',
                         mix: str = 'balanced100', modules: str = 'simbad,mast,heasarc,gaia,vizier',
                         batch_size: int = 5, url: str | None = None, timeout: float = 180,
                         require_ads: bool = False, replace: bool = False,
                         progress=None, research_fn=None, llm_fn=None, openai_client_factory=None) -> dict[str,Any]:
    name = name if name is not None else f'synthetic_{count}'
    paths = dataset_paths(root, name, output_dir=output_dir)
    if any(paths[k].exists() for k in ('tasks','tasks_csv','generation_report','single_calls','multistep')) and not replace:
        raise FileExistsError('Named dataset exists; choose another --name to preserve experiments')
    recipe = parse_task_mix(mix, count=count)
    if recipe is None:
        raise ValueError('A mixed task recipe is required')
    tasks, report = await generate_mixed(url, count=count, seed=seed, modules=parse_modules(modules),
        mix=recipe, backend='openai', model=model, batch_size=batch_size,
        timeout=timeout, use_mcp=True, use_instructions=True, require_ads=require_ads,
        progress=progress, research_fn=research_fn, llm_fn=llm_fn,
        openai_client_factory=openai_client_factory)
    regular = [t for t in tasks if t['task_type'] in ('archive_driven', 'coordinate_driven')]
    multi = [t for t in tasks if t['task_type'] in ('multi_archive', 'literature_driven')]
    # Publish only once each task family and every output destination has been checked.
    if len(tasks) != count or len(regular) != recipe['archive_driven']+recipe['coordinate_driven']:
        raise GenerationError('Task family count mismatch')
    report['dataset_sha256'] = write_jsonl(paths['tasks'], tasks, replace=replace)
    report['single_call_sha256'] = write_jsonl(paths['single_calls'], regular, replace=replace)
    report['multistep_sha256'] = write_jsonl(paths['multistep'], multi, replace=replace)
    save_views(tasks, csv_path=paths['tasks_csv'], kind='candidate', replace=replace)
    report.update({'milestone': '0.6.7.11 - MIXED_100_SIMPLE_WORKFLOWS',
        'task_dataset': str(paths['tasks']), 'question_csv': str(paths['tasks_csv']),
        'single_call_dataset': str(paths['single_calls']),
        'multistep_dataset': str(paths['multistep']),
        'single_call_references_pending': len(regular),
        'multistep_reference_collection': 'NOT_PERFORMED_REQUIRES_SEPARATE_EVIDENCE',
        'verified_gold_answers': 0})
    _save_json(paths['generation_report'], report, replace=replace)
    return report


async def collect_references(*, name: str = 'synthetic_100', root: str | Path = '.',
                             output_dir: str | Path | None = None,
                             url: str | None = None, limit: int | None = None, resume: bool = False,
                             replace: bool = False, timeout: float = 90.,
                             archive_timeouts: str = 'mast=60,simbad=30,heasarc=60,gaia=60,vizier=45',
                             archive_attempts: str = 'mast=1,simbad=1,heasarc=1,gaia=1,vizier=1',
                             reference_deadline: float = 70., progress=None) -> dict[str,Any]:
    p=dataset_paths(root,name,output_dir=output_dir)
    if not p['single_calls'].exists():
        raise FileNotFoundError(f'Single-call subset missing: {p["single_calls"]}')
    if resume and replace:
        raise ValueError('--resume and --replace are mutually exclusive')
    return await validate(p['single_calls'], p['references'], p['references_report'],
        url=url, timeout=timeout, attempts=1, delay=2, limit=limit,
        csv_output=p['references_csv'], resume=resume, replace=replace,
        archive_timeouts=archive_timeouts,archive_attempts=archive_attempts,
        reference_deadline=reference_deadline, progress=progress)


def _rows_csv(path: Path, rows: list[dict[str,Any]], cols: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def _bar(plt, data: Counter, path: Path, title: str, *, xlabel: str = 'Questions'):
    fig,ax=plt.subplots(figsize=(10, max(4,0.38*len(data)+1)))
    pairs=sorted(data.items(),key=lambda pair: pair[1])
    if pairs:
        ax.barh([str(k) for k,v in pairs],[v for k,v in pairs])
    ax.set_title(title);ax.set_xlabel(xlabel)
    fig.tight_layout(); fig.savefig(path.with_suffix('.png'),dpi=180); fig.savefig(path.with_suffix('.svg'));plt.close(fig)


def reference_report(*, name: str = 'synthetic_100', root: str | Path = '.',
                      output_dir: str | Path | None = None, plots: bool = True, replace: bool = False) -> dict[str,Any]:
    """Offline archive completeness/shape/time plots, including uncollected mixed tasks.

    Strongly binds each reference to the *single-call subset* hash, not the
    full mixed-task dataset hash. Refuses extraneous task IDs or stale evidence.
    """
    p=dataset_paths(root,name,output_dir=output_dir)
    tasks, full_sha=load_jsonl(p['tasks'],max_bytes=128*1024*1024)
    single, single_sha=load_jsonl(p['single_calls'],max_bytes=128*1024*1024)
    if len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Duplicate IDs in tasks')
    full_by_id={t['id']:t for t in tasks}
    singles={t['id']:t for t in single}
    if any(tid not in full_by_id or full_by_id[tid]!=task or
           task.get('task_type','archive_driven') not in ('archive_driven','coordinate_driven')
           for tid,task in singles.items()):
        raise ValueError('Single-call subset must match tasks in the full named dataset')
    refs=[]
    if p['references'].exists():
        refs,_=load_jsonl(p['references'],max_bytes=512*1024*1024)
    elif p['references'].with_name(p['references'].name+'.progress.jsonl').exists():
        refs,_=load_jsonl(p['references'].with_name(p['references'].name+'.progress.jsonl'),max_bytes=512*1024*1024)
    by_id={}
    for r in refs:
        tid=r.get('task_id')
        if tid in by_id or tid not in singles or r.get('input_dataset_sha256')!=single_sha or r.get('reference_call')!=singles[tid].get('reference_call'):
            raise ValueError(f'Invalid/stale/duplicated reference record: {tid}')
        by_id[tid]=r
    out=p['plots']/ 'references'
    names=('reference_summary.json','reference_questions.csv','reference_archives.csv',
           'questions_by_archive.png','questions_by_archive.svg','answer_shapes.png','answer_shapes.svg',
           'reference_dispositions.png','reference_dispositions.svg','review_flags.png','review_flags.svg',
           'response_times.png','response_times.svg','response_time_distribution.png','response_time_distribution.svg',
           'truncation_null_by_archive.png','truncation_null_by_archive.svg')
    requested=names if plots else names[:3]
    if any((out/n).exists() for n in requested) and not replace:
        raise FileExistsError('Reference report exists; add --replace (does not modify evidence)')
    if plots:
        try: from matplotlib import pyplot as plt
        except ImportError as exc: raise RuntimeError('Install plots: uv run --with matplotlib ...') from exc
    type_counts=Counter(t.get('task_type','unknown') for t in tasks)
    archives=Counter(t.get('module','unknown') for t in tasks)
    statuses=Counter(); shapes=Counter(); flags=Counter(); times=defaultdict(list)
    csv_rows=[]
    for task in tasks:
        ident=task['id']; r=by_id.get(ident)
        if ident not in singles:
            status='multistep_not_single_call_validated'; shape='multistep_unreviewed'; details={}
            rowflags=['multistep_reference_required']; duration=''
        elif r is None:
            status='not_collected'; shape='not_collected'; details={}
            rowflags=['missing_reference']; duration=''
        else:
            details=review_detail(task,r)
            status=r.get('disposition','unknown'); shape=details['answer_shape']
            rowflags=details['review_flags']
            elapsed=[a.get('elapsed_seconds') for a in r.get('attempts',[]) if isinstance(a.get('elapsed_seconds'),(int,float))]
            duration=sum(elapsed) if elapsed else ''
            if elapsed: times[task['module']].append(sum(elapsed))
        statuses[status]+=1;shapes[shape]+=1;flags.update(rowflags)
        csv_rows.append({'task_id':ident,'task_type':task.get('task_type'),
           'archive':task['module'],'target':task.get('target'),'question':task.get('question'),
           'reference_disposition':status,'answer_shape':shape,'review_flags':';'.join(rowflags),
           'runtime_seconds':duration,'returned_rows':details.get('checks',{}).get('returned_rows',''),
           'truncated':'incomplete_truncated_response' in rowflags,
           'null_measurements':'null_measurements' in rowflags,
           'scientific_gold_verified':False})
    archive_rows=[]
    for arch in sorted(archives):
        sub=[row for row in csv_rows if row['archive']==arch]
        archive_rows.append({'archive':arch,'tasks':len(sub),
           'nonempty':sum(r['reference_disposition']=='accepted_nonempty' for r in sub),
           'empty':sum(r['reference_disposition']=='accepted_empty' for r in sub),
           'failed':sum(r['reference_disposition'] in ('transport_error','error','rejected') for r in sub),
           'not_collected':sum(r['reference_disposition']=='not_collected' for r in sub),
           'multistep_pending':sum(r['reference_disposition']=='multistep_not_single_call_validated' for r in sub),
           'truncated':sum(r['truncated'] for r in sub),
           'null_measurement_tasks':sum(r['null_measurements'] for r in sub),
           'median_reference_seconds':round(median(times[arch]),3) if times[arch] else ''})
    report={'milestone':'0.6.7.11 - NATIVE_REFERENCE_REPORT','version':__version__,
        'dataset_sha256':full_sha,'single_call_sha256':single_sha,
        'total_questions':len(tasks),'single_call_tasks':len(single),
        'multistep_tasks':len(tasks)-len(single),'reference_records':len(refs),
        'task_type_counts':dict(type_counts),'reference_disposition_counts':dict(statuses),
        'answer_shape_counts':dict(shapes),'review_flag_counts':dict(flags),
        'gold_verified':0,'scientific_accuracy_ready':False,'status':'REVIEW',
        'note':'Archive responses are unreviewed; multistep questions require separate evidence.'}
    out.mkdir(parents=True,exist_ok=True)
    _rows_csv(out/'reference_questions.csv',csv_rows,list(csv_rows[0]))
    _rows_csv(out/'reference_archives.csv',archive_rows,list(archive_rows[0]))
    if plots:
        _bar(plt,archives,out/'questions_by_archive','Candidate questions by archive / task type')
        _bar(plt,shapes,out/'answer_shapes','Observed answer shapes (unreviewed)')
        _bar(plt,statuses,out/'reference_dispositions','Reference dispositions')
        _bar(plt,flags,out/'review_flags','Completeness and scientific review flags')
        fig,ax=plt.subplots(figsize=(10,5))
        ordered=[item['archive'] for item in archive_rows]
        xx=range(len(ordered))
        ax.bar([i-0.18 for i in xx],[item['truncated'] for item in archive_rows],width=0.36,label='Truncated')
        ax.bar([i+0.18 for i in xx],[item['null_measurement_tasks'] for item in archive_rows],width=0.36,label='Null values')
        ax.set_xticks(list(xx),ordered,rotation=20,ha='right')
        ax.set_ylabel('Reference questions');ax.set_title('Truncation and null measurements by archive')
        ax.legend();fig.tight_layout()
        fig.savefig(out/'truncation_null_by_archive.png',dpi=180)
        fig.savefig(out/'truncation_null_by_archive.svg');plt.close(fig)
        _bar(plt,Counter({a:round(median(v),2) for a,v in times.items()}),out/'response_times',
             'Median archived response time by archive',xlabel='Seconds')
        fig,ax=plt.subplots(figsize=(9,5))
        observed=[v for values in times.values() for v in values]
        if observed: ax.hist(observed,bins=min(20,max(3,len(observed)//4)))
        ax.set_title('Reference response-time distribution');ax.set_xlabel('Seconds');ax.set_ylabel('References')
        fig.tight_layout();fig.savefig(out/'response_time_distribution.png',dpi=180)
        fig.savefig(out/'response_time_distribution.svg');plt.close(fig)
    _save_json(out/'reference_summary.json',report,replace=True)
    report['output_dir']=str(out)
    return report
