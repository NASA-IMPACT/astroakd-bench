"""Auditable, question-aware comparison against saved *archive* reference evidence.

This is archive-reference answer scoring, not externally adjudicated scientific truth.
No MCP/OpenAI calls; only the source journal and independent references are read.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re

ARMS = ('mcp_only', 'mcp_instruction', 'web_only')
LABELS = ('A: MCP only', 'B: AstroAKD', 'C: Web only')
EXCLUDE_FLAGS = {'incomplete_truncated_response', 'missing_expected_field',
 'missing_or_empty_reference', 'null_measurements', 'observed_values_preview_capped_at_100', 'multiple_tables'}
NUMBER = re.compile(r'(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])')


def _read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def _text(value):
    return ' '.join(str(value).casefold().split())


def _number(value):
    try:
        if isinstance(value, bool): return None
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _same(a, b, *, coord=False, field=''):
    x,y=_number(a),_number(b)
    if x is not None and y is not None:
        if field.lower() in {'obsid','source_id','designation','bibcode'}:
            return str(a).strip()==str(b).strip()
        if coord:
            return abs((x-y+180)%360-180) <= 1e-5 if field.lower() in ('ra','raj2000') else abs(x-y)<=1e-5
        # Account for 3-decimal human-rendered magnitudes and floating-point table types.
        return math.isclose(x,y,rel_tol=2e-5,abs_tol=0.0011)
    return _text(a)==_text(b)


def _tokens(v, n, fields):
    """Interpret one structured row, optionally with field-labelled text.

    Do not extract arbitrary embedded source IDs as measurement numbers.
    """
    if isinstance(v, (tuple,list)) and len(v)==n: return list(v)
    if isinstance(v,dict):
        out=[v.get(f) for f in fields]
        return out if all(x is not None for x in out) else None
    if not isinstance(v,str):return None
    # Named value pairs are used by common agent formatter ('Jmag=...', 'pmra=...').
    named=[]
    for f in fields:
        m=re.search(r'(?<![a-z0-9_])'+re.escape(f)+r'\s*[:=]\s*('+NUMBER.pattern+r')',v,re.I)
        if m is None and f.lower().endswith('mag'):
            m=re.search(r'(?<![a-z0-9_])'+re.escape(f[:-3])+r'\s*[:=]\s*('+NUMBER.pattern+r')',v,re.I)
        if m is None: break
        named.append(m.group(1))
    if len(named)==n:return named
    # Comma/whitespace-delimited values only if no labels/IDs are intermixed.
    if re.fullmatch(r'[\s,;()\[\]0-9eE.+\-]+',v):
        found=NUMBER.findall(v)
        if len(found)==n:return found
    return None


def _group(values, shape):
    fields=list(dict.fromkeys(str(v.get('field','')) for v in values))
    if not fields or any(v.get('value') is None for v in values): return None
    if shape in ('single_value','record_list'):
        return [v['value'] for v in values] if len(fields)==1 else None
    rows=defaultdict(dict)
    for item in values:
        key=(item.get('table_index',0),item.get('row_index',0))
        f=item.get('field','')
        if f in rows[key]:return None
        rows[key][f]=item['value']
    if any(set(row)!=set(fields) for row in rows.values()):return None
    return fields,[list(row[f] for f in fields) for _,row in sorted(rows.items())]


def _pairs_equal(ref, pred, fields, *, coord=False):
    return all(_same(x,y,coord=coord,field=f) for x,y,f in zip(ref,pred,fields))


def _max_pairing(expected,pred,fields,*,coord=False):
    # Bipartite matching preserves repeated records and avoids greedy collisions.
    adj=[[i for i,r in enumerate(pred) if _pairs_equal(e,r,fields,coord=coord)] for e in expected]
    assigned={}
    def augment(k,seen):
        for j in adj[k]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or augment(assigned[j],seen):
                assigned[j]=k;return True
        return False
    return sum(augment(k,set()) for k in range(len(expected)))


def _unit_compatible(answer, fields):
    """Check explicitly declared measurement units where the requested field has a known unit.

    No unit inference is made from prose, and no numeric conversion is invented.
    Missing unit metadata remains neutral; unit-sensitive gold validation is separate.
    """
    raw=answer.get('unit')
    if raw is None or not isinstance(raw,str) or not raw.strip():return True
    unit=raw.casefold().replace(' ','')
    f={x.casefold().split(':')[-1] for x in fields}
    units=[]
    for name in f:
        if name in {'ra','dec','raj2000','dej2000'}:units.append('deg')
        elif name in {'jmag','hmag','kmag','phot_g_mean_mag'}:units.append('mag')
        elif name in {'pmra','pmdec'}:units.append('mas/yr')
        elif name in {'parallax'}:units.append('mas')
        elif name in {'duration','exposure','t_exptime'}:units.append('s')
    if not units or len(set(units))!=1:return True
    canonical=units[0]
    if canonical=='deg':return unit.startswith(('deg','degree')) or 'degree' in unit
    if canonical=='mag':return unit.startswith('mag')
    if canonical=='mas/yr':return unit.startswith(('mas/yr','masyr'))
    if canonical=='mas':return unit=='mas'
    if canonical=='s':return unit in {'s','sec','second','seconds'}
    return True


def compare_answer(shape,evidence, answer, task):
    """Return (classification, matched_entries, expected_entries, reason)."""
    if not isinstance(answer,dict):return ('incorrect',0,len(evidence),'missing_structured_answer')
    if answer.get('abstained') is True:return ('abstained',0,len(evidence),'agent_abstained')
    vals=answer.get('answer_values')
    if not isinstance(vals,list) or not vals:return ('incorrect',0,len(evidence),'missing_answer_values')
    if not _unit_compatible(answer,[v.get('field','') for v in evidence]):
        return ('incorrect',0,len(evidence),'explicit_unit_mismatch')
    expected=evidence if shape=='multi_archive_values' else _group(evidence,shape)
    if expected is None:return ('not_evaluable',0,0,'unsupported_or_incomplete_reference')
    if shape in ('single_value','record_list'):
        fields=[evidence[0]['field']]
        exp=[[x] for x in expected]
        pred=[[v] for v in vals]
        if len(fields)==1 and _number(expected[0]) is not None:
            normalized=[]
            for v in vals:
                if isinstance(v,str) and ':' in v and re.fullmatch(r'\s*[^:]+:\s*'+NUMBER.pattern+r'\s*',v):
                    normalized.append([v.rsplit(':',1)[1].strip()])
                else:normalized.append([v])
            pred=normalized
        # Statuses are often requested as *distinct values*, not per-row counts.
        question=task.get('question','').lower();field=fields[0].lower()
        distinct = (('distinct' in question or 'unique' in question) or
                    (field in ('status','obs_status') and ('status values' in question or 'status value(s)' in question or 'statuses' in question or 'what status' in question)))
        if distinct:
            exp=[[x] for x in dict.fromkeys(map(str,expected))]
            pred=[[x] for x in dict.fromkeys(map(str,vals))]
        matches=_max_pairing(exp,pred,fields)
    elif shape=='multi_archive_values':
        fields=[e.get('field','') for e in evidence]
        exp=[[e['value']] for e in evidence]
        pred=[[v] for v in vals]
        # Archive-prefix is provenance; compare the requested scalar values only.
        matches=_max_pairing(exp,pred,[''])*1
    else:
        fields,exp=expected
        n=len(fields)
        if shape in ('vector','coordinate_pair'):
            if len(exp)!=1:return ('not_evaluable',0,0,'ambiguous_vector_rows')
            if len(vals)==n:
                pred=[[NUMBER.search(v).group(0) if isinstance(v,str) and NUMBER.search(v) and re.search(r'[:=]',v) else v for v in vals]]
            elif len(vals)==1 and (parsed:=_tokens(vals[0],n,fields)) is not None:pred=[parsed]
            else:pred=[]
        else:
            pred=[]
            if len(vals)==len(exp)*(n+1) and all(isinstance(vals[i*(n+1)],str) for i in range(len(exp))):
                # Explicit per-source ID followed by exactly n requested measurements.
                pred=[list(vals[i*(n+1)+1:(i+1)*(n+1)]) for i in range(len(exp))]
            elif len(vals)==n*len(exp) and all(not isinstance(v,(dict,list)) for v in vals):
                pred=[list(vals[i:i+n]) for i in range(0,len(vals),n)]
            else:
                for v in vals:
                    parsed=_tokens(v,n,fields)
                    if parsed is not None:pred.append(parsed)
                # Unparsable records are omissions, never presumed correct.
        matches=_max_pairing(exp,pred,fields,coord=shape.startswith('coordinate'))
    count=len(exp)
    if matches==count and len(pred)==count:return ('correct',matches,count,'full_reference_agreement')
    if matches>0:return ('partially_correct',matches,count,'incomplete_or_extra_values')
    return ('incorrect',0,count,'values_do_not_match')


def _single_evidence(task,ref):
    flags=set(filter(None,ref.get('review_flags','').split(';')))
    if flags & EXCLUDE_FLAGS:return None,'reference_flags:'+','.join(sorted(flags & EXCLUDE_FLAGS))
    if ref.get('reference_disposition')!='accepted_nonempty':return None,'reference_unavailable'
    if str(ref.get('truncated','')).lower()=='true':return None,'truncated_reference'
    shape=ref.get('answer_shape','')
    if shape not in {'single_value','record_list','coordinate_pair','coordinate_pair_list','vector','vector_list'}:
        return None,'unsupported_answer_shape:'+shape
    try:evidence=json.loads(ref.get('reference_answer_values_json','[]'))
    except (ValueError,TypeError):return None,'invalid_reference_json'
    if not evidence or _group(evidence,shape) is None:return None,'incomplete_reference_values'
    return (shape,evidence),None


def score_automated(tasks_path, runs_path, references_review_csv, output_dir, *,
                    multistep_path=None, plots=True, replace=False):
    tasks_path,runs_path=Path(tasks_path),Path(runs_path)
    refs_path=Path(references_review_csv)
    output_dir=Path(output_dir)
    tasks=_read_jsonl(tasks_path); runs=_read_jsonl(runs_path)
    digest=hashlib.sha256(tasks_path.read_bytes()).hexdigest()
    if len({t['id'] for t in tasks})!=len(tasks):raise ValueError('Duplicate task ID')
    run_map={}
    for r in runs:
        key=r.get('task_id'),r.get('arm')
        if r.get('candidate_sha256')!=digest or key in run_map or key[0] not in {t['id'] for t in tasks} or key[1] not in ARMS:
            raise ValueError('Duplicate runs or mismatched dataset SHA-256')
        run_map[key]=r
    if not refs_path.is_file():raise FileNotFoundError(refs_path)
    with refs_path.open(newline='',encoding='utf-8') as f:
        refs=list(csv.DictReader(f))
    ref_map={r['task_id']:r for r in refs}
    if len(ref_map)!=len(refs):raise ValueError('Duplicate reference IDs')
    multimap={}
    if multistep_path is not None and Path(multistep_path).is_file():
        for r in _read_jsonl(multistep_path):
            if r.get('dataset_sha256')!=digest:raise ValueError('Multi-step reference SHA-256 mismatch')
            if r['task_id'] in multimap:raise ValueError('Duplicate multi-step reference ID')
            multimap[r['task_id']]=r
    rows=[];exclusions=Counter();results=defaultdict(Counter); archive_results=defaultdict(lambda:defaultdict(Counter));family_results=defaultdict(lambda:defaultdict(Counter))
    for task in tasks:
        tid=task['id']; arch=task.get('module','unknown');family=task.get('task_type','unknown')
        if tid in ref_map:spec,reason=_single_evidence(task,ref_map[tid])
        elif tid in multimap:
            record=multimap[tid]
            reason=record.get('status','missing_multistep_evidence')
            spec=None
            if reason=='complete' and isinstance(record.get('answer_evidence'),list):
                shape=record.get('answer_shape','')
                if shape in {'single_value','record_list','vector','vector_list','coordinate_pair','coordinate_pair_list','multi_archive_values'}:
                    spec=(shape,record['answer_evidence']);reason=None
        else:spec,reason=None,'no_independent_multistep_reference' if family in ('literature_driven','multi_archive') else 'missing_reference'
        if reason:exclusions[reason]+=1
        row={'task_id':tid,'task_type':family,'archive':arch,'evaluable':'no' if reason else 'yes','exclusion_reason':reason or '',
             'reference_shape':spec[0] if spec else ''}
        for arm in ARMS:
            r=run_map.get((tid,arm))
            if reason:category='not_evaluable';matched=0;total=0;why=reason
            elif r is None:category='failed';matched=0;total=len(spec[1]);why='missing_run'
            elif r.get('status')!='completed':category='failed';matched=0;total=len(spec[1]);why='agent_execution_error'
            else:category,matched,total,why=compare_answer(spec[0],spec[1],r.get('answer'),task)
            row[arm+'_classification']=category
            row[arm+'_matched_entries']=matched;row[arm+'_expected_entries']=total
            row[arm+'_reason']=why
            if not reason:
                results[arm][category]+=1
                archive_results[arch][arm][category]+=1
                family_results[family][arm][category]+=1
        rows.append(row)
    if not replace and any((output_dir/f).exists() for f in ('automated_scoring_summary.json','automated_scores_per_question.csv')):
        raise FileExistsError(f'{output_dir}: scoring output already exists; pass --replace')
    output_dir.mkdir(parents=True,exist_ok=True)
    with (output_dir/'automated_scores_per_question.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    denominator=len(tasks)-sum(exclusions.values())
    def arm_rates(counts):
        return {a:{'correct':counts[a]['correct'],'partially_correct':counts[a]['partially_correct'],
           'incorrect':counts[a]['incorrect'],'abstained':counts[a]['abstained'],'failed':counts[a]['failed'],
           'evaluable':sum(counts[a].values()),
           'strict_match_pct':round(100*counts[a]['correct']/sum(counts[a].values()),2) if sum(counts[a].values()) else None}
            for a in ARMS}
    summary={'milestone':'0.6.7.11.11 - AUTOMATED_REFERENCE_ANSWER_SCORING',
        'status':'NOT_SCORABLE' if denominator==0 else ('COMPLETE' if denominator==len(tasks) else 'PARTIAL_REFERENCE_COVERAGE'),
        'metric':'AUTOMATED_ARCHIVE_REFERENCE_ANSWER_AGREEMENT_NOT_INDEPENDENT_SCIENTIFIC_GOLD',
        'dataset_sha256':digest,'runs_sha256':hashlib.sha256(runs_path.read_bytes()).hexdigest(),
        'references_sha256':hashlib.sha256(refs_path.read_bytes()).hexdigest(),
        'total_questions':len(tasks),'evaluable_questions':denominator,
        'excluded_questions':len(tasks)-denominator,'exclusion_reasons':dict(sorted(exclusions.items())),
        'arms':arm_rates(results),
        'by_archive':{key:arm_rates(value) for key,value in sorted(archive_results.items())},
        'by_question_type':{key:arm_rates(value) for key,value in sorted(family_results.items())},
        'scoring_policy':{'numeric_relative_tolerance':2e-5,'numeric_absolute_tolerance':0.0011,
            'coordinate_tolerance_deg':1e-5,'list_semantics':'duplicate-aware, order-independent',
            'statuses':'distinct values only when question requests statuses as a set',
            'multi_field':'complete tuples by row; no cross-row mixing'},
        'note':'Automatic agreement to observed archive values; no manual gold approval or external scientific verification is implied.'}
    (output_dir/'automated_scoring_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (output_dir/'accuracy_breakdown.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['grouping','group','arm','correct','partially_correct','incorrect','abstained','failed','evaluable','strict_match_pct'])
        w.writeheader()
        for grouping,groups in [('archive',summary['by_archive']),('question_type',summary['by_question_type'])]:
            for group,arms in groups.items():
                for arm,data in arms.items():w.writerow({'grouping':grouping,'group':group,'arm':arm,**data})
    if plots and denominator:
        from matplotlib import pyplot as plt
        def draw(name,title,groups):
            labels=list(groups)
            fig,ax=plt.subplots(figsize=(max(9,len(labels)*1.7),5.6))
            xs=list(range(len(labels)))
            for i,arm in enumerate(ARMS):
                rates=[groups[l][arm]['strict_match_pct'] or 0 for l in labels]
                ax.bar([x+(i-1)*.24 for x in xs],rates,width=.24,label=LABELS[i])
            ax.set_xticks(xs,labels,rotation=15 if len(labels)>3 else 0,ha='right' if len(labels)>3 else 'center')
            ax.set_ylim(0,105);ax.set_ylabel('Strict reference-answer agreement (%)')
            ax.set_title(title);ax.legend(fontsize=9)
            fig.text(.5,.015,f'Automatic archive-reference agreement • {denominator}/{len(tasks)} evaluable; not independent scientific gold',ha='center',fontsize=8,color='0.35')
            fig.tight_layout(rect=(0,.04,1,1))
            for ext in ('.png','.svg'):fig.savefig(output_dir/(name+ext),dpi=175)
            plt.close(fig)
        draw('match_rate','Question-aware reference-answer agreement',{'All evaluable':summary['arms']})
        draw('accuracy_by_archive','Reference agreement by archive',summary['by_archive'])
        draw('accuracy_by_question_type','Reference agreement by question type',summary['by_question_type'])
    summary['output_dir']=str(output_dir)
    return summary
