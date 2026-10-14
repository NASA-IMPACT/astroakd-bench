"""Offline paired GPT-5.2 experiment analyses; no reference oracle modification.

Missing arm runs remain unavailable (never coerced to negative results or zero
cost). Reference mismatch does not establish a scientifically wrong answer.
"""
from __future__ import annotations

from pathlib import Path
from collections import Counter
import math
import os
import random
import statistics
import tempfile

from .three_arm import ARMS
from .scorable_diagnostics import ARM_LABELS, _mcp_events, _mcp_success, _usage_detail
from .exports import atomic_csv, json_compact
from .validator import ValidationError

PAIRS = (('A', 'B'), ('A', 'C'), ('B', 'C'))
PLOT_STEMS = ('paired_runtime_deltas', 'paired_token_deltas',
              'paired_match_disagreements', 'paired_mcp_attempt_deltas')
EXTENSIONS = ('.png', '.svg')


def paired_plot_paths(folder: Path) -> list[Path]:
    return [folder / (stem + ext) for stem in PLOT_STEMS for ext in EXTENSIONS]


def _number(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _difference(left, right):
    l, r = _number(left), _number(right)
    return round(r - l, 8) if l is not None and r is not None else ''


def _percentile(sorted_numbers, p):
    if not sorted_numbers:
        return ''
    index = p * (len(sorted_numbers) - 1)
    lo, hi = math.floor(index), math.ceil(index)
    return sorted_numbers[lo] + (sorted_numbers[hi] - sorted_numbers[lo]) * (index - lo)


def _spread(numbers, seed):
    """Paired, nonparametric bootstrap of a mean difference, deterministic."""
    if not numbers:
        return dict(pairs=0, mean='', median='', q1='', q3='', bootstrap_ci95_low='', bootstrap_ci95_high='')
    sorted_numbers = sorted(numbers)
    rand = random.Random(seed)
    n = len(numbers)
    means = sorted(sum(numbers[rand.randrange(n)] for _ in range(n)) / n for _ in range(2000))
    return dict(pairs=n, mean=round(statistics.fmean(numbers), 6),
                median=round(statistics.median(numbers), 6),
                q1=round(_percentile(sorted_numbers, .25), 6),
                q3=round(_percentile(sorted_numbers, .75), 6),
                bootstrap_ci95_low=round(_percentile(means, .025), 6),
                bootstrap_ci95_high=round(_percentile(means, .975), 6))


def _exact_mcnemar(first_only, second_only):
    """Exact two-sided binomial McNemar p for discordant complete pairs."""
    n = first_only + second_only
    if n == 0:
        return 1.0
    return float(f"{min(1.0, 2 * sum(math.comb(n, k) for k in range(min(first_only, second_only) + 1)) / (2 ** n)):.12g}")


def _label_case(a, b):
    if a == '' or b == '':
        return 'NOT_PAIRED'
    if a and b:
        return 'BOTH_MATCH'
    if a:
        return 'FIRST_ONLY_MATCH'
    if b:
        return 'SECOND_ONLY_MATCH'
    return 'NEITHER_MATCH'


def _error_category(record, status):
    if status == 'RUN_ERROR':
        return 'RUN_ERROR'
    answer = (record or {}).get('answer') or {}
    if not isinstance(answer, dict):
        return 'UNSTRUCTURED'
    if answer.get('abstained') is True and answer.get('answer_values'):
        return 'ABSTAIN_WITH_VALUES'
    if answer.get('abstained') is True:
        return 'ABSTAIN'
    if status == 'INCORRECT_FORMAT':
        return 'INCORRECT_FORMAT'
    if status in ('REVIEW_UNSTRUCTURED', 'REVIEW_DUPLICATE_VALUES'):
        return 'INCORRECT_FORMAT'
    if status in ('NOT_RUN', 'CORRECT'):
        return ''
    return 'REFERENCE_MISMATCH_UNCLASSIFIED'


def _records(comparisons, runs):
    paired = []
    mismatches = []
    for question in comparisons:
        task_id = question['task_id']
        row = {k: question[k] for k in ('task_id','task_type','archive','question',
                'reference_answer','answer_kind','unit','tolerance','reference_status')}
        for letter, arm in zip('ABC', ARMS):
            rec = runs.get((task_id, arm))
            metrics = _usage_detail(rec)
            status = question[letter + '_status']
            answer = (rec or {}).get('answer') or {}
            if not isinstance(answer, dict):
                answer = {'answer': str(answer)}
            row.update({
                f'{letter}_match_status': status,
                f'{letter}_reference_match': question[letter + '_correct'],
                f'{letter}_run_status': rec.get('status', '') if rec else 'NOT_RUN',
                f'{letter}_answer': answer.get('answer', ''),
                f'{letter}_answer_values_json': json_compact(answer.get('answer_values')) if answer.get('answer_values') is not None else '',
                f'{letter}_unit': answer.get('unit') or '',
                f'{letter}_duration_seconds': metrics['duration_seconds'],
                f'{letter}_prompt_tokens': metrics['prompt_tokens'],
                f'{letter}_completion_tokens': metrics['completion_tokens'],
                f'{letter}_total_tokens': metrics['total_tokens'],
                f'{letter}_mcp_tool_attempts': metrics['mcp_tool_attempts'] if letter!='C' else '',
                f'{letter}_successful_mcp_calls': metrics['successful_mcp_calls'] if letter!='C' else '',
                f'{letter}_rejected_tool_calls': metrics['rejected_tool_calls'] if letter!='C' else '',
                f'{letter}_web_search_calls': metrics['web_search_calls'] if letter=='C' else '',
                f'{letter}_mcp_tool_names_json': metrics['mcp_tool_names_json'] if letter!='C' else '',
            })
            if rec is not None and status != 'CORRECT':
                mismatches.append({
                    'task_id': task_id, 'archive': question['archive'], 'question': question['question'],
                    'arm': arm, 'arm_label': ARM_LABELS[arm], 'run_status': rec.get('status',''),
                    'match_status': status, 'observed_category': _error_category(rec, status),
                    'reference_answer': question['reference_answer'], 'reference_unit': question['unit'],
                    'reference_tolerance': question['tolerance'],
                    'answer_text': answer.get('answer',''),
                    'answer_values_json': row[f'{letter}_answer_values_json'],
                    'answer_unit': answer.get('unit') or '',
                    'abstained': answer.get('abstained',''),
                    'parse_status': answer.get('parse_status',''),
                    'sources_json': json_compact(answer.get('sources') or []),
                    'review_status': 'PENDING_INDEPENDENT_REVIEW',
                    'scientific_cause': '',
                })
        for first, second in PAIRS:
            row[f'{first}_{second}_match_case'] = _label_case(
                row[f'{first}_reference_match'], row[f'{second}_reference_match'])
            row[f'{second}_minus_{first}_runtime_seconds'] = _difference(
                row[f'{first}_duration_seconds'], row[f'{second}_duration_seconds'])
            row[f'{second}_minus_{first}_total_tokens'] = _difference(
                row[f'{first}_total_tokens'], row[f'{second}_total_tokens'])
        row['B_minus_A_mcp_attempts'] = _difference(row['A_mcp_tool_attempts'], row['B_mcp_tool_attempts'])
        row['B_minus_A_successful_mcp_calls'] = _difference(row['A_successful_mcp_calls'], row['B_successful_mcp_calls'])
        row['B_minus_A_rejected_calls'] = _difference(row['A_rejected_tool_calls'], row['B_rejected_tool_calls'])
        paired.append(row)
    return paired, mismatches


def _pairwise(paired):
    records = []
    for i,(first, second) in enumerate(PAIRS):
        cases=Counter(row[f'{first}_{second}_match_case'] for row in paired)
        n = sum(count for case,count in cases.items() if case!='NOT_PAIRED')
        runtime=[row[f'{second}_minus_{first}_runtime_seconds'] for row in paired]
        tokens=[row[f'{second}_minus_{first}_total_tokens'] for row in paired]
        runtime=[v for x in runtime if (v:=_number(x)) is not None]
        tokens=[v for x in tokens if (v:=_number(x)) is not None]
        result = {
            'pair': f'{first}_vs_{second}', 'first_arm': ARMS['ABC'.index(first)],
            'second_arm': ARMS['ABC'.index(second)],
            'total_questions':len(paired), 'correctness_paired_questions':n,
            'both_match':cases['BOTH_MATCH'], 'first_only_match':cases['FIRST_ONLY_MATCH'],
            'second_only_match':cases['SECOND_ONLY_MATCH'], 'neither_match':cases['NEITHER_MATCH'],
            'not_paired':cases['NOT_PAIRED'],
            'second_minus_first_match_percentage_points':
                round(100*(cases['SECOND_ONLY_MATCH']-cases['FIRST_ONLY_MATCH'])/n, 4) if n else '',
            'exact_mcnemar_two_sided_p':_exact_mcnemar(cases['FIRST_ONLY_MATCH'], cases['SECOND_ONLY_MATCH']) if n else '',
        }
        for label,nums,offset in (('runtime_seconds',runtime,0),('total_tokens',tokens,10)):
            stats = _spread(nums,seed=6078+i*30+offset)
            result.update({f'{label}_{key}':value for key,value in stats.items()})
        if first=='A' and second=='B':
            data=[v for row in paired if (v:=_number(row['B_minus_A_mcp_attempts'])) is not None]
            stats=_spread(data,seed=6078+80)
            result.update({f'mcp_attempts_{key}':value for key,value in stats.items()})
        else:
            result.update({f'mcp_attempts_{key}':'' for key in _spread([],0)})
        records.append(result)
    return records


def _overall(performance):
    return [{**p,'evaluation_scope':'reference_snapshot_unreviewed'} for p in performance]


def _mcp_ab(performance, runs, comparisons):
    items = []
    for arm in ARMS[:2]:
        perf = next(row for row in performance if row['arm']==arm)
        records = [runs.get((q['task_id'],arm)) for q in comparisons]
        attempts = [ev for record in records if record is not None for ev in _mcp_events(record)]
        unique_functions=set()
        for event in attempts:
            args=event.get('arguments') or {}
            if isinstance(args,dict) and args.get('module_name') and args.get('function_name'):
                unique_functions.add(f"{args['module_name']}.{args['function_name']}")
        items.append({**perf,
            'mcp_error_calls':sum(event.get('status')=='error' for event in attempts),
            'mcp_other_unsuccessful':sum(not _mcp_success(e) and e.get('status') not in ('error','rejected') for e in attempts),
            'distinct_underlying_archive_functions':len(unique_functions),
            'underlying_archive_functions_json':json_compact(sorted(unique_functions)),
        })
    return items


def _save_plot(fig, directory, stem):
    directory.mkdir(parents=True,exist_ok=True)
    for ext in EXTENSIONS:
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=directory,suffix=ext,prefix='.astroakd-paired-',delete=False) as f:
                temp=Path(f.name)
            fig.savefig(temp,format=ext[1:],dpi=180,bbox_inches='tight')
            os.replace(temp,directory/(stem+ext))
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)


def _plots(paired, paired_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
    except ImportError as exc:
        raise ValidationError('Paired plots require matplotlib: uv run --with matplotlib python -m benchmark score-scorable ...') from exc
    for stem,title,key,unit in (
        ('paired_runtime_deltas','Paired runtime: B minus A','B_minus_A_runtime_seconds','seconds'),
        ('paired_token_deltas','Paired token use: B minus A','B_minus_A_total_tokens','tokens'),
        ('paired_mcp_attempt_deltas','Paired MCP attempts: B minus A','B_minus_A_mcp_attempts','call attempts'),
    ):
        vals=[v for row in paired if (v:=_number(row[key])) is not None]
        fig,ax=plt.subplots(figsize=(9,5))
        if vals:
            ax.hist(vals,bins=max(1,min(21,round(math.sqrt(len(vals))*2))))
            ax.axvline(0,linestyle='--',linewidth=1,label='No difference')
            ax.axvline(statistics.median(vals),linestyle=':',linewidth=1.2,label=f'Median {statistics.median(vals):,.2f}')
            ax.legend()
        else:
            ax.text(.5,.5,'No paired observations',ha='center',va='center',transform=ax.transAxes)
        ax.set_xlabel(unit+' (B − A)');ax.set_ylabel('Number of paired questions');ax.set_title(title+' — GPT-5.2')
        ax.grid(axis='y',alpha=.15);fig.tight_layout()
        _save_plot(fig,paired_dir,stem);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9.8,5.7))
    labels=[]; bottom=[0,0,0]
    for first,second in PAIRS:
        labels.append(f'{first} vs {second}')
    positions=range(3)
    for category,label in (
        ('BOTH_MATCH','Both match'),('FIRST_ONLY_MATCH','First only'),
        ('SECOND_ONLY_MATCH','Second only'),('NEITHER_MATCH','Neither match')):
        values=[sum(row[f'{a}_{b}_match_case']==category for row in paired) for a,b in PAIRS]
        ax.bar(positions,values,bottom=bottom,label=label)
        bottom=[x+y for x,y in zip(bottom,values)]
    ax.set_xticks(list(positions),labels)
    ax.set_ylabel('Questions with paired observations')
    ax.set_title('Paired reference-snapshot match outcomes — GPT-5.2')
    ax.legend();ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);fig.tight_layout()
    _save_plot(fig,paired_dir,'paired_match_disagreements');plt.close(fig)


def export_paired(comparisons, performance, runs_by_key, *,
                  overall_csv=None,mcp_ab_summary_csv=None,paired_questions_csv=None,
                  paired_summary_csv=None,mismatch_audit_csv=None,paired_plots_dir=None,
                  replace=False):
    """Write optional supplementary files after scorer validates hashes/arm membership."""
    if not any(p is not None for p in (overall_csv,mcp_ab_summary_csv,paired_questions_csv,
                     paired_summary_csv,mismatch_audit_csv,paired_plots_dir)):
        return {}
    questions,mismatches=_records(comparisons,runs_by_key)
    overview=_overall(performance)
    mcp=_mcp_ab(performance,runs_by_key,comparisons)
    summary=_pairwise(questions)
    if paired_plots_dir is not None:
        try:
            import matplotlib
        except ImportError as exc:
            raise ValidationError('Paired figures require matplotlib') from exc
    for path,rows in ((overall_csv,overview),(mcp_ab_summary_csv,mcp),
                      (paired_questions_csv,questions),(paired_summary_csv,summary),
                      (mismatch_audit_csv,mismatches)):
        if path is not None:
            if rows:
                columns=tuple(rows[0])
            elif path==mismatch_audit_csv:
                columns=('task_id','archive','question','arm','arm_label','run_status','match_status',
                         'observed_category','reference_answer','reference_unit','reference_tolerance',
                         'answer_text','answer_values_json','answer_unit','abstained','parse_status',
                         'sources_json','review_status','scientific_cause')
            else:
                raise ValidationError('No observations for '+str(path))
            atomic_csv(path,rows,columns,replace=replace)
    if paired_plots_dir is not None:
        _plots(questions,paired_plots_dir)
    return dict(paired_reporting_milestone='0.6.7.8 - PAIRED_THREE_ARM_ERROR_AND_EFFICIENCY_ANALYSIS',
                overall_results_csv=str(overall_csv) if overall_csv else None,
                mcp_ab_summary_csv=str(mcp_ab_summary_csv) if mcp_ab_summary_csv else None,
                paired_questions_csv=str(paired_questions_csv) if paired_questions_csv else None,
                paired_comparison_summary_csv=str(paired_summary_csv) if paired_summary_csv else None,
                mismatch_audit_csv=str(mismatch_audit_csv) if mismatch_audit_csv else None,
                paired_plots=[str(p) for p in paired_plot_paths(paired_plots_dir)] if paired_plots_dir else [],
                mismatch_records=len(mismatches),paired_comparison_summary=summary,
                caveat='Reference-snapshot agreement; reference answers require independent science review.')
