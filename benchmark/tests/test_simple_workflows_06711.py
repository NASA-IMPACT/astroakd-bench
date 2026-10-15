"""Release 0.6.7.11 offline verification: no OpenAI, live MCP, or ADS calls."""
import asyncio
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import json
import unittest

from benchmark.mixed_generation import parse_task_mix, generate_mixed
from benchmark.tests.test_mixed_generation_065 import Responses, fake_research, FixtureSession
from benchmark.simple_workflows import create_queries, dataset_paths, reference_report
from benchmark.operational_report import create_operational_report
from benchmark.cli import build_parser


class EasyWorkflowTests(unittest.TestCase):
    def mock_kwargs(self):
        return {'openai_client_factory':lambda:N(responses=Responses()),
                'research_fn':fake_research,
                'llm_fn':None}

    def test_default_balanced_100(self):
        mix=parse_task_mix('balanced100',count=100)
        self.assertEqual(mix,{'archive_driven':60,'coordinate_driven':20,'literature_driven':8,'multi_archive':12})
        self.assertEqual(parse_task_mix('gold50',count=50)['literature_driven'],8)
        self.assertEqual(parse_task_mix('archive_driven=3,coordinate_driven=1,literature_driven=2',count=6)['multi_archive'],0)

    def test_new_task_compositions_and_ads(self):
        tasks, report=asyncio.run(generate_mixed(count=100,seed=20261018,mix=parse_task_mix('balanced100',count=100),
            session_factory=lambda url:FixtureSession(url),**self.mock_kwargs()))
        self.assertEqual(Counter(t['task_type'] for t in tasks),parse_task_mix('balanced100',count=100))
        self.assertEqual(len({t['id'] for t in tasks}),100)
        for task in tasks:
            if task['task_type']=='multi_archive':
                steps=task['constraints']['multi_archive_steps']
                self.assertEqual(len(steps),2)
                self.assertNotEqual(steps[0]['module'],steps[1]['module'])
                self.assertTrue(all(s['reference_call']['tool']=='astroquery_execute' for s in steps))
                self.assertIsNone(task['reference_call'])
            if task['task_type']=='literature_driven':
                self.assertEqual(task['research_evidence']['research_provider'],'astroquery_mcp_ads')
        self.assertEqual(report['expected_answers_verified'],0)
        self.assertEqual(report['research_provider_counts'],{'astroquery_mcp_ads':8})

    def test_require_ads_rejects_fallback(self):
        async def web(*args,**kwargs):
            return {'status':'PASS','research_provider':'openai_web_search'}
        with self.assertRaisesRegex(ValueError,'ADS required'):
            asyncio.run(generate_mixed(count=6,seed=5,
                mix=parse_task_mix('archive_driven=3,coordinate_driven=1,literature_driven=2',count=6),
                require_ads=True,session_factory=lambda url:FixtureSession(url),
                research_fn=web,openai_client_factory=lambda:N(responses=Responses())))

    def test_named_outputs_and_reports_no_reference(self):
        # Offline creation directly tests the same API used by create-queries CLI.
        # Patch the MCP-backed generator as a test dependency, not as production behavior.
        from unittest.mock import patch
        async def fake_generator(*args,**kwargs):
            return await generate_mixed(*args,session_factory=lambda url:FixtureSession(url),
                **{k:v for k,v in kwargs.items() if k not in ('research_fn','llm_fn','openai_client_factory')},
                **self.mock_kwargs())
        with TemporaryDirectory() as tmp:
            with patch('benchmark.simple_workflows.generate_mixed',fake_generator):
                data=asyncio.run(create_queries(root=tmp,name='synthetic_100'))
            paths=dataset_paths(tmp,'synthetic_100')
            self.assertEqual(len(paths['tasks'].read_text().splitlines()),100)
            self.assertEqual(len(paths['single_calls'].read_text().splitlines()),80)
            self.assertEqual(len(paths['multistep'].read_text().splitlines()),20)
            self.assertEqual(data['verified_gold_answers'],0)
            result=reference_report(root=tmp,plots=False)
            self.assertEqual(result['reference_disposition_counts']['not_collected'],80)
            self.assertEqual(result['reference_disposition_counts']['multistep_not_single_call_validated'],20)
            with self.assertRaises(FileExistsError): reference_report(root=tmp,plots=False)
            with self.assertRaises(FileExistsError):
                asyncio.run(create_queries(root=tmp))

    def test_report_rejects_stale_reference(self):
        with TemporaryDirectory() as tmp:
            p=dataset_paths(tmp)
            for field in ('tasks','single_calls'):
                p[field].parent.mkdir(parents=True,exist_ok=True)
            task={'id':'T1','module':'simbad','task_type':'archive_driven','target':'M31',
                  'question':'What main identifier does SIMBAD return for M31?',
                  'reference_call':{'tool':'astroquery_execute'},
                  'answer_spec':{'expected_columns':['main_id']}}
            content=json.dumps(task)+'\n'
            p['tasks'].write_text(content);p['single_calls'].write_text(content)
            p['references'].parent.mkdir(parents=True,exist_ok=True)
            p['references'].write_text(json.dumps({'task_id':'T1','input_dataset_sha256':'bad',
                'reference_call':task['reference_call'],'disposition':'accepted_nonempty'})+'\n')
            with self.assertRaisesRegex(ValueError,'stale'):
                reference_report(root=tmp,plots=False)

    def test_operational_report_outputs_unverified_answers(self):
        import hashlib
        with TemporaryDirectory() as tmp:
            p=dataset_paths(tmp)
            p['tasks'].parent.mkdir(parents=True,exist_ok=True)
            task={'id':'T1','module':'simbad','question':'What is M31?', 'target':'M31'}
            p['tasks'].write_text(json.dumps(task)+'\n')
            h=hashlib.sha256(p['tasks'].read_bytes()).hexdigest()
            p['runs'].parent.mkdir(parents=True,exist_ok=True)
            p['runs'].write_text(''.join(json.dumps({'task_id':'T1','arm':a,'candidate_sha256':h,
                    'status':'completed','duration_seconds':2.0,'answer':{'answer':'unverified',
                    'parse_status':'structured'},'trace':[],'token_usage':{'total_tokens':10}})+'\n'
                    for a in ('mcp_only','mcp_instruction','web_only')))
            result=create_operational_report(p['tasks'],p['runs'],p['plots']/'agents',plots=False)
            self.assertEqual(result['runs_recorded'],3)
            self.assertTrue((p['plots']/'agents'/'abc_answers.csv').exists())
            with self.assertRaises(FileExistsError):
                create_operational_report(p['tasks'],p['runs'],p['plots']/'agents',plots=False)

    def test_named_cli_available(self):
        parser=build_parser()
        self.assertIsNone(parser.parse_args(['create-queries']).name)
        self.assertEqual(parser.parse_args(['reference-report','--no-plots']).no_plots,True)
        self.assertEqual(parser.parse_args(['run-benchmark','--limit','5']).limit,5)


if __name__=='__main__': unittest.main()
