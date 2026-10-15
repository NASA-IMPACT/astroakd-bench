"""0.6.7.11.1: bounded count scaling and custom artifact root (no network)."""
import asyncio
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from benchmark.mixed_generation import generate_mixed, parse_task_mix
from benchmark.tests.test_mixed_generation_065 import Responses, fake_research, FixtureSession
from benchmark.simple_workflows import create_queries, dataset_paths, reference_report
from benchmark.cli import build_parser


async def fixture_generator(*args, **kwargs):
    original = {k: v for k, v in kwargs.items()
                if k not in ('research_fn', 'llm_fn', 'openai_client_factory')}
    return await generate_mixed(*args, **original,
        session_factory=lambda url: FixtureSession(url),
        research_fn=fake_research,
        openai_client_factory=lambda: SimpleNamespace(responses=Responses()))


class ConfigurableGenerationTests(TestCase):
    def test_scaling_preserves_exact_100_and_multiple_smaller_sizes(self):
        self.assertEqual(parse_task_mix('balanced100',count=100),
            {'archive_driven':60, 'coordinate_driven':20, 'literature_driven':8, 'multi_archive':12})
        for n in (1,5,10,25,40,50,75,100):
            mix=parse_task_mix('balanced100',count=n)
            self.assertEqual(sum(mix.values()),n)
            self.assertLessEqual(mix['literature_driven'],8)
            if n < 30:
                self.assertEqual(mix['multi_archive'],0)
        with self.assertRaisesRegex(ValueError,'1..100'):  # actual error is GenerationError -> ValueError
            parse_task_mix('balanced100',count=101)

    def test_custom_folder_and_auto_name_real_generation_with_mocked_providers(self):
        with TemporaryDirectory() as folder:
            custom=Path(folder)/'research'/'session1'
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator):
                result=asyncio.run(create_queries(name=None,count=40,root=folder,
                    output_dir='research/session1',seed=20261018))
            files=dataset_paths(folder,'synthetic_40',output_dir='research/session1')
            self.assertEqual(files['tasks'], custom/'generated'/'synthetic_40.jsonl')
            self.assertEqual(len(files['tasks'].read_text().splitlines()),40)
            self.assertEqual(len(files['single_calls'].read_text().splitlines()),32)
            self.assertEqual(len(files['multistep'].read_text().splitlines()),8)
            self.assertTrue(files['tasks_csv'].exists())
            self.assertTrue(files['generation_report'].exists())
            self.assertEqual(Path(result['task_dataset']),files['tasks'])
            rep=reference_report(root=folder,name='synthetic_40',output_dir='research/session1',plots=False)
            self.assertTrue(files['plots'].joinpath('references','reference_summary.json').exists())
            self.assertEqual(rep['total_questions'],40)
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator):
                with self.assertRaises(FileExistsError):
                    asyncio.run(create_queries(count=40,root=folder,output_dir='research/session1'))

    def test_user_supplied_absolute_output_folder(self):
        with TemporaryDirectory() as folder:
            p=dataset_paths(root='.',name='custom_test',output_dir=folder)
            self.assertEqual(p['tasks'],Path(folder)/'generated/custom_test.jsonl')
            self.assertEqual(p['runs'],Path(folder)/'agent/custom_test_ABC_runs.jsonl')
            self.assertEqual(p['plots'],Path(folder)/'reports/custom_test')

    def test_cli_accepts_directory_on_every_short_workflow(self):
        parser=build_parser()
        for command in ('create-queries','collect-references','reference-report','run-benchmark','agent-report'):
            a=parser.parse_args([command,'--output-dir','/tmp/project_data'])
            self.assertEqual(a.output_dir,Path('/tmp/project_data'))
        a=parser.parse_args(['create-queries','--count','40','--output-dir','study_data'])
        self.assertEqual(a.count,40)
        self.assertIsNone(a.name)

    def test_mocked_scale_composition(self):
        for count in (10,50):
            mix=parse_task_mix('balanced100',count=count)
            tasks,_=asyncio.run(fixture_generator(count=count,seed=20261018,mix=mix))
            self.assertEqual(dict(Counter(t['task_type'] for t in tasks)),
                             {k:v for k,v in mix.items() if v})
