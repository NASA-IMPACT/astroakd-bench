"""Regression: incomplete feasibility must be recoverable without repeated MCP calls."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from benchmark.reference_aware import select_reference_aware, _load_checkpoint
from benchmark.generator import BoundMethod, GenerationError
from benchmark.seeds import SkyTarget


class RecoveryTests(unittest.TestCase):
    def test_truncated_mast_falls_back_and_preserves_probe_journal(self):
        calls = []
        class Client:
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def call(self, tool, arguments):
                calls.append(arguments)
                if arguments['module_name'] == 'mast':
                    return {'success': True, 'module':'mast', 'function':'query_region',
                        'result':{'data':[{'obs_id':'a'}], 'row_count':1,
                                  'total_rows':500, 'truncated':True}}
                return {'success': True, 'module':'simbad', 'function':'query_object',
                    'result':{'data':[{'main_id':'a','matched_id':'b', 'ra':1.2, 'dec':3.4}],
                              'row_count':1, 'total_rows':1}}
        async def discover(client, modules):
            return {
                'simbad':BoundMethod('simbad','query_object',{'object':'object_name'},
                                     ({'name':'object_name','required':True},)),
                'mast':BoundMethod('mast','query_region',{'coordinate':'coordinates', 'radius':'radius'},
                                  ({'name':'coordinates','required':True}, {'name':'radius','required':False}))}
        seeds = (SkyTarget('M31', 10,20), SkyTarget('M33',20,30), SkyTarget('M51',30,40))
        with TemporaryDirectory() as temporary, \
             patch('benchmark.reference_aware.AstroqueryMCPClient', Client), \
             patch('benchmark.reference_aware.discover_bindings', discover):
            checkpoint = Path(temporary)/'generated'/'study_feasibility_progress.json'
            with self.assertRaisesRegex(GenerationError,'budget exhausted'):
                asyncio.run(select_reference_aware(None, count=3, seed=42,
                    modules=('simbad','mast'), timeout=30, targets=seeds,
                    max_probes=5, checkpoint_path=checkpoint))
            self.assertTrue(checkpoint.is_file())
            saved = json.loads(checkpoint.read_text())
            self.assertEqual(len(saved['selected']),2)
            self.assertEqual(len(saved['outcomes']),5)
            initial_calls = len(calls)
            self.assertEqual(initial_calls, 5)
            with self.assertRaisesRegex(GenerationError,'settings differ'):
                asyncio.run(select_reference_aware(None, count=3, seed=43,
                    modules=('simbad','mast'), timeout=30, targets=seeds,
                    max_probes=6, checkpoint_path=checkpoint, resume_checkpoint=True))
            self.assertEqual(len(calls),initial_calls)
            tasks, summary = asyncio.run(select_reference_aware(None, count=3, seed=42,
                    modules=('simbad','mast'), timeout=30, targets=seeds,
                    max_probes=6, checkpoint_path=checkpoint, resume_checkpoint=True))
            self.assertEqual(len(tasks),3)
            self.assertEqual(len(calls),6)
            self.assertEqual(summary['reference_aware_selection']['probes'],6)
            self.assertEqual(summary['reference_aware_selection']['fallback_slots'],1)
            self.assertEqual([t['module'] for t in tasks],['simbad','simbad','simbad'])
            damaged = json.loads(checkpoint.read_text())
            damaged['selected'][0]['target'] = 'fake'
            checkpoint.write_text(json.dumps(damaged))
            with self.assertRaisesRegex(GenerationError,'checksum'):
                asyncio.run(select_reference_aware(None, count=3, seed=42,
                    modules=('simbad','mast'), timeout=30, targets=seeds,
                    max_probes=6, checkpoint_path=checkpoint, resume_checkpoint=True))


    def test_coordinate_quota_rejects_simbad_only_pool(self):
        with self.assertRaisesRegex(GenerationError, 'coordinate-capable'):
            asyncio.run(select_reference_aware(None, count=3, seed=42,
                modules=('simbad',), timeout=10,
                targets=(SkyTarget('M31', 10, 20), SkyTarget('M33', 20, 30),
                         SkyTarget('M51', 30, 40)), min_coordinate_tasks=1))


    def test_named_workflow_resume_routes_progress_without_gpt(self):
        from benchmark.simple_workflows import create_queries, dataset_paths
        from unittest.mock import AsyncMock
        with TemporaryDirectory() as location:
            paths = dataset_paths(Path(location), 'sample10')
            paths['feasibility_progress'].parent.mkdir(parents=True)
            paths['feasibility_progress'].write_text('{"unfinished":true}')
            mocked = AsyncMock(side_effect=RuntimeError('stop-before-model'))
            with patch('benchmark.simple_workflows.generate_mixed', mocked):
                with self.assertRaisesRegex(RuntimeError,'stop-before-model'):
                    asyncio.run(create_queries(name='sample10', root=location,
                        count=10, resume=True, with_reference_answers=True,
                        require_ads=False))
            options = mocked.await_args.kwargs
            self.assertEqual(options['feasibility_progress'],paths['feasibility_progress'])
            self.assertTrue(options['resume_feasibility_progress'])
            self.assertFalse(options['reuse_feasibility_plan'])
            self.assertFalse(paths['generation_journal'].exists())


if __name__ == '__main__':
    unittest.main()
