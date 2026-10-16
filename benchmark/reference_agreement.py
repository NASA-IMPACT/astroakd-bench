"""Conservative, *unreviewed* archive-reference snapshot agreement.

This metric is not scientific accuracy. Only complete single-column fields and
single coordinate pairs can be compared automatically; all exclusions reported.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path

ARMS = ('mcp_only', 'mcp_instruction', 'web_only')
LABELS = ('A — MCP only', 'B — MCP + Instruction', 'C — Web only')
DISQUALIFY = {'incomplete_truncated_response','missing_expected_field',
              'missing_or_empty_reference','null_measurements',
              'observed_values_preview_capped_at_100','multiple_tables',
              'structured_multi_field_response'}
SHAPES = {'single_value','record_list','coordinate_pair'}


def _scalar(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (float,int,Decimal)):
        try:
            d=Decimal(str(value))
            return ('number',d) if d.is_finite() else None
        except InvalidOperation:
            return None
    text=' '.join(str(value).casefold().split())
    if not text: return None
    return ('text',text)


def _compare_scalar(reference, prediction):
    a,b=_scalar(reference),_scalar(prediction)
    if a is None or b is None: return False
    if a[0]=='number' and b[0]=='number':
        # Strict numeric serialization tolerance; do not round catalog IDs.
        return a[1]==b[1]
    return a==b


def _matches(shape, expected, answer):
    if not isinstance(answer,dict) or answer.get('abstained') is True:
        return False
    vals=answer.get('answer_values')
    if not isinstance(vals,list): return False
    if shape=='single_value':
        return len(expected)==len(vals)==1 and _compare_scalar(expected[0],vals[0])
    if shape=='coordinate_pair':
        if len(expected)!=2 or len(vals)!=2: return False
        try:
            pred=list(map(float,vals)); ref=list(map(float,expected))
            return (all(math.isfinite(v) for v in pred+ref)
                    and abs((pred[0]-ref[0]+180)%360-180)<=1e-5
                    and abs(pred[1]-ref[1])<=1e-5)
        except (TypeError,ValueError,OverflowError): return False
    if shape=='record_list':
        if len(vals)!=len(expected): return False
        # Multiset handles duplicate values and is row-order-independent.
        def key(v):
            scalar=_scalar(v)
            return (scalar[0],str(scalar[1])) if scalar is not None else None
        expected_key=[key(x) for x in expected]
        predicted_key=[key(x) for x in vals]
        return (None not in expected_key and None not in predicted_key
                and Counter(expected_key)==Counter(predicted_key))
    return False


def reference_snapshot_agreement(tasks_path:Path,runs_path:Path,review_csv:Path,
                                  output_dir:Path,*,plots=True):
    """Produce match_rate only when usable saved reference snapshots exist."""
    tasks_path,runs_path,review_csv=map(Path,(tasks_path,runs_path,review_csv))
    tasks=[json.loads(x) for x in tasks_path.read_text().splitlines() if x.strip()]
    runs=[json.loads(x) for x in runs_path.read_text().splitlines() if x.strip()]
    digest=hashlib.sha256(tasks_path.read_bytes()).hexdigest()
    known={t['id']:t for t in tasks}
    if len(known)!=len(tasks): raise ValueError('Duplicate task IDs')
    byrun={}
    for r in runs:
        key=(r.get('task_id'),r.get('arm'))
        if (key in byrun or key[0] not in known or key[1] not in ARMS
                or r.get('candidate_sha256')!=digest):
            raise ValueError('Run journal fingerprint or ID mismatch')
        byrun[key]=r
    with review_csv.open(newline='',encoding='utf-8') as f:
        refs=list(csv.DictReader(f))
    if len(refs)!=len({r['task_id'] for r in refs}):
        raise ValueError('Duplicate reference snapshot rows')
    per_question=[]; scorable=[]; excluded=Counter()
    for task in tasks:
        tid=task['id']; subset=[r for r in refs if r['task_id']==tid]
        reason='no_single_call_reference'
        if subset:
            ref=subset[0]
            reasons=set(filter(None,ref.get('review_flags','').split(';')))
            shape=ref.get('answer_shape','')
            reason=''
            if ref.get('gold_status')=='verified':
                # Still label output snapshot agreement, never transform into gold scoring.
                pass
            if shape not in SHAPES: reason='unsupported_answer_shape'
            elif reasons & DISQUALIFY: reason='reference_flags:'+';'.join(sorted(reasons & DISQUALIFY))
            elif ref.get('truncated','').lower()=='true': reason='truncated'
            elif ref.get('reference_disposition')!='accepted_nonempty': reason='empty_reference'
            elif len({(x.get('field') or '') for x in json.loads(ref['reference_answer_values_json'])})!=1 and shape!='coordinate_pair':
                reason='multiple_reference_fields'
            if not reason:
                evidence=json.loads(ref['reference_answer_values_json'])
                values=[x.get('value') for x in evidence]
                if not values or any(v is None for v in values): reason='missing_reference_values'
                elif shape=='single_value' and len(values)!=1: reason='ambiguous_single_value'
                elif shape=='coordinate_pair' and len(values)!=2: reason='malformed_coordinate_pair'
                elif any((tid,arm) not in byrun for arm in ARMS): reason='missing_agent_run'
        row={'task_id':tid,'task_type':task.get('task_type',''),
             'scorable':'no' if reason else 'yes','exclusion_reason':reason}
        for arm in ARMS:
            rec=byrun.get((tid,arm))
            row[arm+'_status']=rec.get('status','missing') if rec else 'missing'
            row[arm+'_match']=''
            if not reason:
                matched=(rec.get('status')=='completed' and _matches(shape,values,rec.get('answer') or {}))
                row[arm+'_match']=1 if matched else 0
        per_question.append(row)
        if reason: excluded[reason]+=1
        else: scorable.append(row)
    if not scorable:
        return {'status':'NOT_SCORABLE','metric':'UNREVIEWED_REFERENCE_SNAPSHOT_AGREEMENT',
                'eligible':0, 'total_questions':len(tasks),'exclusions':dict(excluded)}
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    with (output_dir/'reference_agreement_per_question.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(per_question[0])); w.writeheader();w.writerows(per_question)
    rates={arm:round(100*sum(x[arm+'_match'] for x in scorable)/len(scorable),2) for arm in ARMS}
    summary={'status':'PROVISIONAL_REVIEW_REQUIRED',
       'metric':'UNREVIEWED_REFERENCE_SNAPSHOT_AGREEMENT_NOT_SCIENTIFIC_ACCURACY',
       'dataset_sha256':digest,'source_reference_review_csv':str(review_csv),
       'denominator':len(scorable),'total_questions':len(tasks),
       'exclusions':dict(sorted(excluded.items())), 'rates_pct':rates,
       'rule':'Exact scalar or complete single-field list, or coordinate pair within 1e-5 degrees; errors/abstentions nonmatches',
       'scientific_accuracy':'NOT_ASSESSED',
       'gold_verified_in_review_csv':sum(r.get('gold_status')=='verified' for r in refs),
       'note':'Reference snapshots are not scientifically reviewed; no results on unscorable tasks are inferred.'}
    (output_dir/'reference_agreement_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if plots:
        from matplotlib import pyplot as plt
        fig,ax=plt.subplots(figsize=(9.8,5.6))
        bars=ax.bar(LABELS,[rates[a] for a in ARMS]);ax.set_ylim(0,110)
        ax.set_ylabel('% exact matches on provisional scorable snapshots')
        ax.set_title('Reference-snapshot match rate — UNREVIEWED, not scientific accuracy')
        for b,a in zip(bars,ARMS):
            ax.annotate(f'{rates[a]:.1f}%',(b.get_x()+b.get_width()/2,b.get_height()),
                       ha='center',va='bottom',xytext=(0,4),textcoords='offset points')
        fig.text(.5,.03,f'Scorable {len(scorable)}/{len(tasks)}; excluded {len(tasks)-len(scorable)}; no verified gold',
                 ha='center',color='0.35',fontsize=9)
        fig.tight_layout(rect=(0,.06,1,1))
        for suffix in ('.png','.svg'):
            fig.savefig(output_dir/('match_rate'+suffix),dpi=180)
        plt.close(fig)
    return summary
