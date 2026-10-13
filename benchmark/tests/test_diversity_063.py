"""0.6.3 offline closure: uniqueness, answer intents and result audits."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark.generator import GenerationError, generate, generate_candidates
from benchmark.diversity import analyze_candidates, analyze_reference_redundancy, analyze_answerability, audit
from benchmark.seeds import SkyTarget
from benchmark.tests.test_generator import FixtureSession, run_fixture
from benchmark.cli import build_parser, main
from benchmark.validator import load_jsonl


class Diversity063Tests(unittest.TestCase):
    def test_50_archive_target_unique(self):
        (tasks, summary), _ = run_fixture(seed=123)
        check = analyze_candidates(tasks)
        self.assertEqual(len(tasks), 50)
        self.assertEqual(check['distinct_archive_target_pairs'], 50)
        self.assertEqual(check['counts'], {
            'duplicate_question_records': 0, 'duplicate_call_records': 0,
            'reused_archive_target_records': 0})
        self.assertEqual(summary['uniqueness_policy'], 'archive-target')
        self.assertEqual(summary['question_style'], 'answer-oriented')
        self.assertGreaterEqual(len(check['by_intent']), 9)
        self.assertTrue(all(t['answer_spec']['expected_answer_status'] == 'unverified_candidate'
                            for t in tasks))

    def test_reproducible_seed_and_distinct_calls(self):
        a = run_fixture(seed=123)[0][0]
        b = run_fixture(seed=123)[0][0]
        c = run_fixture(seed=124)[0][0]
        self.assertEqual(a,b)
        self.assertNotEqual(a,c)
        self.assertEqual(len({t['question'] for t in a}),50)

    def test_global_uniqueness_capacity_explained(self):
        with self.assertRaisesRegex(GenerationError, "only 22 available"):
            asyncio.run(generate(count=50, seed=123, uniqueness='global-target',
                                 session_factory=lambda url: FixtureSession(url)))
        tasks, report = asyncio.run(generate(count=20, seed=123,
                                 uniqueness='global-target',
                                 session_factory=lambda url: FixtureSession(url)))
        self.assertEqual(len({t['target'] for t in tasks}),20)
        self.assertEqual(report['distinct_targets'],20)

    def test_archive_capacity_fails_closed(self):
        with self.assertRaisesRegex(GenerationError, 'Not enough unique targets'):
            run_fixture(modules=('mast',),count=23)

    def test_custom_targets_with_same_coordinates_rejected(self):
        with self.assertRaisesRegex(GenerationError, 'Duplicate custom target coordinates'):
            asyncio.run(generate(count=2, modules=('mast',),
                targets=(SkyTarget('A',1,2),SkyTarget('B',1,2)),
                session_factory=lambda url:FixtureSession(url)))

    def test_catalog_aware_template_fields(self):
        cases=run_fixture(seed=123)[0][0]
        by_catalog={}
        for task in cases:
            if task['module'] not in ('vizier','heasarc'):continue
            params=task['reference_call']['arguments']['params']
            by_catalog.setdefault((task['module'],params['catalog']),[]).append(task)
        self.assertIn(('vizier','I/355'),by_catalog)
        self.assertIn(('vizier','II/246'),by_catalog)
        for task in by_catalog[('vizier','I/355')]:
            self.assertNotIn('2MASS',task['answer_spec']['expected_columns'])
        for task in by_catalog[('heasarc','chanmaster')]:
            self.assertNotIn('duration',task['answer_spec']['expected_columns'])

    def test_discovery_style_supported_and_unique(self):
        tasks, _ = asyncio.run(generate(count=50,seed=42,question_style='discovery',
                                       session_factory=lambda url:FixtureSession(url)))
        self.assertEqual(len(tasks),50)
        self.assertEqual(analyze_candidates(tasks)['counts']['reused_archive_target_records'],0)

    def test_duplicate_returned_subsets_identified(self):
        tasks=[{'id':'a','module':'mast','target':'M31'}, {'id':'b','module':'mast','target':'M31'},
               {'id':'c','module':'mast','target':'M33'}]
        result={'success':True,'result':{'columns':[{'name':'obsid'}],
                'data':[{'obsid':123}], 'row_count':1,'total_rows':20,'truncated':True}}
        refs=[{'task_id':i, 'module':'mast', 'response':result} for i in ('a','b')]
        refs.append({'task_id':'c','module':'mast','response':
             {'success':True,'result':{'columns':[{'name':'obsid'}],'data':[], 'row_count':0}}})
        info=analyze_reference_redundancy(refs,tasks)
        self.assertEqual(info['redundant_returned_table_records'],1)
        self.assertEqual(info['analyzed_nonempty_responses'],2)
        self.assertTrue(info['groups'][0]['any_truncated_or_limited'])

    def test_identical_subset_does_not_equate_different_archives(self):
        tasks=[{'id':'a','module':'mast'}, {'id':'b','module':'gaia'}]
        data={'success':True,'result':{'columns':[{'name':'x'}], 'data':[{'x':7}]}}
        refs=[{'task_id':'a','module':'mast','response':data},
              {'task_id':'b','module':'gaia','response':data}]
        self.assertEqual(analyze_reference_redundancy(refs,tasks)['groups'],[])

    def test_answerability_is_column_advisory(self):
        tasks=[{'id':'a','intent':'proposal_ids','answer_spec':{
                 'expected_columns':['proposal_id']}}]
        refs=[{'task_id':'a','disposition':'accepted_nonempty','response':{
             'result':{'columns':[{'name':'obs_id'}],'data':[{'obs_id':1}]}}}]
        a=analyze_answerability(tasks,refs)
        self.assertEqual(a['schema_incompatible'],1)
        self.assertEqual(a['checks'][0]['missing_columns'],['proposal_id'])

    def test_old_frozen_hash_unchanged(self):
        base=Path(__file__).resolve().parent.parent.parent
        frozen=base/'datasets/generated/synthetic_queries.jsonl'
        _, sha=load_jsonl(frozen)
        self.assertEqual(sha, 'e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9')

    def test_cli_audit_offline(self):
        parser=build_parser()
        args=parser.parse_args(['generate','--uniqueness','global-target',
                               '--question-style','answer-oriented'])
        self.assertEqual(args.uniqueness,'global-target')
        with TemporaryDirectory() as td:
            path=Path(td)/'test.jsonl'; out=Path(td)/'audit.json'
            t=run_fixture(count=5)[0][0]
            path.write_text(''.join(json.dumps(x)+'\n' for x in t))
            from contextlib import redirect_stdout
            from io import StringIO
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['audit-diversity','--input',str(path),
                                       '--report',str(out)]),0)
            self.assertEqual(json.loads(out.read_text())['task_count'],5)


if __name__=='__main__':
    unittest.main()
