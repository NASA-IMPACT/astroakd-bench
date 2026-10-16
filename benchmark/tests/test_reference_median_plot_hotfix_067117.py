"""Regression for median(empty) in reference-report and documentation of A/B/C plots."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from benchmark.simple_workflows import dataset_paths, reference_report

ROOT = Path(__file__).resolve().parents[2]


class ReferenceMedianPlotHotfixTests(TestCase):
    @skipUnless(importlib.util.find_spec('matplotlib') is not None,
                'optional matplotlib required for plot regression')
    def test_plots_when_all_reference_durations_missing(self):
        with TemporaryDirectory() as directory:
            paths = dataset_paths(root=directory, name='pilot')
            paths['tasks'].parent.mkdir(parents=True, exist_ok=True)
            paths['single_calls'].parent.mkdir(parents=True, exist_ok=True)
            single = {
                'id': 'T1', 'task_type': 'archive_driven', 'module': 'simbad',
                'target': 'M31', 'question': 'What is the main identifier?',
                'reference_call': {'tool': 'astroquery_execute', 'module': 'simbad'},
            }
            multi = {
                'id': 'T2', 'task_type': 'multi_archive', 'module': 'multi_archive',
                'target': 'M31', 'question': 'Compare two archives',
                'reference_call': None,
            }
            paths['tasks'].write_text(''.join(json.dumps(t) + '\n' for t in (single, multi)))
            paths['single_calls'].write_text(json.dumps(single) + '\n')
            report = reference_report(name='pilot', root=directory, plots=True)
            out = Path(report['output_dir'])
            self.assertEqual(report['total_questions'], 2)
            self.assertEqual(report['multistep_tasks'], 1)
            self.assertEqual(report['reference_records'], 0)
            self.assertEqual(report['reference_disposition_counts']['not_collected'], 1)
            self.assertEqual(report['reference_disposition_counts']['multistep_not_single_call_validated'], 1)
            for filename in ('reference_summary.json', 'response_times.png',
                             'response_time_distribution.png', 'questions_by_archive.png',
                             'reference_questions.csv', 'reference_archives.csv'):
                self.assertTrue((out / filename).is_file(), filename)
            with self.assertRaises(FileExistsError):
                reference_report(name='pilot', root=directory, plots=True)
            reference_report(name='pilot', root=directory, plots=True, replace=True)

    def test_current_readme_and_sphinx_guides_name_plot_commands(self):
        docs = [ROOT/'README.md', ROOT/'docs/benchmark/quickstart.md',
                ROOT/'docs/benchmark/evaluation_and_plots.md',
                ROOT/'docs/benchmark/references_and_review.md']
        texts = '\n'.join(path.read_text(encoding='utf-8') for path in docs)
        for expected in ('reference-report', 'agent-report', '--replace',
                         'response_times.png', 'mean_runtime.png', 'total_tokens.png',
                         'match_rate.png', 'completed_runs.png', 'gold'):
            self.assertIn(expected, texts, expected)
        self.assertIn('agent-report', (ROOT/'README.md').read_text())
        self.assertIn('reference-report', (ROOT/'README.md').read_text())
        self.assertIn('does **not**', (ROOT/'docs/benchmark/evaluation_and_plots.md').read_text())
