"""0.6.7.11.12: VizieR lists, selective recovery and provenance-safe scoring."""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from benchmark.automated_scoring import compare_answer
from benchmark.multistep_reference import _extract, _payload_diagnostics, collect_multistep, write_literature_drafts


def test_vizier_table_list_two_tables_preserves_indices():
    fields=['Jmag','Hmag','Kmag']
    tab=lambda j: {'columns':[{'name':n} for n in fields],
                   'data':[{'Jmag':j,'Hmag':j-1,'Kmag':j-2}], 'row_count':1}
    evidence,reason=_extract({'success':True,'result':[tab(13.),tab(12.)]},fields,'vizier')
    assert reason is None and len(evidence)==6
    assert [x['table_index'] for x in evidence]==[0,0,0,1,1,1]
    assert _payload_diagnostics({'result':[tab(13.)]})['result_kind']=='list'
    assert _extract({'result':[dict(tab(13.),total_rows=5)]},fields,'vizier')[1]=='truncated_reference'
    assert _extract({'result':[tab(13.),{'columns':[], 'data':[{}]}]},fields,'vizier')[1]=='missing_expected_field'


def test_multifield_archive_and_strict_overcount():
    vals=[{'field':'heasarc:duration','row_index':i,'table_index':0,'value':v}
          for i,v in enumerate([14304,14304,13913,10420])]
    vals += [{'field':'simbad:matched_id','row_index':0,'table_index':0,'value':'M  33'}]
    a={'answer_values':[14304,14304,13913,10420,'M  33'],
       'unit':'s (HEASARC duration); SIMBAD matched_id is unitless'}
    assert compare_answer('multi_archive_values',vals,a,{})[0]=='correct'
    b={'answer_values':[14304,14304,13913,10420,'M  33'],
       'unit':'HEASARC duration: hour; SIMBAD matched_id: identifier string'}
    assert compare_answer('multi_archive_values',vals,b,{})[0]=='incorrect'
    obs=[{'field':'heasarc:obsid','row_index':i,'table_index':0,'value':v} for i,v in enumerate(['0961390201','0803670501'])]
    obs += [{'field':'simbad:matched_id','row_index':0,'table_index':0,'value':'M  87'}]
    assert compare_answer('multi_archive_values',obs,{'answer_values':[
        'HEASARC:xmmmaster obsid=0961390201','HEASARC:xmmmaster obsid=0803670501',
        'SIMBAD matched_id=M  87']},{})[0]=='correct'
    assert compare_answer('multi_archive_values',obs,{'answer_values':['961390201','0803670501','M 87']},{})[0]!='correct'
    assert compare_answer('multi_archive_values',obs,{'answer_values':['0961390201','0803670501','EXTRA','M 87']},{})[0]=='partially_correct'
    many=[{'field':'heasarc:obsid','row_index':i,'table_index':0,'value':v} for i,v in enumerate([11387,11388,13864,13865,2087])]
    many += [{'field':'gaia:pmra','row_index':0,'table_index':0,'value':0.005995450707960242},
             {'field':'gaia:pmdec','row_index':0,'table_index':0,'value':0.028362646307752266}]
    combined={'answer_values':['GAIA: Gaia DR3 source pmra=0.005995450707960242 mas/yr pmdec=0.028362646307752266 mas/yr',
                               'HEASARC chanmaster obsid(s): 11387, 11388, 13864, 13865, 2087']}
    assert compare_answer('multi_archive_values',many,combined,{})[0]=='correct'


def test_identical_unlabelled_values_across_archives_do_not_prove_provenance():
    vals=[{'field':'heasarc:duration','row_index':0,'table_index':0,'value':42},
          {'field':'gaia:parallax','row_index':0,'table_index':0,'value':42}]
    result=compare_answer('multi_archive_values',vals,{'answer_values':[42,42]}, {})
    assert result[0]!='correct'
    tagged={'answer_values':[{'heasarc:duration':42},{'gaia:parallax':42}]}
    assert compare_answer('multi_archive_values',vals,tagged,{})[0]=='correct'


class FakeClient:
    def __init__(self): self.calls=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def call(self,tool,args):
        self.calls.append(args['module_name'])
        if args['module_name']!='vizier':raise AssertionError('Completed step was unnecessarily repeated')
        return {'success':True,'result':[{'columns':[{'name':'Jmag'},{'name':'Hmag'},{'name':'Kmag'}],
                    'data':[{'Jmag':12.2,'Hmag':11.2,'Kmag':10.2}]}]}


def make_resume_dataset(tmp_path):
    root=tmp_path/'datasets'
    for d in ('generated','validated'): (root/d).mkdir(parents=True,exist_ok=True)
    steps=[{'module':m,'expected_columns':fields,'reference_call':{'tool':'astroquery_execute',
            'arguments':{'module_name':m,'function_name':'query_region','params':{'radius':{'unit':'arcmin','value':.1}}}}}
            for m,fields in [('simbad',['ra']),('vizier',['Jmag','Hmag','Kmag'])]]
    task={'id':'M1','task_type':'multi_archive','constraints':{'multi_archive_steps':steps}}
    (root/'generated/x.jsonl').write_text(json.dumps(task)+'\n')
    (root/'generated/x_multistep.jsonl').write_text(json.dumps(task)+'\n')
    digest=hashlib.sha256((root/'generated/x.jsonl').read_bytes()).hexdigest()
    old={'task_id':'M1','task_type':'multi_archive','dataset_sha256':digest,
         'status':'incomplete_step_evidence','answer_shape':'multi_archive_values',
         'steps':[{'module':'simbad','function':'query_region','expected_columns':['ra'],'status':'complete'},
                  {'module':'vizier','function':'query_region','expected_columns':['Jmag','Hmag','Kmag'],'status':'not_structured_table'}],
         'answer_evidence':[{'field':'simbad:ra','row_index':0,'table_index':0,'value':17.1}]}
    path=root/'validated/x_multistep_references.jsonl'
    path.write_text(json.dumps(old)+'\n')
    (root/'validated/x_multistep_references.progress.jsonl').write_text(json.dumps(old)+'\n')
    return root,old


def test_resume_only_incomplete_steps_and_preserve_original(tmp_path):
    root,old=make_resume_dataset(tmp_path)
    fake=FakeClient()
    preview=asyncio.run(collect_multistep(name='x',output_dir=root,resume=True,
       retry_incomplete=True,dry_run=True,client_factory=lambda:fake))
    assert preview['selected_task_ids']==['M1'] and not fake.calls
    result=asyncio.run(collect_multistep(name='x',output_dir=root,resume=True,
       retry_incomplete=True,client_factory=lambda:fake))
    assert fake.calls==['vizier'] and result['reference_complete']==1
    snapshot=root/'validated/x_multistep_references_preretry.jsonl'
    assert json.loads(snapshot.read_text())['status']=='incomplete_step_evidence'
    latest=json.loads((root/'validated/x_multistep_references.jsonl').read_text())
    assert latest['status']=='complete' and len(latest['answer_evidence'])==4
    assert latest['steps'][0]['reused_prior_evidence'] is True
    assert len(latest['retry_history'])==1
    again=asyncio.run(collect_multistep(name='x',output_dir=root,resume=True,
       retry_incomplete=True,client_factory=lambda:fake))
    assert again['reference_complete']==1 and fake.calls==['vizier']


def test_literature_drafts_are_only_drafts(tmp_path):
    root=tmp_path/'datasets';(root/'generated').mkdir(parents=True)
    task={'id':'L1','task_type':'literature_driven','target':'NGC 1068',
          'constraints':{'required_result':'Chandra grating observation identifiers'},
          'research_evidence':{'bibcodes':['2023ApJ.123']} }
    (root/'generated/x_multistep.jsonl').write_text(json.dumps(task)+'\n')
    report=write_literature_drafts('x',root)
    assert report['status']=='DRAFT_ONLY_NOT_REFERENCE' and report['draft_ready']==1
    obj=json.loads(Path(report['output']).read_text())
    assert obj['archive']=='heasarc' and obj['catalog']=='chanmaster'
    assert obj['bibcodes_are_candidate_only'] is True
    assert 'observation' in obj['steps_required'][-1]


def test_vizier_multifield_row_association_cannot_mix_sources():
    evidence=[{'field':'vizier:'+field,'row_index':i,'table_index':0,'value':v}
        for i,values in enumerate([[11.1,10.2,9.3],[12.1,11.2,10.3]])
        for field,v in zip(('Jmag','Hmag','Kmag'),values)]
    ungrouped={'answer_values':[11.1,10.2,9.3,12.1,11.2,10.3]}
    assert compare_answer('multi_archive_values',evidence,ungrouped,{})[0]!='correct'
    grouped={'answer_values':['2MASS x: J=11.1 H=10.2 K=9.3','2MASS y: J=12.1 H=11.2 K=10.3']}
    assert compare_answer('multi_archive_values',evidence,grouped,{})[0]=='correct'
    swapped={'answer_values':['2MASS x: J=11.1 H=11.2 K=9.3','2MASS y: J=12.1 H=10.2 K=10.3']}
    assert compare_answer('multi_archive_values',evidence,swapped,{})[0]!='correct'
