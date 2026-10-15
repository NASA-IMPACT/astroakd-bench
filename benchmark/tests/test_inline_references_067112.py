"""0.6.7.11.2: safe opt-in reference collection in the named mixed workflow.

All tests use fixture question generation and a mocked archive collector; no
remote archives, OpenAI, ADS, or API tokens are accessed.
"""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from benchmark.cli import build_parser, _execute
from benchmark.simple_workflows import create_queries, dataset_paths
from benchmark.tests.test_flexible_counts_067111 import fixture_generator


class InlineReferencesTests(TestCase):
    def test_cli_parses_exact_documented_command(self):
        parsed=build_parser().parse_args([
            'create-queries','--name','astroakd_test40','--count','100',
            '--output-dir','/scratch/astroakd/study1','--seed','20261018',
            '--require-ads','--with-reference-answers'])
        self.assertTrue(parsed.with_reference_answers)
        self.assertIsNone(parsed.reference_limit)
        self.assertEqual(parsed.name,'astroakd_test40')
        self.assertEqual(parsed.count,100)
        self.assertEqual(parsed.output_dir,Path('/scratch/astroakd/study1'))

    def test_cli_passes_flags_to_workflow(self):
        args=build_parser().parse_args([
            'create-queries','--count','40','--with-reference-answers',
            '--reference-limit','5'])
        with patch('benchmark.simple_workflows.create_queries',new_callable=AsyncMock,
                   return_value={'status':'PARTIAL'}) as create:
            result=asyncio.run(_execute(args))
        self.assertEqual(result['status'],'PARTIAL')
        self.assertTrue(create.await_args.kwargs['with_reference_answers'])
        self.assertEqual(create.await_args.kwargs['reference_limit'],5)

    def test_one_step_saves_candidates_and_collects_only_single_call(self):
        with TemporaryDirectory() as tmp:
            out=Path(tmp)/'study1'
            fake=AsyncMock(return_value={
                'status':'PARTIAL','quality_gate':'PENDING',
                'processed':5,'remaining':75,'dispositions':{'accepted_nonempty':5}})
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator), \
                 patch('benchmark.simple_workflows.collect_references',fake):
                result=asyncio.run(create_queries(name='astroakd_test40',
                    count=100,output_dir=out,seed=20261018,
                    with_reference_answers=True,reference_limit=5))
            paths=dataset_paths(name='astroakd_test40',output_dir=out)
            self.assertEqual(len(paths['tasks'].read_text().splitlines()),100)
            self.assertEqual(len(paths['single_calls'].read_text().splitlines()),80)
            self.assertEqual(len(paths['multistep'].read_text().splitlines()),20)
            self.assertEqual(result['reference_collection']['processed'],5)
            self.assertEqual(result['reference_collection']['remaining'],75)
            self.assertEqual(result['reference_collection']['multistep_pending'],20)
            self.assertEqual(result['reference_collection']['gold_verified'],0)
            self.assertEqual(fake.await_args.kwargs['limit'],5)
            self.assertFalse(fake.await_args.kwargs['resume'])
            self.assertEqual(fake.await_args.kwargs['name'],'astroakd_test40')
            self.assertEqual(fake.await_args.kwargs['output_dir'],out)
            self.assertEqual(json.loads(paths['generation_report'].read_text())['reference_collection'],
                             result['reference_collection'])
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator):
                with self.assertRaises(FileExistsError):
                    asyncio.run(create_queries(name='astroakd_test40',count=100,
                        output_dir=out,with_reference_answers=True))

    def test_explicit_optin_is_required_for_reference_limit(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'requires --with-reference-answers'):
                asyncio.run(create_queries(output_dir=tmp,count=5,reference_limit=5))
            with self.assertRaisesRegex(ValueError,'positive integer'):
                asyncio.run(create_queries(output_dir=tmp,count=5,
                    with_reference_answers=True,reference_limit=0))

    def test_existing_reference_artifacts_are_protected_before_generation(self):
        with TemporaryDirectory() as tmp:
            paths=dataset_paths(output_dir=tmp,name='special')
            paths['references'].parent.mkdir(parents=True,exist_ok=True)
            paths['references'].write_text('do not overwrite')
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator):
                with self.assertRaises(FileExistsError):
                    asyncio.run(create_queries(name='special',count=5,
                        output_dir=tmp,with_reference_answers=True))
            self.assertFalse(paths['tasks'].exists())
            self.assertEqual(paths['references'].read_text(),'do not overwrite')
