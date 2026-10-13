"""0.6.2: CLI generation/validation CSV+JSON export and observable progress."""
import asyncio
import csv
import contextlib
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark.cli import build_parser, main
from benchmark.exports import check_destinations, save_views
from benchmark.tests.test_generator import run_fixture
from benchmark.tests.test_reference_validation import fake_factory, no_wait, make_test_dataset
from benchmark.validator import ValidationError, load_jsonl, validate


class Export062Tests(unittest.TestCase):
    def test_generated_csv_and_pretty_match_source(self):
        (candidates, _), _ = run_fixture(count=50)
        with TemporaryDirectory() as d:
            root = Path(d)
            pretty, flat = root/'queries_pretty.json', root/'queries.csv'
            save_views(candidates, pretty=pretty, csv_path=flat)
            self.assertEqual(json.loads(pretty.read_text()), candidates)
            self.assertIn("\n  {", pretty.read_text())
            with flat.open(newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 50)
            self.assertEqual(rows[0]['question'], candidates[0]['question'])
            self.assertEqual(json.loads(rows[1]['mcp_parameters_json']),
                             candidates[1]['reference_call']['arguments']['params'])

    def test_csv_formula_injection_escaped(self):
        from benchmark.exports import atomic_csv
        with TemporaryDirectory() as d:
            path=Path(d)/'a.csv'
            atomic_csv(path,[{'question':'=HYPERLINK("x")'}],('question',))
            with path.open(newline='') as f:
                self.assertEqual(next(csv.DictReader(f))['question'], "'=HYPERLINK(\"x\")")

    def test_invalid_path_no_write_and_duplicate_fails(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(ValidationError,'collision'):
                check_destinations(None, root/'a.json',None,root/'a.json',None)
            with self.assertRaisesRegex(ValidationError,'end in .csv'):
                check_destinations(None,root/'a.jsonl',None,None,root/'x.json')
            path=root/'a.json'
            path.write_text('PRESERVE')
            with self.assertRaisesRegex(ValidationError,'exists'):
                check_destinations(None,root/'a.jsonl',None,path,None)
            self.assertEqual(path.read_text(),'PRESERVE')

    def test_generation_command_with_both_exports(self):
        from benchmark.cli import _execute
        from benchmark.tests.test_generator import run_fixture
        (candidates, report), _ = run_fixture(count=5)
        async def fake_generate(*args,**kwargs):
            return candidates, dict(report)
        with TemporaryDirectory() as d, patch('benchmark.generator.generate') as _:
            root=Path(d)
            args=build_parser().parse_args(['generate','--count','5','--output',str(root/'a.jsonl'),
                                             '--csv-output',str(root/'a.csv'),
                                             '--pretty-output',str(root/'a_pretty.json')])
            with patch('benchmark.cli.generate',fake_generate):
                result=asyncio.run(_execute(args))
            records,sha=load_jsonl(root/'a.jsonl')
            self.assertEqual(len(records),5)
            self.assertEqual(result['dataset_sha256'],sha)
            self.assertEqual(json.loads((root/'a_pretty.json').read_text()),records)
            with (root/'a.csv').open(newline='') as f:
                self.assertEqual(len(list(csv.DictReader(f))),5)

    def test_validation_partial_resume_exports_progress_and_canonical_hash(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            dataset,cases=make_test_dataset(root,5)
            output,report=root/'refs.jsonl',root/'report.json'
            pretty,csv_out=root/'refs_pretty.json',root/'refs.csv'
            messages=[]
            kwargs=dict(attempts=1,delay=0,session_factory=fake_factory(), sleep=no_wait,
                        pretty_output=pretty,csv_output=csv_out,progress=messages.append)
            first=asyncio.run(validate(dataset,output,report,limit=2,**kwargs))
            self.assertEqual(first['status'],'PARTIAL')
            self.assertEqual(len(json.loads(pretty.read_text())),2)
            self.assertFalse(output.exists())
            second=asyncio.run(validate(dataset,output,report,resume=True,**kwargs))
            self.assertEqual(second['status'],'COMPLETE')
            refs,sha=load_jsonl(output)
            self.assertEqual(second['reference_answers_sha256'],sha)
            self.assertEqual(json.loads(pretty.read_text()),refs)
            with csv_out.open(newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),5)
            self.assertEqual(rows[0]['question'],cases[0]['question'])
            self.assertTrue(any('preflight' in s for s in messages))
            self.assertEqual(len([s for s in messages if s.startswith('DONE')]),5)

    def test_help_exposes_new_options(self):
        gen=build_parser().parse_args(['generate','--csv-output','a.csv','--pretty-output','b.json'])
        val=build_parser().parse_args(['validate','--csv-output','a.csv','--pretty-output','b.json'])
        self.assertEqual(gen.csv_output,Path('a.csv'))
        self.assertEqual(val.pretty_output,Path('b.json'))
        self.assertFalse(val.quiet_progress)

if __name__=='__main__':
    unittest.main()

class Timeout062Tests(unittest.TestCase):
    def test_unresponsive_archive_attempt_is_bounded_and_reported(self):
        from benchmark.tests.test_reference_validation import make_test_dataset
        from benchmark.validator import execute_task
        from benchmark.tests.test_reference_validation import ValidatingSession
        class StalledSession(ValidatingSession):
            async def call_tool(self, name, args, *, timeout=None):
                if name == 'astroquery_execute':
                    await asyncio.sleep(1)
                return await super().call_tool(name, args, timeout=timeout)
        with TemporaryDirectory() as d:
            _, cases = make_test_dataset(Path(d), 1)
            result = asyncio.run(execute_task(cases[0], url='http://127.0.0.1:8000/mcp',
                timeout=0.025, attempts=1, delay=0, max_rows=20,
                max_response_bytes=100000, session_factory=lambda url: StalledSession(url),
                sleep=no_wait))
            self.assertEqual(result['disposition'], 'transport_error')
            self.assertIn('timed out', result['error']['message'])
