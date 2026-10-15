"""0.5.1 regression tests for persisted human-readable score export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmark.cli import build_parser
from benchmark.evaluator import EvaluationError, evaluate

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'benchmark/tests/fixtures/legacy/generated/synthetic_queries.jsonl'
REFERENCES = ROOT / 'benchmark/tests/fixtures/legacy/validated/reference_answers.jsonl'
RUNS = ROOT / 'benchmark/tests/fixtures/legacy/agent/openai_041_runs.jsonl.progress.jsonl'


class PrettyExport051Tests(unittest.TestCase):
    def test_option_is_optional_and_explicit(self):
        parser = build_parser()
        self.assertIsNone(parser.parse_args(['evaluate']).pretty_output)
        args = parser.parse_args(['evaluate', '--json-format', 'compact',
                                  '--pretty-output', 'datasets/evaluation/scores_pretty.json'])
        self.assertEqual(args.pretty_output, Path('datasets/evaluation/scores_pretty.json'))
        self.assertEqual(args.json_format, 'compact')

    def test_saved_pretty_array_matches_compact_records(self):
        candidate_hash = hashlib.sha256(TASKS.read_bytes()).hexdigest()
        reference_hash = hashlib.sha256(REFERENCES.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            compact, pretty = base/'scores.jsonl', base/'scores_pretty.json'
            report = evaluate(TASKS,REFERENCES,RUNS,compact,base/'report.json',
                              csv_path=base/'scores.csv',pretty_output=pretty,
                              strict_accepted_020=True,json_format='compact')
            pretty_text = pretty.read_text(encoding='utf-8')
            compact_lines = compact.read_text(encoding='utf-8').splitlines()
            self.assertTrue(pretty_text.startswith('[\n  {'))
            self.assertEqual(len(compact_lines), 5)
            self.assertTrue(all(line.startswith('{') and '\n' not in line for line in compact_lines))
            self.assertEqual(json.loads(pretty_text),[json.loads(line) for line in compact_lines])
            self.assertEqual(json.loads((base/'report.json').read_text())['pretty_output'],str(pretty))
            self.assertEqual(report['mean_technical_score'], 94.0)
            self.assertEqual(report['technical_gates'], {'PASS':3,'REVIEW':2})
            self.assertEqual(hashlib.sha256(TASKS.read_bytes()).hexdigest(), candidate_hash)
            self.assertEqual(hashlib.sha256(REFERENCES.read_bytes()).hexdigest(), reference_hash)
            self.assertEqual(candidate_hash, 'e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9')
            self.assertEqual(reference_hash, '1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87')

    def test_output_is_still_optional_and_jsonl_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            report = evaluate(TASKS,REFERENCES,RUNS,base/'scores.jsonl',base/'summary.json',
                              json_format='pretty',strict_accepted_020=True)
            self.assertNotIn('pretty_output',report)
            self.assertEqual(len((base/'scores.jsonl').read_text().splitlines()),5)
            self.assertTrue((base/'summary.json').read_text().startswith('{\n'))

    def test_refuse_duplicate_paths_or_invalid_extension_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            out=base/'scores.jsonl'; report=base/'report.json'
            for invalid in (report, REFERENCES, base/'out.jsonl', out):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(EvaluationError):
                        evaluate(TASKS,REFERENCES,RUNS,out,report,pretty_output=invalid)
                    self.assertFalse(out.exists())
                    self.assertFalse(report.exists())

    def test_no_overwrite_and_preserve_prior_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); output=base/'scores.jsonl'; report=base/'report.json'; pretty=base/'scores_pretty.json'
            pretty.write_text('PREEXISTING',encoding='utf-8')
            with self.assertRaisesRegex(EvaluationError, 'already exist'):
                evaluate(TASKS,REFERENCES,RUNS,output,report,pretty_output=pretty)
            self.assertEqual(pretty.read_text(),'PREEXISTING')
            self.assertFalse(output.exists())
            scored=evaluate(TASKS,REFERENCES,RUNS,output,report,pretty_output=pretty,replace=True)
            self.assertEqual(scored['evaluated_tasks'],5)
            self.assertIsInstance(json.loads(pretty.read_text()),list)

    def test_cli_writes_file_not_just_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            command=[sys.executable, '-m', 'benchmark', 'evaluate',
                     '--tasks',str(TASKS),'--references',str(REFERENCES),'--runs',str(RUNS),
                     '--output',str(base/'scores.jsonl'), '--report',str(base/'report.json'),
                     '--csv',str(base/'scores.csv'), '--pretty-output',str(base/'pretty.json'),
                     '--strict-accepted-020','--json-format','compact']
            completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(completed.returncode,0,completed.stderr+' '+completed.stdout)
            self.assertEqual(len(json.loads((base/'pretty.json').read_text())),5)
            self.assertNotIn('\n  "',completed.stdout)  # stdout remains compact
            self.assertIn('pretty_output',json.loads(completed.stdout))

if __name__=='__main__': unittest.main()
