"""0.6.7.11.3 source-only dataset layout, hashes and self-creating workflows."""
import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from benchmark.cli import build_parser
from benchmark.simple_workflows import dataset_paths, create_queries, reference_report
from benchmark.tests.test_flexible_counts_067111 import fixture_generator
from benchmark.operational_report import create_operational_report
from benchmark.three_arm import run_three_arm
from benchmark.tests.test_gold_three_arm_066 import FakeMCP, FakeSDK

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'archives/historical_datasets_manifest_0_6_7_11_3.json'

class HistoricalDatasetCleanup(TestCase):
    def test_workspace_empty_and_all_history_indexed(self):
        p = ROOT / 'datasets'
        self.assertEqual(sorted(x.name for x in p.iterdir()), ['README.md'])
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(manifest['record_count'],118)
        self.assertEqual(len({f['path'] for f in manifest['files']}), 118)
        self.assertEqual(manifest['frozen_science']['generated/scorable_50.jsonl'],
            '4744ae4df40381eea635a92a13d8af6f83fd69c0e2274c839e1dbb04f382bbb8')
        self.assertEqual(manifest['frozen_science']['gold/scorable_50_reference_oracle.jsonl'],
            '58caf910963cdce4e333ae5a0a6d48501ece27bce71352b15664a10a76fc1d5e')
        self.assertFalse((ROOT/'datasets/generated/synthetic_queries.jsonl').exists())

    def test_essential_fixtures_have_original_archive_hashes(self):
        manifest = json.loads(MANIFEST.read_text())
        hash_by_path={f['path']:f['sha256'] for f in manifest['files']}
        base=ROOT/'benchmark/tests/fixtures/legacy'
        fixture_files=list(base.rglob('*'))
        fixture_files=[p for p in fixture_files if p.is_file()]
        self.assertEqual(len(fixture_files),9)
        for file in fixture_files:
            original='datasets/'+file.relative_to(base).as_posix()
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),hash_by_path[original])

    def test_exact_readme_command_parses_and_seed_is_optional(self):
        command=['create-queries','--name','astroakd_100','--count','100',
                 '--output-dir','datasets','--require-ads','--with-reference-answers']
        parser=build_parser()
        parsed=parser.parse_args(command)
        self.assertEqual(parsed.name,'astroakd_100')
        self.assertEqual(parsed.count,100)
        self.assertEqual(parsed.seed,20261018)
        self.assertTrue(parsed.require_ads and parsed.with_reference_answers)
        self.assertEqual(parsed.output_dir,Path('datasets'))
        self.assertIn('  --output-dir datasets \\', (ROOT/'README.md').read_text())
        with TemporaryDirectory() as tmp:
            files=dataset_paths(root=tmp,name=parsed.name,output_dir=parsed.output_dir)
            self.assertEqual(files['tasks'],Path(tmp)/'datasets/generated/astroakd_100.jsonl')
            self.assertFalse((Path(tmp)/'datasets/generated').exists())

    def test_generation_and_reference_report_create_dirs_automatically(self):
        with TemporaryDirectory() as tmp:
            work=Path(tmp)/'fresh'
            self.assertFalse(work.exists())
            with patch('benchmark.simple_workflows.generate_mixed',fixture_generator):
                asyncio.run(create_queries(root=tmp,output_dir='fresh',name='pilot',count=10))
            paths=dataset_paths(root=tmp,output_dir='fresh',name='pilot')
            self.assertTrue(paths['tasks'].is_file())
            self.assertFalse((work/'reports').exists())
            result=reference_report(root=tmp,output_dir='fresh',name='pilot',plots=False)
            self.assertEqual(result['total_questions'],10)
            self.assertTrue((work/'reports/pilot/references/reference_summary.json').exists())

    def test_abc_execution_and_reporting_create_dirs_automatically(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            work=root/'new_experiment'
            p=dataset_paths(root=root,name='abc',output_dir='new_experiment')
            p['tasks'].parent.mkdir(parents=True,exist_ok=True)
            task={'id':'T1','question':'What does SIMBAD return for M31?',
                  'task_type':'archive_driven','module':'simbad','target':'M31'}
            p['tasks'].write_text(json.dumps(task)+'\n')
            instruction=root/'instruction.md'
            instruction.write_text('AstroAKD science and archive instructions. '*20)
            self.assertFalse((work/'agent').exists())
            asyncio.run(run_three_arm(p['tasks'],instruction,p['runs'],p['run_report'],
                sdk=FakeSDK(),mcp_factory=FakeMCP))
            self.assertTrue(p['runs'].is_file())
            self.assertTrue(p['run_report'].is_file())
            self.assertFalse((work/'reports').exists())
            summary=create_operational_report(p['tasks'],p['runs'],p['plots']/'agents',plots=False)
            self.assertEqual(summary['runs_recorded'],3)
            self.assertTrue((work/'reports/abc/agents/operational_report.json').is_file())

class CollectionDirectory(TestCase):
    def test_collect_references_creates_validated_directory_without_manual_mkdir(self):
        from benchmark.simple_workflows import collect_references
        from benchmark.validator import validate as real_validate
        from benchmark.tests.test_reference_validation import fake_factory, no_wait
        from benchmark.tests.test_generator import run_fixture
        from benchmark.validator import atomic_jsonl
        candidates=run_fixture(count=5)[0][0]
        with TemporaryDirectory() as tmp:
            p=dataset_paths(root=tmp,name='example',output_dir='workspace')
            p['single_calls'].parent.mkdir(parents=True,exist_ok=True)
            atomic_jsonl(p['single_calls'],candidates)
            self.assertFalse(p['references'].parent.exists())
            async def offline_validate(*args, **kwargs):
                return await real_validate(*args,session_factory=fake_factory(),sleep=no_wait,**kwargs)
            with patch('benchmark.simple_workflows.validate',offline_validate):
                result=asyncio.run(collect_references(name='example',root=tmp,
                          output_dir='workspace',limit=5))
            self.assertTrue(p['references'].parent.is_dir())
            self.assertTrue(p['references'].is_file())
            self.assertTrue(p['references_csv'].is_file())
            self.assertEqual(result['processed'],5)
