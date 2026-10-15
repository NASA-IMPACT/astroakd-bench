"""Offline qualification for narrow objective reference-snapshot scoring."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from benchmark.scorable import build_scorable, score_scorable, _normalize_equivalent_unit
from benchmark.validator import load_jsonl, atomic_jsonl, ValidationError

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'benchmark/tests/fixtures/legacy/generated/gold_mixed_065_single_call_42.jsonl'
REFS=ROOT/'benchmark/tests/fixtures/legacy/validated/gold_mixed_065_ref_42.jsonl'

class Scorable067(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.p=Path(self.work.name)
        self.tasks=self.p/'tasks.jsonl';self.oracle=self.p/'oracle.jsonl'
        self.answers=self.p/'answers.csv';self.report=self.p/'report.json'
        self.out=build_scorable(BASE,REFS,self.tasks,self.oracle,self.answers,self.report)
    def test_full_50_with_unique_keys_and_snapshot_provenance(self):
        self.assertEqual(self.out['count'],50)
        self.assertEqual(sum(self.out['by_archive'].values()),50)
        self.assertEqual(self.out['independently_verified_gold'],0)
        tasks,sha=load_jsonl(self.tasks);oracle,_=load_jsonl(self.oracle)
        self.assertEqual(len({x['question'] for x in tasks}),50)
        self.assertEqual(len(oracle),50)
        self.assertTrue(all(x['oracle_status']=='reference_anchored_unreviewed' for x in oracle))
        self.assertTrue(all(x['input_dataset_sha256']==sha for x in oracle))
        self.assertTrue(all(len(x['gold']['values'])==1 for x in oracle))
        self.assertTrue(all('answer_values' in t['question'] for t in tasks))
        self.assertTrue(all('source_reference_record_sha256' in t['provenance'] for t in tasks))
        with self.answers.open(newline='') as fh:self.assertEqual(len(list(csv.DictReader(fh))),50)
    def test_build_is_reproducible(self):
        other=self.p/'other'
        other.mkdir()
        build_scorable(BASE,REFS,other/'tasks.jsonl',other/'oracle.jsonl',other/'answers.csv',other/'report.json')
        self.assertEqual(self.tasks.read_bytes(),(other/'tasks.jsonl').read_bytes())
        self.assertEqual(self.oracle.read_bytes(),(other/'oracle.jsonl').read_bytes())
    def test_no_overwrite_without_replace(self):
        with self.assertRaises(ValidationError):
            build_scorable(BASE,REFS,self.tasks,self.oracle,self.answers,self.report)
    def test_strict_scoring_and_full_answer_retention(self):
        tasks,sha=load_jsonl(self.tasks)
        oracle,_=load_jsonl(self.oracle)
        val=oracle[0]['gold']['values'][0]
        runs=[{'task_id':tasks[0]['id'],'arm':arm,'status':'completed','model':'gpt-5.2',
               'candidate_sha256':sha,'trace':([{'tool':'openai_web_search'}] if arm=='web_only' else []),
               'answer':ans, 'duration_seconds':1.0} for arm,ans in [
                   ('mcp_only',{'answer':'correct','answer_values':[val], 'unit':oracle[0]['gold'].get('unit'),'abstained':False}),
                   ('mcp_instruction',{'answer':'wrong','answer_values':['definitely-wrong'],'unit':None,'abstained':False}),
                   ('web_only',{'answer':'free text is still preserved','answer_values':None,'abstained':False})]]
        runs_path=self.p/'runs.jsonl';atomic_jsonl(runs_path,runs)
        summary=score_scorable(self.tasks,self.oracle,runs_path,self.p/'compare.csv',self.p/'rate.csv',self.p/'scores.json')
        self.assertEqual(summary['status'],'PARTIAL')
        self.assertEqual(summary['arms']['mcp_only']['reference_match_pct_attempted'],100)
        self.assertEqual(summary['arms']['mcp_only']['reference_match_pct_all_questions'],2)
        self.assertEqual(summary['arms']['mcp_instruction']['reference_match_pct_attempted'],0)
        self.assertEqual(summary['arms']['web_only']['incorrect_format'],1)
        with (self.p/'compare.csv').open(newline='') as fh:rows=list(csv.DictReader(fh))
        self.assertEqual(len(rows),50)
        self.assertEqual(rows[0]['C_answer'],'free text is still preserved')
        self.assertEqual(rows[0]['B_answer'],'wrong')
        self.assertEqual(rows[0]['A_status'],'CORRECT')
        self.assertEqual(rows[1]['A_status'],'NOT_RUN')
    def test_gpt52_default_and_bounded_resolution_policy(self):
        from benchmark.cli import build_parser
        from benchmark.agent_runner import TracedMCPGateway
        from benchmark.tests.test_gold_three_arm_066 import FakeMCP
        import asyncio
        parser=build_parser()
        cli=parser.parse_args(['run-three-arm','--tasks','a','--agent-instruction','b',
                               '--output','c','--report','d'])
        self.assertEqual(cli.model,'gpt-5.2')
        async def check():
            gate=TracedMCPGateway(FakeMCP('local'),question='Find HEASARC data for M31',
                    extended_tools=True,max_tool_bytes=65536)
            outcome=await gate.call_tool('astroquery_execute',{
                'module_name':'simbad','function_name':'query_object',
                'params':{'object_name':'M31'}})
            self.assertTrue(outcome['ok'])
            strict=TracedMCPGateway(FakeMCP('local'),question='Find HEASARC data for M31',
                    extended_tools=False,max_tool_bytes=65536)
            rejected=await strict.call_tool('astroquery_execute',{
                'module_name':'simbad','function_name':'query_object',
                'params':{'object_name':'M31'}})
            self.assertFalse(rejected['ok'])
        asyncio.run(check())

    def test_unit_spelling_aliases_only(self):
        expected={'kind':'numeric','unit':'deg','values':[49.0],'absolute_tolerance':0.001}
        ans={'answer_values':[49.0],'unit':'degrees','abstained':False}
        self.assertEqual(_normalize_equivalent_unit(ans,expected)['unit'],'deg')
        self.assertEqual(_normalize_equivalent_unit({**ans,'unit':'hours'},expected)['unit'],'hours')

    def test_model_mismatch_and_bad_oracle_fail(self):
        tasks,sha=load_jsonl(self.tasks)
        runs=self.p/'bad_runs.jsonl'
        atomic_jsonl(runs,[{'task_id':tasks[0]['id'],'arm':'mcp_only','model':'gpt-4.1-mini',
                           'candidate_sha256':sha, 'trace':[],'status':'completed','answer':{}}])
        with self.assertRaises(ValidationError):
            score_scorable(self.tasks,self.oracle,runs,self.p/'a.csv',self.p/'b.csv',self.p/'c.json')
        o,_=load_jsonl(self.oracle)
        o[0]['input_dataset_sha256']='tampered'
        bad=self.p/'bad_oracle.jsonl';atomic_jsonl(bad,o)
        atomic_jsonl(runs,[],replace=True)
        with self.assertRaises(ValidationError):
            score_scorable(self.tasks,bad,runs,self.p/'a.csv',self.p/'b.csv',self.p/'c.json')

if __name__=='__main__':unittest.main()
