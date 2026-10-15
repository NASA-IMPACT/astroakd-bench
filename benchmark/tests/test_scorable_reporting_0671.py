"""Offline regression of side-by-side answers, performance CSV and barplots."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from benchmark.scorable import score_scorable
from benchmark.validator import atomic_jsonl, load_jsonl, ValidationError
from benchmark.cli import build_parser

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'benchmark/tests/fixtures/legacy/generated/scorable_50.jsonl'
ORACLE=ROOT/'benchmark/tests/fixtures/legacy/gold/scorable_50_reference_oracle.jsonl'

class Reporting0671(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        tasks,self.digest=load_jsonl(TASKS)
        self.task=tasks[0]
        gold,_=load_jsonl(ORACLE)
        self.key=gold[0]['gold']
        correct=dict(answer='matches',answer_values=self.key['values'],unit=self.key.get('unit'),
                     abstained=False,parse_status='structured',sources=['archive:record-1'])
        conflict=dict(answer='324.0',answer_values=[324.0],unit='s',abstained=True,
                      parse_status='structured',sources=['https://example.com'])
        bad=dict(answer='unstructured response',answer_values=None,abstained=False,
                 sources=[],parse_status='unstructured')
        self.runs=[dict(task_id=self.task['id'],arm=arm,model='gpt-5.2',status='completed',
                         candidate_sha256=self.digest,answer=answer,
                         trace=trace, duration_seconds=duration,
                         token_usage=tokens) for arm,answer,trace,duration,tokens in [
            ('mcp_only',correct,[{'tool':'astroquery_execute','status':'ok','response_success':True}],10,
                dict(total_tokens=1000,prompt_tokens=900,completion_tokens=100)),
            ('mcp_instruction',bad,[{'tool':'astroquery_execute','status':'rejected'}],20,
                dict(total_tokens=2000,prompt_tokens=1700,completion_tokens=300)),
            ('web_only',conflict,[{'tool':'openai_web_search','web_search_calls':3,'status':'ok'}],30,
                dict(total_tokens=700,input_tokens=650,output_tokens=50)),
        ]]
        self.runs_path=self.p/'runs.jsonl'
        atomic_jsonl(self.runs_path,self.runs)
        self.outputs=dict(
            comparison_csv=self.p/'comparison.csv',summary_csv=self.p/'summary.csv',
            detail_csv=self.p/'details.csv',performance_csv=self.p/'performance.csv',
            task_performance_csv=self.p/'per_task.csv',plots_dir=self.p/'plots',
        )
        self.report=self.p/'report.json'
    def score(self,**overrides):
        params={**self.outputs,**overrides}
        return score_scorable(TASKS,ORACLE,self.runs_path,params.pop('comparison_csv'),
             params.pop('summary_csv'),self.report,**params)
    @staticmethod
    def csvrows(p):
        with p.open(encoding='utf-8',newline='') as f:
            return list(csv.DictReader(f))
    def test_detail_rows_full_answers_and_conflicting_abstention(self):
        r=self.score()
        self.assertEqual(r['status'],'PARTIAL')
        detail=self.csvrows(self.outputs['detail_csv'])
        self.assertEqual(len(detail),150)
        self.assertEqual(detail[0]['reference_match'],'True')
        self.assertEqual(detail[1]['answer_text'],'unstructured response')
        self.assertEqual(detail[2]['answer_text'],'324.0')
        self.assertEqual(detail[2]['answer_disposition'],'ABSTAIN_WITH_VALUES')
        self.assertEqual(detail[2]['match_status'],'ABSTAIN')
        self.assertEqual(detail[3]['run_status'],'not_run')
        self.assertEqual(detail[3]['reference_match'],'')
        self.assertIn('archive:record-1',detail[0]['source_identifiers_json'])
        self.assertIn('astroquery_execute',detail[0]['tool_event_summary_json'])
        perf=self.csvrows(self.outputs['performance_csv'])
        self.assertEqual(len(perf),3)
        self.assertEqual([v['mean_runtime_seconds'] for v in perf],['10.0','20.0','30.0'])
        self.assertEqual([v['total_tokens'] for v in perf],['1000','2000','700'])
        self.assertEqual([v['web_search_calls'] for v in perf],['0','0','3'])
        self.assertEqual([v['reference_match_pct_attempted'] for v in perf],['100.0','0.0','0.0'])
        self.assertEqual(len(self.csvrows(self.outputs['task_performance_csv'])),150)
    def test_barplots_png_and_svg_have_content(self):
        self.score()
        for name in ('match_rate','mean_runtime','total_tokens'):
            self.assertGreater((self.outputs['plots_dir']/(name+'.png')).stat().st_size,5000)
            self.assertIn('<svg',(self.outputs['plots_dir']/(name+'.svg')).read_text()[:1000])
    def test_overwrite_protection_on_any_requested_output(self):
        self.score()
        with self.assertRaises(ValidationError):self.score(replace=False)
        report=self.score(replace=True)
        self.assertEqual(report['arms']['mcp_only']['correct'],1)
        self.assertEqual(report['arms']['mcp_only']['reference_match_pct_all_questions'],2)
    def test_destination_collision_catches_plot(self):
        conflict=self.outputs['plots_dir']/'match_rate.png'
        with self.assertRaises(ValidationError):self.score(detail_csv=conflict)
        self.assertFalse(self.report.exists())
    def test_empty_run_stats_and_charts_no_false_100_pct(self):
        empty=self.p/'one_run.jsonl';atomic_jsonl(empty,self.runs[:1])
        self.runs_path=empty
        result=self.score()
        perf=self.csvrows(self.outputs['performance_csv'])
        self.assertEqual([row['attempted'] for row in perf],['1','0','0'])
        self.assertTrue(all(row['mean_runtime_seconds']=='' for row in perf[1:]))
        self.assertTrue(all(row['reference_match_pct_attempted']=='' for row in perf[1:]))
        self.assertEqual(result['runs_recorded'],1)
    def test_cli_options_parsed(self):
        a=build_parser().parse_args(['score-scorable','--tasks','t','--oracle','o','--runs','r',
          '--comparison-csv','c','--summary-csv','s','--report','j',
          '--detailed-csv','d','--performance-csv','p',
          '--task-performance-csv','pt','--plots-dir','plots'])
        self.assertEqual(a.detailed_csv,Path('d'))
        self.assertEqual(a.plots_dir,Path('plots'))

if __name__=='__main__':unittest.main()
