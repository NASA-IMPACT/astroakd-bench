"""0.6.6 isolated gold and three-arm tests; no live network, no secrets."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from benchmark.gold import gold_draft, gold_finalize
from benchmark.three_arm import run_three_arm, score_three_arm, _score_one, _parse_answer, ARMS
from benchmark.agent_runner import validate_tool_args, AgentRunError
from benchmark.validator import atomic_jsonl, load_jsonl, ValidationError
from benchmark.cli import build_parser


def jfile(p,rows):
    atomic_jsonl(p,rows)
    return p


class FakeMCP:
    def __init__(self,url): self.url=url
    async def __aenter__(self): return self
    async def __aexit__(self,*args): return False
    async def list_tools(self):
        return [{'name':'astroquery_execute','description':'query','input_schema':{'type':'object','properties':{'module_name':{'type':'string'},'function_name':{'type':'string'},'params':{'type':'object'}}}},
                {'name':'ads_query_compact','description':'search papers','input_schema':{'type':'object','properties':{'query_string':{'type':'string'}}}}]
    async def call(self,tool,args):
        return {'success': True,'result': {'rows':[{'main_id':'M31'}]}}


class FakeSDK:
    def __init__(self): self.responses=self; self.chat=NS(completions=self); self.per_arm_calls=0
    async def create(self,**kw):
        if 'input' in kw:
            assert kw['tools']==[{'type':'web_search'}]
            return NS(output_text=json.dumps({'answer':'M31','answer_values':['M31'],'sources':['https://example.org/x'],'abstained':False}),
                      output=[NS(type='web_search_call',action=NS(sources=[]))],usage=NS(input_tokens=10,output_tokens=4,total_tokens=14))
        self.per_arm_calls+=1
        # First response issues a safe MCP call, second returns structured final answer
        is_tool=any(m['role']=='tool' for m in kw['messages'])
        if not is_tool:
            call=NS(id='id1',function=NS(name='astroquery_execute', arguments=json.dumps({'module_name':'simbad','function_name':'query_object','params':{'object_name':'M31'}})))
            return NS(choices=[NS(message=NS(content=None,tool_calls=[call]))],usage=NS(prompt_tokens=20,completion_tokens=2,total_tokens=22))
        return NS(choices=[NS(message=NS(content=json.dumps({'answer':'M31','answer_values':['M31'],'sources':[],'abstained':False}),tool_calls=[]))],usage=NS(prompt_tokens=10,completion_tokens=7,total_tokens=17))


class TestGold066(unittest.TestCase):
    def _files(self,root):
        tasks=[{'id':'T1','task_type':'archive_driven','question':'What does SIMBAD return for M31?','module':'simbad','target':'M31','answer_spec':{'expected_columns':['main_id']}}]
        path=jfile(root/'tasks.jsonl',tasks)
        from hashlib import sha256
        h=sha256(path.read_bytes()).hexdigest()
        ref=[{'task_id':'T1','input_dataset_sha256':h,'disposition':'accepted_nonempty',
              'response':{'result':{'rows':[{'main_id':'M31'}]}},
              'evaluation':{'checks':{'returned_rows':1,'truncated':False}}}]
        refpath=jfile(root/'refs.jsonl',ref)
        return path,refpath

    def test_draft_never_claims_verified(self):
        with TemporaryDirectory() as d:
            r=Path(d);t,ref=self._files(r)
            summary=gold_draft(t,r/'draft.jsonl',r/'report.json',references=ref,reference_tasks=t)
            row=load_jsonl(r/'draft.jsonl')[0][0]
            self.assertEqual(summary['references_collected'],1)
            self.assertEqual(summary['gold_verified'],0)
            self.assertEqual(row['gold_status'],'pending')
            self.assertIsNone(row['gold'])
            with self.assertRaises(ValidationError): gold_finalize(t,r/'draft.jsonl',r/'gold.jsonl',r/'g_report.json')

    def test_bad_reference_hash_rejected(self):
        with TemporaryDirectory() as d:
            r=Path(d);t,ref=self._files(r)
            v=load_jsonl(ref)[0];v[0]['input_dataset_sha256']='wrong';atomic_jsonl(ref,v,replace=True)
            with self.assertRaises(ValidationError): gold_draft(t,r/'draft.jsonl',r/'report.json',references=ref,reference_tasks=t)

    def test_review_approves_with_independent_sources(self):
        with TemporaryDirectory() as d:
            r=Path(d);t,ref=self._files(r)
            gold_draft(t,r/'draft.jsonl',r/'report.json',references=ref,reference_tasks=t)
            row=load_jsonl(r/'draft.jsonl')[0][0]
            row.update(question_review='approved',gold_status='verified',gold={'kind':'set','values':['M31']},reviewer='reviewer-1',
                       sources=[{'uri':'https://simbad.cds.unistra.fr/object','description':'Independent catalogue'},
                                {'uri':'https://archive.stsci.edu/observations','description':'Independent cross-check'}])
            edited=jfile(r/'edited.jsonl',[row])
            summary=gold_finalize(t,edited,r/'gold.jsonl',r/'gold_report.json')
            self.assertEqual(summary['verified_gold_answers'],1)
            self.assertTrue(summary['scientific_accuracy_ready'])
            result=score_three_arm(t,r/'gold.jsonl',jfile(r/'runs.jsonl',[{'task_id':'T1','arm':arm,'status':'completed','candidate_sha256':row['input_dataset_sha256'],'answer':{'answer_values':['M31'],'abstained':False},'trace':[]} for arm in ARMS]),r/'scores.jsonl',r/'scores_report.json')
            self.assertEqual(result['arms']['mcp_only']['mean_scientific_fraction'],1.0)

    def test_source_and_missing_instruction_rejected(self):
        with TemporaryDirectory() as d:
            r=Path(d);t,ref=self._files(r)
            gold_draft(t,r/'draft.jsonl',r/'report.json',references=ref,reference_tasks=t)
            row=load_jsonl(r/'draft.jsonl')[0][0]
            row.update(question_review='approved',gold_status='verified',gold={'kind':'text','values':['M31']},reviewer='x',
                       sources=[{'uri':'https://same.org/x','description':'a'},{'uri':'https://same.org/y','description':'b'}])
            jfile(r/'edited.jsonl',[row])
            with self.assertRaisesRegex(ValidationError,'two distinct'):
                gold_finalize(t,r/'edited.jsonl',r/'gold.jsonl',r/'r.json')

    def test_unverified_never_scored(self):
        with TemporaryDirectory() as d:
            r=Path(d);t,ref=self._files(r)
            gold_draft(t,r/'draft.jsonl',r/'report.json',references=ref,reference_tasks=t)
            gold_finalize(t,r/'draft.jsonl',r/'gold.jsonl',r/'g_report.json',allow_partial=True)
            runs=[{'task_id':'T1','arm':arm,'status':'completed','candidate_sha256':load_jsonl(t)[1],
                   'answer':{'answer_values':['M31'],'abstained':False},'trace':[]} for arm in ARMS]
            summary=score_three_arm(t,r/'gold.jsonl',jfile(r/'runs.jsonl',runs),r/'s.jsonl',r/'sreport.json')
            self.assertIsNone(summary['arms']['mcp_only']['mean_scientific_fraction'])
            self.assertEqual(summary['arms']['mcp_only']['statuses']['UNSCORABLE_NO_GOLD'],1)

    def test_numeric_and_set(self):
        self.assertEqual(_score_one({'kind':'numeric','values':[10.], 'absolute_tolerance':0.1,'unit':'km/s'}, {'answer_values':[10.05],'unit':'km/s','abstained':False}),('CORRECT',1.0))
        self.assertEqual(_score_one({'kind':'set','values':['a','b']},{'answer_values':['a'],'abstained':False}),('PARTIAL',0.66667))
        self.assertEqual(_parse_answer('plain answer')['parse_status'],'unstructured')

    def test_ads_gate_bounded(self):
        self.assertEqual(validate_tool_args('ads_query_compact',{'query_string':'black holes','max_results':5},extended=True)['max_results'],5)
        with self.assertRaises(AgentRunError):validate_tool_args('ads_query_compact',{'query_string':'test'},extended=False)
        with self.assertRaises(AgentRunError):validate_tool_args('ads_query_compact',{'query_string':'test','max_results':999},extended=True)
        with self.assertRaises(AgentRunError):validate_tool_args('ads_get_paper',{'bibcode':'2000','other':1},extended=True)

    def test_all_arms_and_separate_instruction(self):
        async def go():
            with TemporaryDirectory() as d:
                r=Path(d);t,_=self._files(r)
                ins=r/'AstroAKD_Instruction.md';ins.write_text('# Instructions\n'+'Domain-specific AstroAKD procedure. '*20)
                sdk=FakeSDK()
                result=await run_three_arm(t,ins,r/'runs.jsonl',r/'report.json',sdk=sdk,mcp_factory=FakeMCP)
                self.assertEqual(result['status'],'COMPLETE')
                rows=load_jsonl(r/'runs.jsonl')[0]
                self.assertEqual([x['arm'] for x in rows],list(ARMS))
                self.assertEqual(sum(x['arm']=='web_only' and x['trace'][0]['tool']=='openai_web_search' for x in rows),1)
                self.assertTrue(all(x['status']=='completed' for x in rows))
                self.assertTrue(all(x['agent_instruction_sha256'] is None for x in rows if x['arm']!='mcp_instruction'))
        asyncio.run(go())

    def test_cli(self):
        p=build_parser()
        self.assertEqual(p.parse_args(['run-three-arm','--tasks','a.jsonl','--agent-instruction','inst.md','--output','out','--report','rep']).command,'run-three-arm')
        self.assertEqual(p.parse_args(['gold-finalize','--tasks','a','--reviewed','b','--output','c','--report','d']).allow_partial,False)
