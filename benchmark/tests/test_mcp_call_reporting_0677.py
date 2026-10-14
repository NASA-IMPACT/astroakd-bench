"""Regression of per-query MCP event CSVs, A/B frequency and call-mean plots."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from benchmark.scorable import score_scorable
from benchmark.cli import build_parser
from benchmark.validator import atomic_jsonl, load_jsonl, ValidationError
from benchmark.scorable_diagnostics import plot_paths

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'datasets/generated/scorable_50.jsonl'
ORACLE=ROOT/'datasets/gold/scorable_50_reference_oracle.jsonl'
PILOT=ROOT/'datasets/agent/scorable_50_gpt52_runs.jsonl.progress.jsonl'


def rows(path):
    with path.open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


class MCPReporting0677(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.outputs=dict(comparison_csv=self.root/'comparison.csv',
                          summary_csv=self.root/'rates.csv',
                          detail_csv=self.root/'details.csv',
                          performance_csv=self.root/'performance.csv',
                          task_performance_csv=self.root/'per_task.csv',
                          mcp_calls_csv=self.root/'mcp_calls.csv',
                          mcp_tool_frequency_csv=self.root/'mcp_frequencies.csv',
                          plots_dir=self.root/'plots')
    def score(self,run_path=PILOT,**overrides):
        params={**self.outputs,**overrides}
        return score_scorable(TASKS,ORACLE,run_path,params.pop('comparison_csv'),
                              params.pop('summary_csv'),self.root/'report.json',**params)

    def test_existing_saved_pilot_exact_events_and_frequencies(self):
        result=self.score()
        calls=rows(self.outputs['mcp_calls_csv'])
        self.assertEqual(len(calls),12)
        self.assertEqual([sum(c['arm']==arm for c in calls) for arm in ('mcp_only','mcp_instruction')],[6,6])
        self.assertTrue(all(c['tool_name']=='astroquery_execute' for c in calls))
        self.assertEqual(set(c['status'] for c in calls),{'ok','rejected'})
        self.assertEqual(sum(c['successful_mcp_call']=='True' for c in calls),10)
        self.assertEqual(sum(c['status']=='rejected' for c in calls),2)
        self.assertIn('mast.query_region',calls[0]['tool_signature'])
        self.assertIn('module_name',calls[0]['arguments_json'])
        freq=rows(self.outputs['mcp_tool_frequency_csv'])
        self.assertEqual(len(freq),4)
        self.assertEqual(sum(int(x['A_attempts']) for x in freq),6)
        self.assertEqual(sum(int(x['B_attempts']) for x in freq),6)
        self.assertEqual({(x['A_attempts'],x['B_attempts']) for x in freq},{('1','1'),('2','2')})
        perf=rows(self.outputs['performance_csv'])
        self.assertEqual([x['total_mcp_tool_attempts'] for x in perf],['6','6','0'])
        self.assertEqual([x['mean_mcp_tool_calls_per_attempt'] for x in perf],['1.2','1.2',''])
        self.assertEqual([x['mean_successful_mcp_calls_per_attempt'] for x in perf],['1.0','1.0',''])
        detail=rows(self.outputs['detail_csv'])
        self.assertEqual(len(detail),150)
        self.assertEqual(json.loads(detail[0]['mcp_tool_names_json']),['astroquery_execute','astroquery_execute'])
        self.assertEqual(rows(self.outputs['task_performance_csv'])[2]['mcp_tool_attempts'],'0')
        self.assertEqual(result['mcp_tool_attempts_recorded'],12)
        self.assertEqual(len(result['mcp_tool_frequencies']),4)
        for plot in plot_paths(self.outputs['plots_dir']):
            self.assertGreater(plot.stat().st_size,3000)

    def test_rejects_and_errors_not_silently_counted_successful(self):
        original,_=load_jsonl(PILOT)
        initial=original[0]
        original=[{**initial,'trace':initial['trace']+[
            {'index':3,'tool':'astroquery_list_modules','status':'error','error_type':'RuntimeError',
             'error':'test','arguments':{}},
            {'index':4,'tool':'astroquery_execute','status':'ok','response_success':False,
             'arguments':{'module_name':'mast','function_name':'query_region'}}]}]
        p=self.root/'synthetic.jsonl';atomic_jsonl(p,original)
        self.score(p)
        calls=rows(self.outputs['mcp_calls_csv'])
        self.assertEqual(len(calls),4)
        self.assertEqual([c['successful_mcp_call'] for c in calls],['False','True','False','False'])
        perf=rows(self.outputs['performance_csv'])
        self.assertEqual(perf[0]['mean_mcp_tool_calls_per_attempt'],'4.0')
        self.assertEqual(perf[0]['mean_successful_mcp_calls_per_attempt'],'1.0')
        self.assertEqual(perf[0]['attempted'],'1')
        self.assertEqual(perf[1]['attempted'],'0')
        self.assertEqual(perf[1]['mean_mcp_tool_calls_per_attempt'],'')
        freq=rows(self.outputs['mcp_tool_frequency_csv'])
        self.assertEqual(sum(int(row['A_errors']) for row in freq),1)
        self.assertEqual(sum(int(row['A_rejected']) for row in freq),1)
        self.assertEqual(sum(int(row['A_successful']) for row in freq),1)
        self.assertEqual(sum(int(row['B_attempts']) for row in freq),0)

    def test_no_calls_emits_headers_and_na_mean(self):
        initial,_=load_jsonl(PILOT)
        row={**initial[0],'trace':[]}
        p=self.root/'empty.jsonl';atomic_jsonl(p,[row]);self.score(p)
        self.assertEqual(rows(self.outputs['mcp_calls_csv']),[])
        self.assertEqual(rows(self.outputs['mcp_tool_frequency_csv']),[])
        perf=rows(self.outputs['performance_csv'])
        self.assertEqual(perf[0]['mean_mcp_tool_calls_per_attempt'],'0.0')
        self.assertEqual(perf[1]['mean_mcp_tool_calls_per_attempt'],'')
        for stem in ('mean_mcp_tool_calls','mcp_tool_calls_by_name'):
            self.assertGreater((self.outputs['plots_dir']/(stem+'.png')).stat().st_size,3000)

    def test_preflight_includes_new_plot_and_csv(self):
        self.score()
        with self.assertRaises(ValidationError):self.score()
        with self.assertRaises(ValidationError):
            self.score(mcp_calls_csv=self.outputs['plots_dir']/'mean_mcp_tool_calls.png',replace=True)
        # No datasets or earlier report should be rewritten by a failed preflight.
        self.assertEqual(self.score(replace=True)['status'],'PARTIAL')

    def test_cli_parse_new_exports(self):
        args=build_parser().parse_args(['score-scorable','--tasks','t','--oracle','o',
            '--runs','r','--comparison-csv','c','--summary-csv','s','--report','j',
            '--mcp-calls-csv','calls.csv','--mcp-tool-frequency-csv','tools.csv'])
        self.assertEqual(args.mcp_calls_csv,Path('calls.csv'))
        self.assertEqual(args.mcp_tool_frequency_csv,Path('tools.csv'))


if __name__=='__main__':unittest.main()
