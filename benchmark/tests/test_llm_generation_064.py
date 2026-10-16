"""Mocked API tests: no OpenAI credentials or external archive network required."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace as Obj

from benchmark.llm_generation import generate_llm, INSTRUCTIONS_VERSION, instruction_text
from benchmark.generator import GenerationError
from benchmark.tests.test_generator import FixtureSession
from benchmark.cli import build_parser
from benchmark.diversity import analyze_candidates
from benchmark.exports import candidate_csv_record, save_views
from benchmark.validator import check_dataset, ValidationError
from benchmark.api import AstroAKDBench

class StubResponses:
    def __init__(self):
        self.calls=[]
    def create(self, **kwargs):
        self.calls.append(kwargs)
        text=kwargs['input'][1]['content'].split('SLOTS JSON:\n',1)[1]
        data=json.loads(text)
        rows=[]
        for slot in data:
            q=f"For {slot['target']}, what {slot['intent'].replace('_',' ')} does {slot['archive'].upper()} report?"
            rows.append({'id':slot['id'],'question':q,'source_urls':['https://example.org/evidence']})
        return Obj(output_text=json.dumps({'questions':rows}),
                   output=([Obj(type='web_search_call',action=Obj(sources=[Obj(url='https://example.org/evidence')]))]
                           if 'tools' in kwargs else []))

class LLM064Tests(unittest.TestCase):
    def test_defaults_instructions_mcp_and_openai(self):
        args=build_parser().parse_args(['generate'])
        self.assertEqual(args.backend,'openai')
        self.assertTrue(args.instructions)
        self.assertTrue(args.mcp)
        self.assertIn('V1-derived',instruction_text(enabled=True))
        self.assertEqual(instruction_text(enabled=False),'')
        self.assertEqual(INSTRUCTIONS_VERSION, 'reference_aware_0_6_7_11_9')

    def test_four_flag_combinations_and_no_mcp_network(self):
        for use_mcp in (True,False):
            for instructions in (True,False):
                with self.subTest(mcp=use_mcp,instructions=instructions):
                    responses=StubResponses()
                    def forbidden(*a,**kw):
                        if not use_mcp:raise AssertionError('MCP unexpectedly used')
                        return FixtureSession(*a,**kw)
                    tasks,report=asyncio.run(generate_llm(count=10,seed=17,
                        use_mcp=use_mcp,use_instructions=instructions,
                        session_factory=forbidden,
                        openai_client_factory=lambda:Obj(responses=responses)))
                    self.assertEqual(len(tasks),10)
                    self.assertEqual(report['use_mcp'],use_mcp)
                    self.assertEqual(report['use_instructions'],instructions)
                    self.assertEqual(report['openai_requests'],2)
                    self.assertEqual(report['web_search_calls'],0 if use_mcp else 2)
                    self.assertTrue(all(q['answer_spec']['expected_answer_status'] != 'verified' for q in tasks))
                    self.assertEqual(analyze_candidates(tasks)['counts']['duplicate_question_records'],0)
                    if use_mcp:
                        self.assertTrue(all(t['reference_call']['tool']=='astroquery_execute' for t in tasks))
                        check_dataset(tasks)
                    else:
                        self.assertTrue(all(t['reference_call'] is None for t in tasks))
                        self.assertEqual(tasks[0]['research_sources'],['https://example.org/evidence'])
                        with self.assertRaisesRegex(ValidationError,'web-search research candidate'):
                            check_dataset(tasks)
                        self.assertEqual(analyze_candidates(tasks)['counts']['duplicate_call_records'],0)
                    self.assertTrue(('V1-derived' in responses.calls[0]['input'][0]['content']) == instructions)

    def test_hybrid_mcp_preserves_call_and_is_readable_export(self):
        responses=StubResponses()
        tasks,report=asyncio.run(generate_llm(count=5,backend='hybrid',
                openai_client_factory=lambda:Obj(responses=responses),
                session_factory=lambda url:FixtureSession(url)))
        self.assertEqual(report['generation_backend'],'hybrid')
        self.assertTrue(all(t['reference_call'] for t in tasks))
        with TemporaryDirectory() as td:
            csv_path=Path(td)/'q.csv'
            pretty=Path(td)/'q.json'
            save_views(tasks,csv_path=csv_path,pretty=pretty)
            self.assertEqual(len(json.loads(pretty.read_text())),5)
            self.assertIn('generation_backend',csv_path.read_text())

    def test_openai_errors_fail_without_writing(self):
        class NoSearch(StubResponses):
            def create(self,**kw):
                response=super().create(**kw)
                response.output=[]
                return response
        with self.assertRaisesRegex(GenerationError,'requires a completed OpenAI web_search'):
            asyncio.run(generate_llm(count=2,use_mcp=False,
                openai_client_factory=lambda:Obj(responses=NoSearch())))
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}):
            with self.assertRaisesRegex(GenerationError,'OPENAI_API_KEY'):
                asyncio.run(generate_llm(count=2,use_mcp=False))

    def test_50_tasks_mcp_and_web_search(self):
        for use_mcp in (True, False):
            stub=StubResponses()
            tasks, report=asyncio.run(generate_llm(
                count=50, seed=123, use_mcp=use_mcp,
                session_factory=(lambda url:FixtureSession(url)) if use_mcp else
                                 (lambda url: (_ for _ in ()).throw(AssertionError('no MCP'))),
                openai_client_factory=lambda:Obj(responses=stub)))
            self.assertEqual(len(tasks),50)
            self.assertEqual(report['distinct_archive_target_pairs'],50)
            self.assertEqual(report['openai_requests'],10)
            self.assertEqual(report['web_search_calls'],0 if use_mcp else 10)
            self.assertTrue(all(not t.get('answer_spec',{}).get('expected_answer') for t in tasks))

    def test_custom_instructions_and_missing_archive_are_rejected(self):
        from benchmark.llm_generation import instruction_text, _guard_question
        with TemporaryDirectory() as td:
            prompt=Path(td)/'prompt.md'; prompt.write_text('' * 0 + 'Only ask astronomical IDs. ' * 3)
            self.assertIn('astronomical IDs',instruction_text(enabled=True,path=prompt))
            with self.assertRaisesRegex(GenerationError,'Cannot specify custom instructions'):
                instruction_text(enabled=False,path=prompt)
            with self.assertRaisesRegex(GenerationError,'Cannot read instructions'):
                instruction_text(enabled=True,path=Path(td)/'missing.md')
        t={'id':'id1','target':'M31','module':'mast','question':'What observation IDs are available near M31?',
           'answer_spec':{'expected_columns':['obs_id']}}
        with self.assertRaisesRegex(GenerationError,'does not uniquely name archive'):
            _guard_question('For M31, what are the observation IDs?',t,use_mcp=True)
        with self.assertRaisesRegex(GenerationError,'invented a year'):
            _guard_question('Which MAST observation IDs exist for M31 in 2017?',t,use_mcp=True)

    def test_python_api_research_outputs(self):
        with TemporaryDirectory() as td:
            api=AstroAKDBench(root=td)
            stub=StubResponses()
            result=asyncio.run(api.generate_queries(count=5,use_mcp=False,
                backend='openai',openai_client_factory=lambda:Obj(responses=stub),
                output='datasets/generated/research.jsonl',
                pretty_output='datasets/generated/research.json',
                csv_output='datasets/generated/research.csv'))
            self.assertEqual(result['openai_requests'],1)
            self.assertEqual(len(api.load_records('datasets/generated/research.jsonl')),5)
            self.assertEqual(len(json.loads((Path(td)/'datasets/generated/research.json').read_text())),5)

if __name__=='__main__': unittest.main()
