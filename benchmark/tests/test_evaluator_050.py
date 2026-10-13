"""0.5.0 offline evaluation, formatting, frozen datasets and failure tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from benchmark.evaluator import (EvaluationError, _param_check, score_task, evaluate, _result_counts)
from benchmark.formatting import json_text, inspect_file
from benchmark.validator import atomic_json, atomic_jsonl, EXPECTED_ACCEPTED_020_SHA256
from benchmark.cli import build_parser

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'datasets/generated/synthetic_queries.jsonl'
REFS=ROOT/'datasets/validated/reference_answers.jsonl'
RUNS=ROOT/'datasets/agent/openai_041_runs.jsonl.progress.jsonl'

class Evaluation050Tests(unittest.TestCase):
    def test_accepted_dataset_fingerprints_survive_root_move(self):
        self.assertEqual(hashlib.sha256(TASKS.read_bytes()).hexdigest(),EXPECTED_ACCEPTED_020_SHA256)
        self.assertEqual(hashlib.sha256(REFS.read_bytes()).hexdigest(),
            '1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87')

    def test_actual_five_task_pilot(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            report=evaluate(TASKS,REFS,RUNS,root/'scores.jsonl',root/'report.json',
                            csv_path=root/'scores.csv',strict_accepted_020=True,json_format='pretty')
            self.assertEqual(report['evaluated_tasks'],5)
            self.assertEqual(report['technical_gates'],{'PASS':3,'REVIEW':2})
            self.assertEqual(report['status'],'PARTIAL')
            self.assertEqual(report['scientific_answer_gate'],'INDEPENDENT_REVIEW_REQUIRED')
            score=[json.loads(v) for v in (root/'scores.jsonl').read_text().splitlines()]
            self.assertEqual([x['module'] for x in score],['simbad','mast','heasarc','gaia','vizier'])
            self.assertEqual(score[3]['result_agreement'],'INDETERMINATE_TRUNCATED')
            self.assertEqual(score[3]['technical_gate'],'REVIEW')
            self.assertIn('\n  "evaluated_tasks": 5', (root/'report.json').read_text())
            self.assertEqual(len((root/'scores.csv').read_text().splitlines()),6)
            with self.assertRaises(EvaluationError):
                evaluate(TASKS,REFS,RUNS,root/'scores.jsonl',root/'report.json')

    def test_json_format_and_bounded_inspection(self):
        value={'name':'M31','nested':{'radius':3}}
        self.assertNotIn('\n',json_text(value,'compact'))
        self.assertIn('\n  "nested"',json_text(value,'pretty'))
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'records.jsonl'
            atomic_jsonl(f,[{'a':1},{'a':2},{'a':3}])
            original=f.read_bytes()
            rec=inspect_file(f,2)
            self.assertEqual(rec['records_shown'],2)
            self.assertEqual(rec['records_total'],3)
            self.assertEqual(f.read_bytes(),original)
            atomic_json(Path(d)/'report.json',value,style='pretty')
            self.assertIn('\n', (Path(d)/'report.json').read_text())
            with self.assertRaises(ValueError):inspect_file(f,0)
            with self.assertRaises(ValueError):json_text(value,'yaml')

    def test_root_cli_defaults_and_pretty_option(self):
        parser=build_parser()
        for cmd in ('generate','validate','run','evaluate'):
            args=parser.parse_args([cmd,'--json-format','pretty'])
            self.assertEqual(args.json_format,'pretty')
        self.assertEqual(parser.parse_args(['generate']).output,TASKS.relative_to(ROOT))
        self.assertEqual(parser.parse_args(['validate']).output,Path('datasets/validated/reference_answers.jsonl'))
        self.assertEqual(parser.parse_args(['run']).output,Path('datasets/agent/agent_runs.jsonl'))
        self.assertEqual(parser.parse_args(['evaluate']).output,Path('datasets/evaluation/task_scores.jsonl'))

    def test_semantic_parameters_allow_omitted_default_icrs(self):
        expected={'coordinates':{'ra':10.,'dec':-2.,'frame':'icrs'},'radius':{'value':2,'unit':'arcmin'}}
        actual={'coordinates':{'ra':10.00002,'dec':-2.00003},'radius':{'unit':'arcmin','value':2.}}
        self.assertEqual(_param_check(expected,actual)['fraction'],1.)
        actual['radius']['value']=3
        self.assertLess(_param_check(expected,actual)['fraction'],1)

    def test_different_module_not_credit_and_missing_answer_failure(self):
        task=json.loads(TASKS.read_text().splitlines()[0]); ref=json.loads(REFS.read_text().splitlines()[0])
        run=json.loads(RUNS.read_text().splitlines()[0]); wrong=copy.deepcopy(run)
        wrong['trace'][0]['arguments']['module_name']='vizier'
        scored=score_task(task,ref,wrong)
        self.assertEqual(scored['metric_scores']['archive_selection'],0)
        self.assertEqual(scored['technical_gate'],'FAIL')
        run['answer']=''
        self.assertEqual(score_task(task,ref,run)['technical_gate'],'FAIL')

    def test_rejected_then_successful_same_query_prefers_success(self):
        task=json.loads(TASKS.read_text().splitlines()[0]); ref=json.loads(REFS.read_text().splitlines()[0])
        run=json.loads(RUNS.read_text().splitlines()[0])
        rejected=copy.deepcopy(run['trace'][0]); rejected.update({'status':'rejected','response_success':False})
        run['trace'].insert(0,rejected)
        self.assertEqual(score_task(task,ref,run)['technical_gate'],'PASS')

    def test_no_full_answer_scoring_from_simple_evidence(self):
        task=json.loads(TASKS.read_text().splitlines()[3]); ref=json.loads(REFS.read_text().splitlines()[3])
        run=json.loads(RUNS.read_text().splitlines()[3]);result=score_task(task,ref,run)
        self.assertEqual(result['scientific_answer_gate'],'INDEPENDENT_REVIEW_REQUIRED')
        self.assertEqual(result['answer_claim_check']['status'],'TRUNCATION_DISCLOSED')

    def test_reject_unknown_duplicate_or_corrupt_agent_trace(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); out=p/'scores.jsonl'; rep=p/'report.json'
            rows=[json.loads(v) for v in RUNS.read_text().splitlines()]
            rows[0]['trace'][0]['response']['result']['row_count']=987
            input_file=p/'runs.jsonl'; atomic_jsonl(input_file,rows)
            with self.assertRaisesRegex(EvaluationError,'fingerprint mismatch'):
                evaluate(TASKS,REFS,input_file,out,rep)
            self.assertFalse(out.exists())
            rows[0]['trace'][0]['response']['result']['row_count']=1
            rows[0]['task_id']='unrecognized-task'
            atomic_jsonl(input_file,rows,replace=True)
            with self.assertRaisesRegex(EvaluationError,'Unknown or duplicate'):
                evaluate(TASKS,REFS,input_file,out,rep)

    def test_no_leak_gold_in_agent_runs(self):
        data=RUNS.read_text()
        self.assertNotIn('reference_call',data)
        self.assertNotIn('accepted_nonempty',data)

if __name__=='__main__':unittest.main()
