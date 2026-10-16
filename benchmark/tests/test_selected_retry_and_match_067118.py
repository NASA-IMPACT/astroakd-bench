"""0.6.7.11.8: immutable selective retries and honest snapshot match plotting."""
import asyncio
import csv
import hashlib
import json
from pathlib import Path

import pytest
from benchmark.selected_retry import retry_failed_mcp
from benchmark.reference_agreement import reference_snapshot_agreement


def _jsonl(p,records):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in records),encoding='utf-8')


def _fixture(tmp_path):
    tasks=tmp_path/'generated/test.jsonl'
    _jsonl(tasks,[{'id':'TEST-1','question':'What identifier?','task_type':'archive_driven','module':'simbad','reference_call':{'tool':'astroquery_execute','arguments':{'module_name':'simbad','function_name':'query_object','params':{'object_name':'M31'}}}},
                  {'id':'TEST-2','question':'What position?','task_type':'coordinate_driven','module':'simbad','reference_call':{'tool':'astroquery_execute','arguments':{'module_name':'simbad','function_name':'query_object','params':{'object_name':'M82'}}}}])
    sha=hashlib.sha256(tasks.read_bytes()).hexdigest()
    runs=tmp_path/'agent/test_ABC_runs.jsonl'; rec=[]
    for tid in ('TEST-1','TEST-2'):
        for arm in ('mcp_only','mcp_instruction','web_only'):
            status='error' if arm=='mcp_only' else 'completed'
            rec.append({'task_id':tid,'arm':arm,'candidate_sha256':sha,'model':'gpt-5.2',
                        'status':status,'answer':{'answer_values':['M 31'],'abstained':False},
                        'trace':[],'error':None if status=='completed' else {'type':'AgentRunError'}})
    _jsonl(runs,rec)
    review=tmp_path/'validated/test_references_review.csv';review.parent.mkdir(parents=True)
    with review.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['task_id','answer_shape','review_flags','truncated',
           'reference_disposition','reference_answer_values_json','gold_status'])
        w.writeheader()
        w.writerow({'task_id':'TEST-1','answer_shape':'single_value','review_flags':'',
          'truncated':'False','reference_disposition':'accepted_nonempty','gold_status':'pending',
          'reference_answer_values_json':json.dumps([{'field':'MAIN_ID','value':'M 31'}])})
        w.writerow({'task_id':'TEST-2','answer_shape':'record_list','review_flags':'incomplete_truncated_response',
          'truncated':'True','reference_disposition':'accepted_nonempty','gold_status':'pending',
          'reference_answer_values_json':json.dumps([{'field':'id','value':'M82'}])})
    return tasks,runs,review,sha


def test_offline_retry_selection_immutable(tmp_path):
    tasks,runs,_,sha=_fixture(tmp_path)
    original=runs.read_bytes()
    r=asyncio.run(retry_failed_mcp(tasks_path=tasks,runs_path=runs,
        output_dir=runs.parent,dry_run=True))
    assert r['task_ids']==['TEST-1','TEST-2'] and r['retry_count']==2
    assert original==runs.read_bytes() and not Path(r['retry_output']).exists()

    async def fake_run(task,digest,old,*,args,sdk):
        return {**old,'status':'completed','error':None,
                'answer':{'answer_values':['M 31'],'abstained':False},
                'diagnostic_retry':{'max_turns':args.max_turns,'max_calls':args.max_calls}}
    result=asyncio.run(retry_failed_mcp(tasks_path=tasks,runs_path=runs,
         output_dir=runs.parent, max_turns=16,max_calls=20,sdk=object(),run_one=fake_run))
    assert result['retry_completed']==2
    assert original==runs.read_bytes()
    retries=[json.loads(x) for x in Path(result['retry_output']).read_text().splitlines()]
    derived=[json.loads(x) for x in Path(result['diagnostic_runs']).read_text().splitlines()]
    assert len(retries)==2 and len(derived)==6
    assert sum(r['status']=='completed' for r in derived)==6
    assert all(r['diagnostic_retry']['max_turns']==16 for r in retries)
    with pytest.raises(FileExistsError):
        asyncio.run(retry_failed_mcp(tasks_path=tasks,runs_path=runs,output_dir=runs.parent,dry_run=False,sdk=object(),run_one=fake_run))


def test_reference_snapshot_agreement_excludes_unreviewed_complex(tmp_path):
    tasks,runs,review,_=_fixture(tmp_path)
    summary=reference_snapshot_agreement(tasks,runs,review,tmp_path/'reports',plots=False)
    assert summary['denominator']==1
    assert summary['rates_pct']=={'mcp_only':0.0,'mcp_instruction':100.0,'web_only':100.0}
    assert summary['scientific_accuracy']=='NOT_ASSESSED'
    assert not (tmp_path/'reports/match_rate.png').exists()
    rows=list(csv.DictReader((tmp_path/'reports/reference_agreement_per_question.csv').open()))
    assert rows[1]['scorable']=='no'


def test_reference_agreement_no_gold_does_not_fabricate_plot(tmp_path):
    tasks,runs,review,_=_fixture(tmp_path)
    review.write_text(review.read_text().replace('single_value','vector_list'))
    r=reference_snapshot_agreement(tasks,runs,review,tmp_path/'reports',plots=False)
    assert r['status']=='NOT_SCORABLE'
    assert not (tmp_path/'reports/reference_agreement_summary.json').exists()


def test_retry_refuses_nonfailed_and_model_mismatch(tmp_path):
    tasks,runs,_,sha=_fixture(tmp_path)
    with pytest.raises(ValueError,match='Invalid or duplicate'):
        asyncio.run(retry_failed_mcp(tasks_path=tasks,runs_path=runs,output_dir=runs.parent,
            task_ids=['TEST-1','TEST-3'],dry_run=True))
    with pytest.raises(ValueError,match='model'):
        asyncio.run(retry_failed_mcp(tasks_path=tasks,runs_path=runs,output_dir=runs.parent,
            model='another-model',dry_run=True))
