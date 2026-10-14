"""Deterministic, offline 0.6.7.8 paired-report regression tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from benchmark.cli import build_parser
from benchmark.scorable import score_scorable
from benchmark.paired_analysis import _spread, _exact_mcnemar, paired_plot_paths
from benchmark.validator import atomic_jsonl, load_jsonl, ValidationError

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'datasets/generated/scorable_50.jsonl'
ORACLE=ROOT/'datasets/gold/scorable_50_reference_oracle.jsonl'
PILOT=ROOT/'datasets/agent/scorable_50_gpt52_runs.jsonl.progress.jsonl'


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))


class Paired0678(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name)
        self.opts={
            'overall_csv':self.root/'overall.csv',
            'mcp_ab_summary_csv':self.root/'mcp.csv',
            'paired_questions_csv':self.root/'paired.csv',
            'paired_summary_csv':self.root/'pairsummary.csv',
            'mismatch_audit_csv':self.root/'audit.csv',
            'paired_plots_dir':self.root/'charts'
        }
        self.output=self.root/'report.json'
        self.journal=PILOT

    def score(self,**overrides):
        kwargs={**self.opts,**overrides}
        return score_scorable(TASKS,ORACLE,self.journal,self.root/'comparison.csv',
            self.root/'summary.csv',self.output,**kwargs)

    def test_pilot_combined_csvs_paired_missing_values_and_plots(self):
        report=self.score()
        self.assertEqual(report['status'],'PARTIAL')
        self.assertEqual(report['mismatch_records'],4)
        self.assertEqual(len(read_csv(self.opts['overall_csv'])),3)
        self.assertEqual(len(read_csv(self.opts['mcp_ab_summary_csv'])),2)
        self.assertEqual(len(read_csv(self.opts['paired_questions_csv'])),50)
        self.assertEqual(len(read_csv(self.opts['paired_summary_csv'])),3)
        self.assertEqual(len(read_csv(self.opts['mismatch_audit_csv'])),4)
        first=read_csv(self.opts['paired_questions_csv'])[0]
        self.assertEqual(first['A_reference_match'],'True')
        self.assertEqual(first['A_B_match_case'],'BOTH_MATCH')
        self.assertEqual(first['B_minus_A_mcp_attempts'],'0.0')
        self.assertEqual(read_csv(self.opts['paired_questions_csv'])[5]['A_reference_match'],'')
        self.assertEqual(read_csv(self.opts['paired_questions_csv'])[5]['B_minus_A_runtime_seconds'],'')
        summary=read_csv(self.opts['paired_summary_csv'])[0]
        self.assertEqual(summary['correctness_paired_questions'],'5')
        self.assertEqual(summary['not_paired'],'45')
        self.assertEqual(summary['exact_mcnemar_two_sided_p'],'1.0')
        self.assertEqual(read_csv(self.opts['overall_csv'])[2]['mean_mcp_tool_calls_per_attempt'],'')
        for img in paired_plot_paths(self.opts['paired_plots_dir']):
            self.assertGreater(img.stat().st_size,1000)

    def test_missing_arm_record_not_false_negative_or_zero_latency(self):
        data,_=load_jsonl(PILOT)
        self.journal=self.root/'single.jsonl'
        atomic_jsonl(self.journal,[data[0]])
        self.score()
        pair=read_csv(self.opts['paired_questions_csv'])[0]
        self.assertEqual(pair['B_match_status'],'NOT_RUN')
        self.assertEqual(pair['B_reference_match'],'')
        self.assertEqual(pair['B_total_tokens'],'')
        self.assertEqual(pair['B_minus_A_runtime_seconds'],'')
        self.assertEqual(pair['A_B_match_case'],'NOT_PAIRED')
        self.assertEqual(read_csv(self.opts['paired_summary_csv'])[0]['correctness_paired_questions'],'0')
        self.assertEqual(read_csv(self.opts['paired_summary_csv'])[0]['exact_mcnemar_two_sided_p'],'')

    def test_mismatch_audit_uses_observable_classes_no_scientific_claim(self):
        data,_=load_jsonl(PILOT)
        self.journal=self.root/'synthetic.jsonl'
        x={**data[0], 'answer':{'answer':'refused','abstained':True,'answer_values':None}}
        atomic_jsonl(self.journal,[x])
        self.score()
        audit=read_csv(self.opts['mismatch_audit_csv'])
        self.assertEqual(len(audit),1)
        self.assertEqual(audit[0]['observed_category'],'ABSTAIN')
        self.assertEqual(audit[0]['review_status'],'PENDING_INDEPENDENT_REVIEW')
        self.assertEqual(audit[0]['scientific_cause'],'')

    def test_statistics_and_exact_mcnemar(self):
        self.assertEqual(_exact_mcnemar(0,1),1.0)
        self.assertAlmostEqual(_exact_mcnemar(0,36),2/2**36,places=20)
        self.assertEqual(_exact_mcnemar(0,0),1.0)
        self.assertEqual(_spread([],1)['median'],'')
        self.assertEqual(_spread([2,4],1)['median'],3)
        self.assertEqual(_spread([1,2,3],1),_spread([1,2,3],1))

    def test_output_preflight_and_cli_options(self):
        self.score()
        with self.assertRaises(ValidationError):self.score()
        self.assertEqual(self.score(replace=True)['status'],'PARTIAL')
        with self.assertRaises(ValidationError):
            self.score(overall_csv=self.opts['paired_plots_dir']/'paired_runtime_deltas.png',replace=True)
        parser=build_parser()
        args=parser.parse_args(['score-scorable','--tasks','t','--oracle','o','--runs','r',
            '--comparison-csv','c','--summary-csv','s','--report','j',
            '--overall-csv','x','--mcp-ab-summary-csv','y','--paired-questions-csv','z',
            '--paired-summary-csv','p','--mismatch-audit-csv','e','--paired-plots-dir','figs'])
        self.assertEqual(args.mcp_ab_summary_csv,Path('y'))
        self.assertEqual(args.paired_plots_dir,Path('figs'))

if __name__=='__main__': unittest.main()
