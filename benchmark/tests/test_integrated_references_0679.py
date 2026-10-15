"""0.6.7.9 integrated candidate generation and real reference evidence tests."""
from __future__ import annotations
import asyncio
import contextlib
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from benchmark.cli import build_parser, main
from benchmark.exports import observed_reference_values, reference_csv_record
from benchmark.reference_generation import reference_paths
from benchmark.tests.test_generator import run_fixture
from benchmark.tests.test_reference_validation import fake_factory, no_wait
from benchmark.validator import validate as real_validate, load_jsonl


class ReferenceGenerationTests(unittest.TestCase):
    def test_options_and_default_paths(self):
        args = build_parser().parse_args(['generate','--count','100',
            '--with-reference-answers','--reference-limit','5'])
        self.assertTrue(args.with_reference_answers)
        self.assertEqual(args.reference_limit, 5)
        paths = reference_paths(Path('datasets/generated/sample.jsonl'),None,None,None,None)
        self.assertEqual(paths[0], Path('datasets/validated/sample_references.jsonl'))
        self.assertEqual(paths[2], Path('datasets/validated/sample_references.csv'))

    def test_real_observed_values_and_empty_no_fabrication(self):
        task = {'question':'Name?','answer_spec': {'expected_columns':['MAIN_ID']}}
        rec = {'disposition':'accepted_nonempty','response':{'result':{'data':[
            {'MAIN_ID':'M31','unrelated':10},{'MAIN_ID':'M32'}]}}}
        observed = observed_reference_values(rec,task)
        self.assertEqual(observed['status'],'OBSERVED_FIELD_VALUES_UNREVIEWED')
        self.assertEqual(observed['count'],2)
        self.assertEqual([r['value'] for r in observed['values']],['M31','M32'])
        rec['response']['result']['data'] = [{'other':'BAD'}]
        self.assertEqual(observed_reference_values(rec,task)['status'],
                         'NO_EXPECTED_FIELD_MATCH_REVIEW_REQUIRED')
        rec['disposition']='accepted_empty'
        self.assertEqual(observed_reference_values(rec,task)['values'], [])

    def test_generation_collects_resumable_archive_answers(self):
        (candidates, generation), _ = run_fixture(count=5)
        async def mocked_generate(*args,**kwargs):
            return candidates, dict(generation)
        async def mocked_validate(*args,**kwargs):
            kwargs['session_factory'] = fake_factory()
            kwargs['sleep'] = no_wait
            kwargs['delay'] = 0
            return await real_validate(*args,**kwargs)
        with TemporaryDirectory() as d:
            root=Path(d)
            dataset=root/'generated'/'new5.jsonl'
            command=['generate','--backend','template','--count','5',
                '--with-reference-answers','--reference-limit','2',
                '--output',str(dataset),'--report',str(root/'gen_report.json'),
                '--quiet-progress']
            with patch('benchmark.cli.generate',mocked_generate), patch('benchmark.cli.validate',mocked_validate):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code=main(command)
            self.assertEqual(code,0,output.getvalue())
            summary=json.loads(output.getvalue())
            self.assertEqual(summary['status'],'PARTIAL')
            self.assertEqual(summary['reference_collection']['processed'],2)
            ref=reference_paths(dataset,None,None,None,None)
            self.assertFalse(ref[0].exists())
            journal=ref[0].with_name(ref[0].name+'.progress.jsonl')
            self.assertEqual(len(journal.read_text().splitlines()),2)
            with ref[2].open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),2)
            self.assertIn('reference_answer_values_json',rows[0])
            self.assertIn('reference_answer_status',rows[0])
            self.assertIn('observed_first_row_json',rows[0])
            self.assertEqual(rows[0]['reference_answer_status'],
                             'NO_EXPECTED_FIELD_MATCH_REVIEW_REQUIRED' if
                             not json.loads(rows[0]['reference_answer_values_json']) else
                             'OBSERVED_FIELD_VALUES_UNREVIEWED')
            dataset_hash=dataset.read_bytes()
            # One command must not repeat expensive candidate generation on resume.
            result=asyncio.run(mocked_validate(dataset,*ref[:2],resume=True,
                csv_output=ref[2],timeout=180,attempts=1))
            self.assertEqual(result['status'],'COMPLETE')
            self.assertEqual(dataset.read_bytes(),dataset_hash)
            self.assertEqual(len(load_jsonl(ref[0])[0]),5)
            with ref[2].open(newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),5)

    def test_invalid_options_and_collision_fail_before_generator(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            dest=root/'new.jsonl'
            bads=(['--with-reference-answers','--no-mcp'],
                  ['--with-reference-answers','--task-mix','gold50'],
                  ['--reference-limit','5'],
                  ['--with-reference-answers','--reference-output',str(dest)])
            for args in bads:
                with self.subTest(args=args),contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(main(['generate','--output',str(dest),*args]),1)
                    self.assertFalse(dest.exists())
            protected=root/'validated'/'new_references.jsonl'
            protected.parent.mkdir()
            protected.write_text('DO NOT OVERWRITE')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['generate','--with-reference-answers',
                    '--output',str(dest)]),1)
            self.assertEqual(protected.read_text(),'DO NOT OVERWRITE')
            self.assertFalse(dest.exists())

if __name__ == '__main__': unittest.main()
