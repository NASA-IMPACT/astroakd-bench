"""Inspect GPT-5.2 A/B/C benchmark answers and resource usage, offline.

Charts compare snapshot matches, runtime, tokens, MCP call averages, and
per-tool frequencies for the two MCP arms. These are experiment diagnostics, not scientific truth.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter
from typing import Any
import math
import os
import tempfile

from .exports import atomic_csv, json_compact
from .validator import ValidationError
from .three_arm import ARMS

ARM_LABELS = {'mcp_only': 'A — MCP only',
              'mcp_instruction': 'B — MCP + Instruction',
              'web_only': 'C — Web only'}
PLOT_STEMS = ('match_rate', 'mean_runtime', 'total_tokens',
              'mean_mcp_tool_calls', 'mcp_tool_calls_by_name')
PLOT_EXTENSIONS = ('.png', '.svg')


def plot_paths(directory: Path) -> list[Path]:
    return [directory / (name + suffix) for name in PLOT_STEMS for suffix in PLOT_EXTENSIONS]


def _nonnegative(v: Any) -> int:
    if v is None or isinstance(v, bool): return 0
    try:
        n = int(v)
    except (TypeError, ValueError, OverflowError): return 0
    return n if n >= 0 else 0


def _finite_nonnegative(v: Any) -> float | None:
    try:
        if v is None or isinstance(v, bool): return None
        value = float(v)
    except (ValueError, TypeError, OverflowError): return None
    return value if math.isfinite(value) and value >= 0 else None


def _usage(record: dict) -> tuple[int, int, int]:
    raw = record.get('token_usage') or {}
    if not isinstance(raw, dict): return (0,0,0)
    prompt = _nonnegative(raw.get('prompt_tokens', raw.get('input_tokens')))
    completion = _nonnegative(raw.get('completion_tokens', raw.get('output_tokens')))
    total = _nonnegative(raw.get('total_tokens')) or (prompt + completion)
    return prompt, completion, total


def _mcp_events(record: dict | None) -> list[dict]:
    """Return the attempted MCP gateway calls, including rejected/errors.

    Original serialized traces contain the full redacted arguments and tool
    response evidence. This offline projection does not change the runner.
    """
    events=(record or {}).get('trace') or []
    return [ev for ev in events if isinstance(ev,dict)
            and ev.get('tool') != 'openai_web_search'] if isinstance(events,list) else []


def _mcp_success(event: dict) -> bool:
    return event.get('status') == 'ok' and event.get('response_success',True) is not False


def _arguments_preview(event:dict) -> tuple[str,bool]:
    """Preserve the full sanitized arguments in JSONL; limit one CSV cell."""
    args=event.get('arguments')
    if args is None:return '',False
    formatted=json_compact(args)
    if len(formatted) > 8192:
        return formatted[:8192]+'...[truncated; full sanitized arguments in run JSONL]',True
    return formatted,False


def _mcp_event_rows(comparisons:list[dict], runs_by_key:dict) -> list[dict]:
    rows=[]
    for comparison in comparisons:
        for arm in ARMS[:2]:
            record=runs_by_key.get((comparison['task_id'],arm))
            for ordinal,ev in enumerate(_mcp_events(record),1):
                args=ev.get('arguments') or {}
                if not isinstance(args,dict):args={}
                preview,truncated=_arguments_preview(ev)
                rows.append({
                    'task_id':comparison['task_id'],
                    'question':comparison['question'], 'archive':comparison['archive'],
                    'arm':arm,'arm_label':ARM_LABELS[arm],
                    'call_index':ev.get('index',ordinal),
                    'tool_name':str(ev.get('tool') or '(unnamed)'),
                    'module_name':args.get('module_name',''),
                    'function_name':args.get('function_name',''),
                    'tool_signature':(str(ev.get('tool') or '(unnamed)') +
                                      (f" ({args['module_name']}.{args['function_name']})"
                                       if args.get('module_name') and args.get('function_name') else '')),
                    'status':ev.get('status','unknown'),
                    'successful_mcp_call':_mcp_success(ev),
                    'response_success':ev.get('response_success',''),
                    'duration_seconds':ev.get('duration_seconds',''),
                    'response_bytes':ev.get('response_bytes',''),
                    'response_truncated':ev.get('response_truncated',''),
                    'error_type':ev.get('error_type',''),
                    'error_message':str(ev.get('error',''))[:500],
                    'arguments_json':preview,'arguments_truncated':truncated,
                })
    return rows


MCP_CALL_COLUMNS = (
    'task_id','question','archive','arm','arm_label','call_index','tool_name',
    'module_name','function_name','tool_signature','status','successful_mcp_call','response_success',
    'duration_seconds','response_bytes','response_truncated','error_type',
    'error_message','arguments_json','arguments_truncated')
MCP_FREQUENCY_COLUMNS = (
    'tool_name','tool_signature','A_attempts','A_successful','A_rejected','A_errors','A_queries_using_tool',
    'B_attempts','B_successful','B_rejected','B_errors','B_queries_using_tool')


def _mcp_frequency(rows:list[dict]) -> list[dict]:
    names=sorted({(row['tool_name'],row['tool_signature']) for row in rows})
    grouped=[]
    for name,signature in names:
        item={'tool_name':name,'tool_signature':signature}
        for arm,letter in zip(ARMS[:2],'AB'):
            group=[row for row in rows if row['tool_signature']==signature and row['arm']==arm]
            item.update({
                f'{letter}_attempts':len(group),
                f'{letter}_successful':sum(x['successful_mcp_call'] for x in group),
                f'{letter}_rejected':sum(x['status']=='rejected' for x in group),
                f'{letter}_errors':sum(x['status']=='error' for x in group),
                f'{letter}_queries_using_tool':len({x['task_id'] for x in group}),
            })
        grouped.append(item)
    return grouped


def _usage_detail(record: dict | None) -> dict:
    if record is None:
        return dict(prompt_tokens='',completion_tokens='',total_tokens='',
                    duration_seconds='',tool_attempts='',successful_mcp_calls='',
                    mcp_tool_attempts='',mcp_tool_errors='',mcp_tool_names_json='',mcp_tool_counts_json='',
                    rejected_tool_calls='',web_search_calls='',error_type='',error_message='')
    prompt, completion, total = _usage(record)
    trace = record.get('trace') or []
    if not isinstance(trace,list):trace=[]
    calls=_mcp_events(record)
    mcp=sum(_mcp_success(ev) for ev in calls)
    names=[str(ev.get('tool') or '(unnamed)') for ev in calls]
    web = sum(_nonnegative(ev.get('web_search_calls',1)) for ev in trace
              if ev.get('tool')=='openai_web_search')
    error = record.get('error') or {}
    return dict(prompt_tokens=prompt,completion_tokens=completion,total_tokens=total,
                duration_seconds=record.get('duration_seconds', ''), tool_attempts=len(trace),
                successful_mcp_calls=mcp,mcp_tool_attempts=len(calls),
                mcp_tool_errors=sum(ev.get('status')=='error' for ev in calls),
                mcp_tool_names_json=json_compact(names),
                mcp_tool_counts_json=json_compact(dict(sorted(Counter(names).items()))),
                rejected_tool_calls=sum(ev.get('status')=='rejected' for ev in trace),
                web_search_calls=web,error_type=error.get('type',''),error_message=error.get('message',''))


def export_detailed(comparisons:list[dict], summaries:list[dict], runs_by_key:dict, *,
                    detail_csv:Path|None,performance_csv:Path|None,task_performance_csv:Path|None,
                    plots_dir:Path|None,mcp_calls_csv:Path|None=None,
                    mcp_tool_frequency_csv:Path|None=None,replace:bool=False,collect:bool=False) -> dict:
    """Export richer post-score views, retaining every answer, even when wrong.

    The caller has already validated task/oracle hashes, model and arm separation.
    """
    if not any(p is not None for p in (detail_csv,performance_csv,task_performance_csv,plots_dir,
                                        mcp_calls_csv,mcp_tool_frequency_csv)) and not collect:
        return {}
    by_arm = {summary['arm']:summary for summary in summaries}
    detail=[]; per_task=[]; performance=[]
    call_rows=_mcp_event_rows(comparisons,runs_by_key)
    frequencies=_mcp_frequency(call_rows)
    for comparison in comparisons:
        for arm,prefix in zip(ARMS,'ABC'):
            record=runs_by_key.get((comparison['task_id'],arm))
            answer=(record or {}).get('answer') or {}
            if not isinstance(answer,dict):answer={'answer':str(answer)}
            status=comparison[prefix+'_status']
            raw_values=answer.get('answer_values')
            mixed_abstention=answer.get('abstained') is True and bool(raw_values)
            if record is None: disposition='NOT_RUN'
            elif record.get('status')!='completed': disposition='RUN_ERROR'
            elif mixed_abstention: disposition='ABSTAIN_WITH_VALUES'
            elif answer.get('abstained') is True:disposition='ABSTAIN'
            elif status=='CORRECT': disposition='CORRECT'
            else: disposition=status
            metrics=_usage_detail(record)
            sources=answer.get('sources') or []
            row = {
                'task_id':comparison['task_id'], 'arm':arm, 'arm_label':ARM_LABELS[arm],
                'task_type':comparison['task_type'],'archive':comparison['archive'],
                'question':comparison['question'], 'reference_answer':comparison['reference_answer'],
                'reference_unit':comparison['unit'], 'reference_tolerance':comparison['tolerance'],
                'reference_status':comparison['reference_status'],
                'run_status':record.get('status') if record else 'not_run',
                'match_status':status,'reference_match':comparison[prefix+'_correct'],
                'answer_disposition':disposition,
                'answer_text':answer.get('answer',''),
                'answer_values_json':json_compact(raw_values) if raw_values is not None else '',
                'answer_unit':answer.get('unit') or '', 'abstained':answer.get('abstained','') if record else '',
                'parse_status':answer.get('parse_status',''),
                'source_identifiers_json':json_compact(sources),
                'model':record.get('model') if record else '',
                **metrics,
                # Keep complete potentially huge tool-response traces in the source
                # JSONL journal; this summary stays usable in ordinary CSV readers.
                'tool_event_summary_json':json_compact([
                    {k:event[k] for k in ('tool','status','error_type','response_success','web_search_calls') if k in event}
                    for event in (record.get('trace') or [])
                ]) if record else '',
            }
            detail.append(row)
            per_task.append({k:row[k] for k in (
                'task_id','arm','arm_label','run_status','match_status','reference_match',
                'duration_seconds','prompt_tokens','completion_tokens','total_tokens',
                'tool_attempts','successful_mcp_calls','rejected_tool_calls','web_search_calls',
                'mcp_tool_attempts','mcp_tool_errors','mcp_tool_names_json','mcp_tool_counts_json')})
    for arm in ARMS:
        summ=by_arm[arm]
        subset=[runs_by_key.get((q['task_id'],arm)) for q in comparisons]
        attempted=[r for r in subset if r is not None]
        elapsed=[duration for r in attempted if (duration:=_finite_nonnegative(r.get('duration_seconds'))) is not None]
        token_counts=[_usage(r) for r in attempted]
        metrics=[_usage_detail(r) for r in attempted]
        good=sum(r.get('status')=='completed' for r in attempted)
        result=dict(arm=arm,arm_label=ARM_LABELS[arm],model='gpt-5.2',
            total_questions=len(comparisons),attempted=len(attempted),completed=good,
            incorrect=summ['attempted']-summ['correct'],correct=summ['correct'],
            not_run=len(comparisons)-len(attempted),
            completion_rate_attempted_pct=round(100*good/len(attempted),2) if attempted else '',
            reference_match_pct_attempted=summ['reference_match_pct_attempted'],
            reference_match_pct_all_questions=summ['reference_match_pct_all_questions'],
            mean_runtime_seconds=round(sum(elapsed)/len(elapsed),4) if elapsed else '',
            total_runtime_seconds=round(sum(elapsed),4) if elapsed else '',
            timed_runs=len(elapsed),
            total_prompt_tokens=sum(a for a,b,c in token_counts),
            total_completion_tokens=sum(b for a,b,c in token_counts),
            total_tokens=sum(c for a,b,c in token_counts),
            token_usage_reported_runs=sum(bool(r.get('token_usage')) for r in attempted),
            mean_tokens_per_attempt=round(sum(c for a,b,c in token_counts)/len(attempted),2) if attempted else '',
            successful_mcp_calls=sum(x['successful_mcp_calls'] for x in metrics),
            total_mcp_tool_attempts=sum(x['mcp_tool_attempts'] for x in metrics),
            mean_mcp_tool_calls_per_attempt=round(sum(x['mcp_tool_attempts'] for x in metrics)/len(attempted),4) if attempted and arm!='web_only' else '',
            mean_successful_mcp_calls_per_attempt=round(sum(x['successful_mcp_calls'] for x in metrics)/len(attempted),4) if attempted and arm!='web_only' else '',
            distinct_mcp_tools=len({ev.get('tool') for r in attempted for ev in _mcp_events(r)}),
            rejected_tool_calls=sum(x['rejected_tool_calls'] for x in metrics),
            web_search_calls=sum(x['web_search_calls'] for x in metrics),
            run_errors=sum(r.get('status')!='completed' for r in attempted),
            answer_key_status='reference_anchored_unreviewed',
            scientific_accuracy_pct='')
        performance.append(result)
    if plots_dir is not None:
        # Check the optional plotting dependency before publishing any CSV.
        try:
            import matplotlib
        except ImportError as exc:
            raise ValidationError('Install optional plotting dependencies: uv run --with matplotlib python -m benchmark score-scorable ...') from exc
    if detail_csv is not None:
        atomic_csv(detail_csv,detail,tuple(detail[0]),replace=replace)
    if performance_csv is not None:
        atomic_csv(performance_csv,performance,tuple(performance[0]),replace=replace)
    if task_performance_csv is not None:
        atomic_csv(task_performance_csv,per_task,tuple(per_task[0]),replace=replace)
    if mcp_calls_csv is not None:
        atomic_csv(mcp_calls_csv,call_rows,MCP_CALL_COLUMNS,replace=replace)
    if mcp_tool_frequency_csv is not None:
        atomic_csv(mcp_tool_frequency_csv,frequencies,MCP_FREQUENCY_COLUMNS,replace=replace)
    if plots_dir is not None:
        _plot(performance,plots_dir,frequencies)
    return {'reporting_milestone':'0.6.7.1 - THREE_ARM_DETAILED_ANSWER_PERFORMANCE_PLOTS',
            'mcp_reporting_milestone':'0.6.7.7 - MCP_TOOL_CALL_REPORTING_AND_AB_PLOTS',
            'detailed_answers_csv':str(detail_csv) if detail_csv else None,
            'performance_observations_csv':str(performance_csv) if performance_csv else None,
            'per_task_performance_csv':str(task_performance_csv) if task_performance_csv else None,
            'barplots':[str(p) for p in plot_paths(plots_dir)] if plots_dir else [],
            'mcp_call_events_csv':str(mcp_calls_csv) if mcp_calls_csv else None,
            'mcp_tool_frequency_csv':str(mcp_tool_frequency_csv) if mcp_tool_frequency_csv else None,
            'mcp_tool_attempts_recorded':len(call_rows),
            'mcp_tool_frequencies':frequencies,
            'performance_observations':performance}


def _plot(performance: list[dict], out_dir:Path, frequencies:list[dict]) -> None:
    try:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
    except ImportError as exc:
        raise ValidationError('Bar plots require matplotlib: run uv run --with matplotlib python -m benchmark score-scorable ...') from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    titles=('Reference-snapshot match rate', 'Mean runtime per attempted query', 'Total recorded tokens')
    keys=('reference_match_pct_attempted','mean_runtime_seconds','total_tokens')
    units=('% of attempted queries', 'seconds', 'tokens')
    labels=['A — MCP only','B — MCP + Instruction','C — Web only']
    stage = 'pilot' if any(x['attempted'] < x['total_questions'] for x in performance) else 'full run'
    for stem,title,key,units_label in zip(PLOT_STEMS,titles,keys,units):
        values=[x[key] for x in performance]
        fig, ax=plt.subplots(figsize=(9.3,5.6))
        present=[isinstance(v,(int,float)) and not isinstance(v,bool) for v in values]
        nums=[float(v) if p else 0.0 for v,p in zip(values,present)]
        bars=ax.bar(labels,nums,width=0.56)
        ax.set_ylabel(units_label)
        ax.set_title(title+f' — GPT-5.2 {stage}')
        maxv=max(nums or [0.0])
        ax.set_ylim(0, (maxv*1.24) if maxv else 1)
        ax.grid(axis='y',alpha=0.2)
        ax.set_axisbelow(True)
        for i,(rect,v,valid) in enumerate(zip(bars,values,present)):
            if not valid:display='N/A'
            elif stem=='match_rate':display=f'{v:.1f}%'
            elif stem=='mean_runtime':display=f'{v:.2f} s'
            else:display=f'{v:,.0f}'
            ax.text(rect.get_x()+rect.get_width()/2,rect.get_height()+max(maxv*.025,0.012),
                    display,ha='center',va='bottom',fontsize=10)
        sizes=', '.join(f"{x['attempted']}/{x['total_questions']}" for x in performance)
        fig.text(0.5,0.045,f'Attempted per arm: {sizes}. Frozen archive snapshot; not independently reviewed scientific gold.',
                 ha='center',va='center',fontsize=8.3,color='#555555')
        fig.tight_layout(rect=(0,0.07,1,1))
        for ext in PLOT_EXTENSIONS:
            final=out_dir/(stem+ext)
            temp=None
            try:
                with tempfile.NamedTemporaryFile(dir=out_dir,prefix='.astroakd-plot-',suffix=ext,delete=False) as fh:
                    temp=Path(fh.name)
                fig.savefig(temp,format=ext.lstrip('.'),dpi=180,bbox_inches='tight')
                os.replace(temp,final)
            finally:
                if temp is not None:temp.unlink(missing_ok=True)
        plt.close(fig)
    _plot_mcp(plt, performance, frequencies, out_dir)


def _plot_mcp(plt, performance:list[dict], frequencies:list[dict], out_dir:Path) -> None:
    """Two MCP-only views; never include the Web-only arm in the denominators."""
    arms=performance[:2]
    labels=['A — MCP only','B — MCP + Instruction']
    fig,ax=plt.subplots(figsize=(9.3,5.6))
    x=[0,1]; width=.32
    attempts=[v['mean_mcp_tool_calls_per_attempt'] for v in arms]
    successes=[v['mean_successful_mcp_calls_per_attempt'] for v in arms]
    one=ax.bar([v-width/2 for v in x],[v if isinstance(v,(int,float)) else 0 for v in attempts],width,label='Attempted calls')
    two=ax.bar([v+width/2 for v in x],[v if isinstance(v,(int,float)) else 0 for v in successes],width,label='Successful calls')
    ax.set_xticks(x,labels);ax.set_ylabel('MCP calls per attempted query')
    ax.set_title('Mean MCP tool calls per question — GPT-5.2')
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend()
    for bars,vals in ((one,attempts),(two,successes)):
        ax.bar_label(bars,labels=[f'{v:.2f}' if isinstance(v,(int,float)) else 'N/A' for v in vals],padding=3)
    n=', '.join(f"{a['attempted']}/{a['total_questions']}" for a in arms)
    fig.text(.5,.045,f'Attempted questions: A/B = {n}; includes rejected gateway calls.',ha='center',fontsize=8.5)
    fig.tight_layout(rect=(0,.07,1,1))
    _save_plot(fig, out_dir, 'mean_mcp_tool_calls')
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(max(9.3,2.2*len(frequencies)+4),5.8))
    if frequencies:
        idx=list(range(len(frequencies)))
        left=ax.bar([i-width/2 for i in idx],[row['A_attempts'] for row in frequencies],width,label='A — MCP only')
        right=ax.bar([i+width/2 for i in idx],[row['B_attempts'] for row in frequencies],width,label='B — MCP + Instruction')
        def short_label(row):
            signature=row['tool_signature']
            if row['tool_name']=='astroquery_execute' and '(' in signature:
                return signature.split('(',1)[1].rstrip(')').replace('.', '\n',1)
            return signature.replace(' (','\n(')
        ax.set_xticks(idx,[short_label(row) for row in frequencies],rotation=0,ha='center')
        for bars in (left,right):
            ax.bar_label(bars,padding=3,fontsize=9)
    else:
        ax.text(.5,.5,'No MCP tool calls recorded',ha='center',va='center',transform=ax.transAxes)
        ax.set_xticks([])
    ax.set_ylim(0, max(1,max([max(row['A_attempts'],row['B_attempts']) for row in frequencies],default=0)*1.25))
    ax.set_ylabel('Total tool call attempts')
    ax.set_title('MCP tool calls by function — GPT-5.2')
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend() if frequencies else None
    fig.text(.5,.04,'A and B only. Counts include successful, rejected and error calls; see tool-frequency CSV.',
             ha='center',fontsize=8.5)
    fig.tight_layout(rect=(0,.07,1,1))
    _save_plot(fig,out_dir,'mcp_tool_calls_by_name')
    plt.close(fig)


def _save_plot(fig, out_dir:Path, stem:str) -> None:
    """Publish both graphics formats after rendering via temporary files."""
    for extension in PLOT_EXTENSIONS:
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=out_dir,prefix='.astroakd-plot-',suffix=extension,delete=False) as stream:
                temporary=Path(stream.name)
            fig.savefig(temporary,format=extension[1:],dpi=180,bbox_inches='tight')
            os.replace(temporary,out_dir/(stem+extension))
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
