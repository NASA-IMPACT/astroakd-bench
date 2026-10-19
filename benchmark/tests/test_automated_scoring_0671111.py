"""Science/completeness behavior for the independent archive-reference comparator."""
import asyncio
import csv
import hashlib
import json
from pathlib import Path

import pytest

from benchmark.automated_scoring import compare_answer, score_automated
from benchmark.multistep_reference import collect_multistep


def evidence(rows, fields):
    return [{'field':field,'row_index':i,'table_index':0,'value':row[j]}
            for i,row in enumerate(rows) for j,field in enumerate(fields)]


def test_vectors_named_rounding_and_row_multiplicity():
    spec=evidence([[11.735,11.07,10.035],[14.0,13.0,12.0]],['Jmag','Hmag','Kmag'])
    ans={'answer_values':['2MASS J0001: J=11.735 H=11.070 K=10.035','2MASS J0002: J=14.000 H=13.000 K=12.000']}
    assert compare_answer('vector_list',spec,ans,{'question':'List magnitudes'})[0]=='correct'
    assert compare_answer('vector_list',spec,{'answer_values':ans['answer_values'][:1]}, {})[0]=='partially_correct'
    # Mixing J, H, K across different source rows must never give full credit.
    swapped={'answer_values':['J=11.735 H=13.000 K=10.035','J=14.000 H=11.070 K=12.000']}
    assert compare_answer('vector_list',spec,swapped,{})[0]!='correct'


def test_coordinates_and_identifiers():
    coords=evidence([[359.999,42.12345]],['RAJ2000','DEJ2000'])
    assert compare_answer('coordinate_pair',coords,{'answer_values':[359.999004,42.123449]}, {})[0]=='correct'
    assert compare_answer('coordinate_pair',coords,{'answer_values':[359.9,42.12345]}, {})[0]=='incorrect'
    ids=evidence([['00123'],['00123'],['00456']],['obsid'])
    assert compare_answer('record_list',ids,{'answer_values':['00123','00456']},{'question':'List each ObsID'})[0]=='partially_correct'
    assert compare_answer('record_list',ids,{'answer_values':['123','00123','00456']},{'question':'List each ObsID'})[0]!='correct'


def test_status_distinct_requested_only():
    statuses=evidence([['archived'],['archived'],['observed']],['status'])
    values={'answer_values':['archived','observed']}
    assert compare_answer('record_list',statuses,values,{'question':'What distinct status values occur?'})[0]=='correct'
    assert compare_answer('record_list',statuses,values,{'question':'List status for each row'})[0]=='partially_correct'
    assert compare_answer('record_list',statuses,{'abstained':True,'answer_values':['archived']}, {})[0]=='abstained'


def test_scoring_without_api_and_with_nonempty_denominator(tmp_path):
    root=tmp_path/'datasets';(root/'generated').mkdir(parents=True);(root/'agent').mkdir();(root/'validated').mkdir()
    tasks=[{'id':'T1','question':'Which statuses occur?','module':'heasarc','task_type':'archive_driven'},
           {'id':'T2','question':'literature','module':'heasarc','task_type':'literature_driven'}]
    tpath=root/'generated/x.jsonl';tpath.write_text(''.join(json.dumps(t)+'\n' for t in tasks))
    sha=hashlib.sha256(tpath.read_bytes()).hexdigest()
    runs=[{'task_id':'T1','arm':arm,'candidate_sha256':sha,'status':'completed',
           'answer':{'answer_values':['archived']}} for arm in ('mcp_only','mcp_instruction','web_only')]
    rpath=root/'agent/x_ABC_runs.jsonl';rpath.write_text(''.join(json.dumps(t)+'\n' for t in runs))
    refs=root/'validated/x_references_review.csv'
    with refs.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['task_id','answer_shape','reference_answer_values_json','reference_disposition','review_flags','truncated']);w.writeheader()
        w.writerow({'task_id':'T1','answer_shape':'single_value','reference_answer_values_json':json.dumps(evidence([['archived']],['status'])),'reference_disposition':'accepted_nonempty'})
    result=score_automated(tpath,rpath,refs,tmp_path/'scores',plots=False)
    assert result['evaluable_questions']==1
    assert result['excluded_questions']==1
    assert result['arms']['mcp_only']['strict_match_pct']==100
    assert (tmp_path/'scores/automated_scores_per_question.csv').exists()
    with pytest.raises(FileExistsError):score_automated(tpath,rpath,refs,tmp_path/'scores',plots=False)


class FakeClient:
    def __init__(self):self.calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*x):pass
    async def call(self,name,args):
        self.calls.append((name,args))
        field='main_id' if args['module_name']=='simbad' else 'phot_g_mean_mag'
        return {'success':True,'result':{'columns':[{'name':field}], 'data':[{field:'NGC 2682' if field=='main_id' else 17.3}]}}


def test_multistep_journal_resume_and_no_fabrication(tmp_path):
    root=tmp_path/'datasets';(root/'generated').mkdir(parents=True)
    task={'id':'M1','task_type':'multi_archive','constraints':{'multi_archive_steps':[
        {'module':m,'expected_columns':[f],'reference_call':{'tool':'astroquery_execute','arguments':{'module_name':m,'function_name':'query_object','params':{'object_name':'M67'}}}}
        for m,f in [('simbad','main_id'),('gaia','phot_g_mean_mag')]]}}
    literature={'id':'L1','task_type':'literature_driven','research_evidence':{'bibcodes':['2022yCat..22620014B']}}
    tasks=[task,literature]
    (root/'generated/x.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in tasks))
    (root/'generated/x_multistep.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in tasks))
    fake=FakeClient()
    first=asyncio.run(collect_multistep(name='x',output_dir=root,limit=1,client_factory=lambda:fake))
    assert first['tasks_recorded']==1 and first['reference_complete']==1 and len(fake.calls)==2
    second=asyncio.run(collect_multistep(name='x',output_dir=root,resume=True,client_factory=lambda:fake))
    assert second['tasks_recorded']==2 and len(fake.calls)==2
    assert second['dispositions']['needs_independent_archive_query_plan']==1
    rows=[json.loads(x) for x in (root/'validated/x_multistep_references.jsonl').read_text().splitlines()]
    assert rows[0]['status']=='complete' and len(rows[0]['answer_evidence'])==2
    assert rows[1]['status']!='complete'
    with pytest.raises(FileExistsError):asyncio.run(collect_multistep(name='x',output_dir=root,client_factory=lambda:fake))
