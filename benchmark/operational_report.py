#!/usr/bin/env python3
"""Offline operational A/B/C reports for original AstroAKD-Bench run-three-arm journals.

Does NOT assess scientific correctness. Supports partial .progress.jsonl journals.
Dependencies: Python 3.11+, matplotlib.
"""
import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import math

ARMS = ('mcp_only', 'mcp_instruction', 'web_only')
LABELS = ('A: MCP', 'B: MCP + instruction', 'C: Web')


def jsonl(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def write_csv(path, rows, names):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def plot_bars(plt, path, labels, values, title, ylabel, *, annotate=True):
    fig, ax = plt.subplots(figsize=(9.2, 5.3))
    numeric = [float('nan') if v is None else v for v in values]
    bars = ax.bar(labels, numeric)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis='x', labelrotation=0)
    if annotate:
        for bar, value in zip(bars, values):
            if value is not None and math.isfinite(float(value)):
                ax.annotate(f'{value:,.2f}' if isinstance(value, float) else f'{value:,}',
                            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            ha='center', va='bottom', xytext=(0, 3), textcoords='offset points')
    top = max((v for v in values if v is not None), default=0)
    ax.set_ylim(0, max(top * 1.17, 1))
    fig.tight_layout()
    fig.savefig(path.with_suffix('.png'), dpi=180)
    fig.savefig(path.with_suffix('.svg'))
    plt.close(fig)


def create_operational_report(tasks_path: Path, runs_path: Path, output_dir: Path,
                              *, replace: bool = False, plots: bool = True):
    from types import SimpleNamespace
    args = SimpleNamespace(tasks=Path(tasks_path), runs=Path(runs_path), output_dir=Path(output_dir))
    if not args.runs.exists() and args.runs.with_name(args.runs.name+'.progress.jsonl').exists():
        args.runs = args.runs.with_name(args.runs.name+'.progress.jsonl')
    if not args.runs.exists():
        raise FileNotFoundError(f'No A/B/C run journal: {args.runs}')
    wanted = ['per_task_operational.csv','arm_operational_summary.csv',
              'mcp_tool_frequency.csv','operational_report.json','abc_answers.csv']
    if any((args.output_dir / n).exists() for n in wanted) and not replace:
        raise FileExistsError('Agent report already exists; use --replace (never overwrites runs)')
    if plots:
        try: from matplotlib import pyplot as plt
        except ImportError as exc: raise RuntimeError('Install matplotlib: uv run --with matplotlib ...') from exc

    tasks = jsonl(args.tasks)
    digest = hashlib.sha256(args.tasks.read_bytes()).hexdigest()
    task_map = {t['id']: t for t in tasks}
    if len(task_map) != len(tasks):
        parser.error('Task IDs are not unique')
    runs = jsonl(args.runs)
    seen = set()
    for rec in runs:
        key = (rec.get('task_id'), rec.get('arm'))
        if rec.get('candidate_sha256') != digest or key[0] not in task_map or key[1] not in ARMS or key in seen:
            parser.error('Mismatched source dataset, unknown arm, or duplicate task/arm in run journal')
        trace = rec.get('trace') or []
        if not isinstance(trace, list):
            parser.error('Invalid run trace')
        if key[1] == 'web_only' and any(e.get('tool') != 'openai_web_search' for e in trace):
            parser.error('Web arm contains non-web tools')
        if key[1] != 'web_only' and any(e.get('tool') == 'openai_web_search' for e in trace):
            parser.error('MCP arm contains web-search tool')
        seen.add(key)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    task_rows, frequencies = [], Counter()
    for r in runs:
        trace = r.get('trace') or []
        mcp = [e for e in trace if e.get('tool') != 'openai_web_search']
        for e in mcp:
            args_info = e.get('arguments') or e.get('args') or {}
            name = str(e.get('tool', 'unknown'))
            if name == 'astroquery_execute' and isinstance(args_info, dict):
                params = args_info.get('params') or {}
                mod = args_info.get('module') or (params.get('module') if isinstance(params, dict) else None)
                fn = args_info.get('function') or (params.get('function') if isinstance(params, dict) else None)
                if mod and fn:
                    name += f':{mod}.{fn}'
            frequencies[(r['arm'], name)] += 1
        usage = r.get('token_usage') or {}
        task_rows.append({
            'task_id': r['task_id'],
            'archive': task_map[r['task_id']].get('module', ''),
            'arm': r['arm'],
            'run_status': r.get('status'),
            'answer_format': (r.get('answer') or {}).get('parse_status', ''),
            'abstained': (r.get('answer') or {}).get('abstained', False),
            'duration_seconds': r.get('duration_seconds', ''),
            'input_tokens': usage.get('input_tokens', ''),
            'output_tokens': usage.get('output_tokens', ''),
            'total_tokens': usage.get('total_tokens', ''),
            'mcp_call_events': len(mcp),
            'successful_mcp_queries': r.get('successful_mcp_queries', 0),
            'web_search_calls': sum(int(e.get('web_search_calls') or 0) for e in trace if e.get('tool') == 'openai_web_search'),
        })
    fields = ['task_id','archive','arm','run_status','answer_format','abstained','duration_seconds',
              'input_tokens','output_tokens','total_tokens','mcp_call_events','successful_mcp_queries','web_search_calls']
    write_csv(args.output_dir / 'per_task_operational.csv', task_rows, fields)

    arm_rows = []
    for arm in ARMS:
        subset = [r for r in task_rows if r['arm'] == arm]
        times = [float(r['duration_seconds']) for r in subset if isinstance(r['duration_seconds'], (float, int))]
        complete = [r for r in subset if r['run_status'] == 'completed']
        arm_rows.append({
            'arm': arm,
            'tasks_total': len(tasks),
            'runs_recorded': len(subset),
            'runs_completed': len(complete),
            'run_errors': len(subset) - len(complete),
            'completion_pct_recorded': (100*len(complete)/len(subset)) if subset else '',
            'mean_runtime_s': round(mean(times), 4) if times else '',
            'median_runtime_s': round(median(times), 4) if times else '',
            'total_input_tokens': sum(int(r['input_tokens'] or 0) for r in subset),
            'total_output_tokens': sum(int(r['output_tokens'] or 0) for r in subset),
            'total_tokens': sum(int(r['total_tokens'] or 0) for r in subset),
            'mean_mcp_events_per_run': round(sum(r['mcp_call_events'] for r in subset)/len(subset), 4) if subset else '',
            'successful_mcp_queries': sum(r['successful_mcp_queries'] for r in subset),
            'web_search_calls': sum(r['web_search_calls'] for r in subset),
            'scientific_accuracy': 'NOT_ASSESSED_UNREVIEWED_GOLD',
        })
    summary_cols = list(arm_rows[0])
    write_csv(args.output_dir / 'arm_operational_summary.csv', arm_rows, summary_cols)
    freq_rows = [dict(arm=a, tool=name, calls=n) for (a, name), n in sorted(frequencies.items())]
    write_csv(args.output_dir / 'mcp_tool_frequency.csv', freq_rows, ['arm','tool','calls'])

    if plots:
        def vals(field):
            return [x[field] if x[field] != '' else None for x in arm_rows]
        plot_bars(plt,args.output_dir/'completed_runs',LABELS,vals('runs_completed'),
                  'Agent runs completed (operational, not scientific accuracy)','Runs')
        plot_bars(plt,args.output_dir/'mean_runtime',LABELS,vals('mean_runtime_s'),
                  'Mean agent runtime','Seconds')
        plot_bars(plt,args.output_dir/'total_tokens',LABELS,vals('total_tokens'),
                  'Total tokens consumed','Tokens')
        plot_bars(plt,args.output_dir/'mean_mcp_events',LABELS,vals('mean_mcp_events_per_run'),
                  'Mean MCP tool events per recorded run','MCP events')
        plot_bars(plt,args.output_dir/'web_search_calls',LABELS,vals('web_search_calls'),
                  'Total web-search calls','Calls')
    report = {
        'dataset_sha256': digest,
        'questions':len(tasks), 'runs_recorded':len(runs),
        'expected_runs':len(tasks)*len(ARMS),
        'status':'COMPLETE' if len(runs)==len(tasks)*len(ARMS) else 'PARTIAL',
        'scientific_accuracy':'NOT_ASSESSED; requires independently reviewed gold answers',
        'arms':arm_rows,
    }
    # Agent answers remain intact, including errors and abstentions.
    byid={(r['task_id'],r['arm']):r for r in runs}
    answer_rows=[]
    for task in tasks:
        row={'task_id':task['id'],'task_type':task.get('task_type',''),
             'question':task.get('question',''),'target':task.get('target','')}
        for prefix,arm in zip(('A','B','C'),ARMS):
            result=byid.get((task['id'],arm),{})
            row[prefix+'_status']=result.get('status','not_run')
            row[prefix+'_answer_json']=json.dumps(result.get('answer',{}),ensure_ascii=False)
        answer_rows.append(row)
    write_csv(args.output_dir/'abc_answers.csv',answer_rows,list(answer_rows[0]))
    (args.output_dir/'operational_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    report['output_dir']=str(args.output_dir)
    return report

