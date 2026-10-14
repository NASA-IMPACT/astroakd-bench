"""0.6.6.1 offline answer-review CSV qualification."""
import csv
import json
from pathlib import Path
import pytest
from benchmark.answer_reports import export_answer_csv
from benchmark.validator import load_jsonl, ValidationError


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, separators=(',', ':'), sort_keys=True)+'\n' for r in rows))
    return load_jsonl(path)[1]


def sample(tmp_path):
    tasks=tmp_path/'tasks.jsonl'
    rows=[{'id':'ONE','task_type':'archive_driven','module':'simbad','target':'NGC 1275',
           'question':'Where is NGC 1275 in ICRS?','answer_spec':{'expected_columns':['ra']}},
          {'id':'TWO','task_type':'literature_driven','module':'heasarc','target':'PG 1211+143',
           'question':'Which paper reports PG 1211+143?','answer_spec':{'expected_columns':[]}}]
    digest=write_jsonl(tasks,rows)
    refs=tmp_path/'refs.jsonl';ref_tasks=tmp_path/'ref_tasks.jsonl'
    ref_sha=write_jsonl(ref_tasks,rows[:1]);write_jsonl(refs,[{
        'task_id':'ONE','input_dataset_sha256':ref_sha,'disposition':'accepted_nonempty',
        'evaluation':{'checks':{'returned_rows':1,'reported_total_rows':1,'truncated':False}},
        'response':{'result':{'columns':[{'name':'ra'}],'data':[{'ra':49.9506}]}}}])
    runs=tmp_path/'runs.progress.jsonl'
    records=[]
    for arm,ans in [('mcp_only',{'answer':'NGC1275 RA 49.9506','answer_values':[49.9506], 'unit':'deg', 'sources':[], 'abstained':False,'parse_status':'structured'}),
                    ('mcp_instruction',{'answer':'=exposed formula','answer_values':None,'sources':[], 'abstained':False,'parse_status':'unstructured'}),
                    ('web_only',{'answer':'Text response','answer_values':None,'sources':[], 'abstained':False,'parse_status':'unstructured'})]:
        records.append({'task_id':'ONE','arm':arm,'candidate_sha256':digest,'status':'completed',
                        'answer':ans,'trace':[{'tool':'openai_web_search','web_search_calls':1}] if arm=='web_only' else [],
                        'duration_seconds':1.5,'token_usage':{'total_tokens':100}, 'successful_mcp_queries':1 if arm=='mcp_only' else 0})
    write_jsonl(runs,records)
    return tasks,refs,ref_tasks,runs,digest


def call(tmp_path,*args,**kwargs):
    return export_answer_csv(args[0],tmp_path/'q.csv',tmp_path/'a.csv',tmp_path/'s.csv',tmp_path/'report.json',
                             runs=args[3],references=args[1],reference_tasks=args[2],
                             reference_values_csv=tmp_path/'values.csv',per_arm_dir=tmp_path/'split',**kwargs)


def csv_rows(path):
    with path.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def test_unverified_scientific_rate_stays_blank_and_all_answers_visible(tmp_path):
    args=sample(tmp_path)
    report=call(tmp_path,*args[:4]);assert report['tasks']==2 and report['reference_observed_values']==1
    qs=csv_rows(tmp_path/'q.csv');assert len(qs)==2 and qs[0]['reference_candidate_value_count']=='1'
    assert '49.9506' in qs[0]['reference_candidate_values_json']
    assert qs[0]['gold_status']=='not_provided' and qs[0]['A_scientific_success']==''
    assert qs[1]['A_run_status']=='not_run'
    arms=csv_rows(tmp_path/'a.csv'); assert len(arms)==6
    assert len(csv_rows(tmp_path/'split'/'B_mcp_instruction_answers.csv'))==2
    assert next(r for r in arms if r['arm']=='mcp_instruction')['answer'].startswith("'=exposed")
    summary=csv_rows(tmp_path/'s.csv')
    assert summary[0]['completion_rate_attempted_pct']=='100.0'
    assert summary[0]['coverage_all_questions_pct']=='50.0'
    assert summary[0]['scientific_success_rate_pct']==''
    assert len(csv_rows(tmp_path/'values.csv'))==1


def test_approved_gold_independent_scoring(tmp_path):
    tasks,refs,ref_tasks,runs,digest=sample(tmp_path)
    gold=tmp_path/'gold.jsonl'
    rows=[{'task_id':'ONE','input_dataset_sha256':digest,'question':'Where is NGC 1275 in ICRS?',
           'gold_status':'verified','question_review':'approved','reviewer':'Science team',
           'gold':{'kind':'numeric','values':[49.9506],'unit':'deg','absolute_tolerance':0.001},
           'sources':[{'uri':'https://simbad.cds.unistra.fr/record','description':'verified archive'},
                      {'uri':'https://www.iau.org/record','description':'cross-check'}]},
          {'task_id':'TWO','input_dataset_sha256':digest,'question':'Which paper reports PG 1211+143?',
           'gold_status':'pending','question_review':'pending','gold':None}]
    write_jsonl(gold,rows)
    report=call(tmp_path,tasks,refs,ref_tasks,runs,gold=gold)
    assert report['arms']['mcp_only']['scientifically_scored']==1
    assert report['arms']['mcp_only']['scientific_success_rate_pct']==100.0
    assert report['arms']['web_only']['scientific_success_rate_pct'] is None


def test_invalid_dataset_binding_is_rejected(tmp_path):
    tasks,refs,ref_tasks,runs,digest=sample(tmp_path)
    records=[json.loads(line) for line in runs.read_text().splitlines()];records[0]['candidate_sha256']='wrong'
    write_jsonl(runs,records)
    with pytest.raises(ValidationError,match='dataset'):
        call(tmp_path,tasks,refs,ref_tasks,runs)
    assert not (tmp_path/'q.csv').exists()


def test_export_never_overwrites_implicitly(tmp_path):
    args=sample(tmp_path);call(tmp_path,*args[:4])
    with pytest.raises(ValidationError,match='exists'):
        call(tmp_path,*args[:4])
