"""Native mixed Gold generation tests. No live OpenAI, ADS, archive calls."""
import asyncio
import json
from collections import Counter
from types import SimpleNamespace as N
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark.mixed_generation import generate_mixed, parse_task_mix
from benchmark.generator import GenerationError
from benchmark.tests.test_generator import FixtureSession
from benchmark.diversity import analyze_candidates
from benchmark.validator import check_dataset, ValidationError
from benchmark.cli import build_parser, main

class Responses:
    def __init__(self): self.calls=[]
    def create(self, **kwargs):
        self.calls.append(kwargs)
        prompt=kwargs['input'][-1]['content']
        if 'SLOTS JSON:\n' in prompt:
            slots=json.loads(prompt.split('SLOTS JSON:\n',1)[1])
            rows=[{'id':s['id'], 'question':f"For {s['target']}, what {s['intent'].replace('_',' ')} does {s['archive'].upper()} report?", 'source_urls':['https://example.org/a']} for s in slots]
        else:
            import re
            target=prompt.split('Target or paper-defined class: ',1)[1].split('. Required result: ',1)[0]
            goal=prompt.split('Required result: ',1)[1].split('. Literature search: ',1)[0]
            rows=[{'question':f'Which published studies identify {target}, and which {goal} can be verified independently with archival records?'}]
        return N(output_text=json.dumps({'questions':rows}),output=[])

async def fake_research(query, **kwargs):
    return {'status':'PASS','research_provider':'astroquery_mcp_ads','papers':[{'bibcode':'2018ApJ...000..000A','title':'Mock paper'}],
            'research_sources':['https://ui.adsabs.harvard.edu/abs/2018ApJ...000..000A'],
            'ads_authenticated':True,'scientific_truth_verified':False}

class MixedGenerationTests(unittest.TestCase):
    def test_parse_and_capacity(self):
        self.assertEqual(parse_task_mix('gold50',count=50)['literature_driven'],8)
        self.assertEqual(parse_task_mix('archive_driven=32,coordinate_driven=10,literature_driven=8',count=50)['coordinate_driven'],10)
        for value,count in [('gold50',49),('archive_driven=2,coordinate_driven=0,literature_driven=9',11),('bogus',50)]:
            with self.assertRaises(GenerationError):parse_task_mix(value,count=count)
        args=build_parser().parse_args(['generate','--task-mix','gold50','--single-call-output','one.jsonl', '--literature-output','two.jsonl'])
        self.assertEqual(args.single_call_output,Path('one.jsonl'))

    def test_fifty_are_native_and_separated(self):
        stub=Responses()
        tasks, report=asyncio.run(generate_mixed(count=50,seed=123,mix=parse_task_mix('gold50',count=50),
            session_factory=lambda url:FixtureSession(url),
            openai_client_factory=lambda:N(responses=stub),research_fn=fake_research))
        self.assertEqual(Counter(t['task_type'] for t in tasks),{'archive_driven':32,'coordinate_driven':10,'literature_driven':8})
        self.assertEqual(len(tasks),50)
        self.assertEqual(len(set(t['id'] for t in tasks)),50)
        self.assertFalse(any(analyze_candidates(tasks)['counts'].values()))
        self.assertTrue(all(t['reference_call'] is None for t in tasks if t['task_type']=='literature_driven'))
        self.assertTrue(all(t['reference_call'] and t['reference_call']['tool']=='astroquery_execute' for t in tasks if t['task_type']!='literature_driven'))
        self.assertTrue(all('ICRS J2000 RA' in t['question'] for t in tasks if t['task_type']=='coordinate_driven'))
        self.assertEqual(report['literature_research_requests'],8)
        self.assertEqual(report['research_provider_counts'],{'astroquery_mcp_ads':8})
        self.assertEqual(report['expected_answers_verified'],0)
        check_dataset([t for t in tasks if t['task_type'] != 'literature_driven'])
        with self.assertRaises(ValidationError):
            check_dataset(tasks)
        self.assertEqual(len(stub.calls), 9+8) # nine batches for 42 + eight literature drafts

    def test_missing_mcp_ads_uses_web_fallback_without_stopping(self):
        async def web(query,**kwargs):
            return {'status':'PASS','research_provider':'openai_web_search',
                    'fallback_reason':'ads_not_configured','ads_authenticated':False,
                    'research_summary_unverified':'Paper evidence to inspect',
                    'research_sources':['https://arxiv.org/abs/1901.00001']}
        stub=Responses()
        tasks, report=asyncio.run(generate_mixed(count=6,seed=12,
            mix=parse_task_mix('archive_driven=3,coordinate_driven=1,literature_driven=2',count=6),
            session_factory=lambda url:FixtureSession(url),
            openai_client_factory=lambda:N(responses=stub),research_fn=web))
        self.assertEqual(len(tasks),6)
        self.assertEqual(report['research_provider_counts'],{'openai_web_search':2})
        self.assertTrue(all(t['research_evidence']['fallback_reason']=='ads_not_configured' for t in tasks if t['task_type']=='literature_driven'))

    def test_template_fails_explicitly(self):
        with self.assertRaisesRegex(GenerationError,'requires --backend openai or hybrid'):
            asyncio.run(generate_mixed(count=3,mix=parse_task_mix('archive_driven=1,coordinate_driven=1,literature_driven=1',count=3),backend='template'))

    def test_cli_allows_published_subsets_with_mock(self):
        async def fake_mixed(*args,**kwargs):
            tasks,report=await generate_mixed(count=6,seed=16,
                mix=parse_task_mix('archive_driven=3,coordinate_driven=1,literature_driven=2',count=6),
                session_factory=lambda url:FixtureSession(url),
                openai_client_factory=lambda:N(responses=Responses()), research_fn=fake_research)
            return tasks,report
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=['generate','--count','6','--task-mix','archive_driven=3,coordinate_driven=1,literature_driven=2',
                  '--output',str(root/'mix.jsonl'),'--single-call-output',str(root/'ordinary.jsonl'),
                  '--literature-output',str(root/'literature.jsonl'), '--csv-output',str(root/'mix.csv')]
            import contextlib,io
            with patch('benchmark.mixed_generation.generate_mixed',fake_mixed),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args),0,out.getvalue())
                self.assertEqual(len((root/'mix.jsonl').read_text().splitlines()),6)
                self.assertEqual(len((root/'ordinary.jsonl').read_text().splitlines()),4)
                self.assertEqual(len((root/'literature.jsonl').read_text().splitlines()),2)
                self.assertEqual(main(args),1)

if __name__=='__main__':unittest.main()
