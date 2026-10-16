"""Offline release checks for live-candidate selection without paid GPT calls."""
import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from benchmark.reference_aware import (
    evaluate_feasibility, _resize, select_reference_aware,
    save_feasibility_plan, load_feasibility_plan,
)
from benchmark.generator import BoundMethod, GenerationError
from benchmark.seeds import SkyTarget
from benchmark.cli import build_parser


def candidate():
    return {'module': 'gaia', 'target': 'M31',
        'question': 'What parallaxes are listed within 3 arcmin of M31?',
        'answer_spec': {'expected_columns': ['parallax']},
        'constraints': {'radius': {'value': 3, 'unit': 'arcmin'}},
        'reference_call': {'tool': 'astroquery_execute', 'arguments': {
            'module_name': 'gaia', 'function_name': 'query_object',
            'params': {'coordinate': {'ra': 10.6, 'dec': 41.2, 'frame': 'icrs'},
                       'radius': {'value': 3, 'unit': 'arcmin'}}}}}


def response(rows=2, total=None, field='parallax'):
    return {'success': True, 'module': 'gaia', 'function': 'query_object',
        'result': {'data': [{field: 0.4 + i} for i in range(rows)], 'row_count': rows,
                   'total_rows': total if total is not None else rows,
                   'truncated': total is not None and total > rows}}


class ReferenceAwareTests(unittest.TestCase):
    def test_rejects_oversize_missing_empty_truncated_null(self):
        task = candidate()
        self.assertTrue(evaluate_feasibility(task, response())[0])
        self.assertEqual(evaluate_feasibility(task, response(total=100))[1], 'truncated_reference')
        self.assertEqual(evaluate_feasibility(task, response(rows=0))[1], 'accepted_empty')
        self.assertEqual(evaluate_feasibility(task, response(field='source_id'))[1], 'missing_expected_field')
        self.assertEqual(evaluate_feasibility(task, response(rows=21), max_rows=20)[1], 'too_many_rows')
        self.assertEqual(evaluate_feasibility(task, response(), max_bytes=80)[1], 'oversized_response')
        bad = response(); bad['result']['data'][0]['parallax'] = None
        self.assertEqual(evaluate_feasibility(task, bad)[1], 'null_answer_field')

    def test_authored_question_cannot_change_prechecked_radius(self):
        from benchmark.llm_generation import _guard_question
        task = _resize(candidate(), 0.2)
        task['id'] = 'TEST-1'
        task['provenance'] = {'reference_aware': {'status': 'PRECHECK_ACCEPTED'}}
        accepted = 'Which Gaia parallaxes occur within 0.2 arcmin of M31?'
        self.assertEqual(_guard_question(accepted, task, use_mcp=True), accepted)
        with self.assertRaisesRegex(GenerationError, 'prechecked radius'):
            _guard_question('Which Gaia parallaxes occur within 3 arcmin of M31?', task, use_mcp=True)
        with self.assertRaisesRegex(GenerationError, 'prechecked radius'):
            _guard_question('Which Gaia parallaxes occur near M31?', task, use_mcp=True)

    def test_resize_updates_call_constraints_and_wording(self):
        old = candidate(); updated = _resize(old, 0.1)
        self.assertEqual(updated['reference_call']['arguments']['params']['radius']['value'], 0.1)
        self.assertIn('within 0.1 arcmin', updated['question'])
        self.assertEqual(old['constraints']['radius']['value'], 3)

    def test_plans_frozen_and_tamper_protected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.json'; cfg = {'count': 1, 'seed': 42}
            save_feasibility_plan(path, configuration=cfg, tasks=[candidate()], summary={'accepted': 1})
            tasks, report = load_feasibility_plan(path, configuration=cfg)
            self.assertEqual(len(tasks), 1); self.assertEqual(report['accepted'], 1)
            with self.assertRaisesRegex(GenerationError, 'checksum or settings'):
                load_feasibility_plan(path, configuration={'count': 1, 'seed': 99})
            data = json.loads(path.read_text()); data['tasks'][0]['question'] = 'tampered'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(GenerationError, 'checksum or settings'):
                load_feasibility_plan(path, configuration=cfg)

    def test_offline_adaptive_selection_before_authoring(self):
        class Client:
            def __init__(self, *a, **k): self.calls = 0
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def call(self, tool, args):
                self.calls += 1
                radius = args['params']['radius']['value']
                field = 'source_id' if args['params']['coordinate']['ra'] == 10 else 'parallax'
                if radius == .1:  # force radius adaptation to .2
                    return {'success': True, 'module': 'gaia', 'function': 'query_object',
                        'result': {'data': [{'source_id': 42, 'parallax': 0.2, 'pmra': 1.2, 'pmdec': 2.1, 'phot_g_mean_mag': 14}], 'row_count': 1, 'total_rows': 500, 'truncated': True}}
                return {'success': True, 'module': 'gaia', 'function': 'query_object',
                        'result': {'data': [{'source_id': 42, 'parallax': 0.2, 'pmra': 1.2, 'pmdec': 2.1, 'phot_g_mean_mag': 14}], 'row_count': 1, 'total_rows': 1}}
        bound = BoundMethod('gaia', 'query_object', {'coordinate': 'coordinate', 'radius': 'radius'},
                ({'name': 'coordinate', 'required': True}, {'name': 'radius', 'required': False}))
        async def discover(client, modules): return {'gaia': bound}
        seeds = (SkyTarget('M31', 10, 20), SkyTarget('M33', 20, 30))
        with patch('benchmark.reference_aware.AstroqueryMCPClient', Client), patch(
                   'benchmark.reference_aware.discover_bindings', discover):
            tasks, report = asyncio.run(select_reference_aware(None, count=2, seed=42,
                modules=('gaia',), timeout=10, targets=seeds, max_probes=10))
        self.assertEqual(len(tasks), 2)
        self.assertEqual(report['reference_aware_selection']['probes'], 4)
        self.assertTrue(all(x['constraints']['radius']['value'] == .2 for x in tasks))
        self.assertEqual(len({x['target'] for x in tasks}), 2)

    def test_curated_pool_expanded_and_unique(self):
        from benchmark.reference_aware import REFERENCE_AWARE_TARGETS
        from benchmark.seeds import TARGETS
        self.assertGreater(len(REFERENCE_AWARE_TARGETS), 40)
        self.assertEqual(len({t.name.casefold() for t in REFERENCE_AWARE_TARGETS}), len(REFERENCE_AWARE_TARGETS))
        self.assertEqual(REFERENCE_AWARE_TARGETS[:len(TARGETS)], TARGETS)

    def test_cli_and_api_policy(self):
        cli = build_parser().parse_args(['create-queries','--reference-aware',
            '--with-reference-answers','--max-reference-rows','10',
            '--max-feasibility-probes','900'])
        self.assertTrue(cli.reference_aware)
        self.assertEqual(cli.max_reference_rows, 10)
        self.assertEqual(cli.max_feasibility_probes, 900)
        from benchmark.simple_workflows import create_queries
        with self.assertRaisesRegex(ValueError, 'requires --with-reference-answers'):
            asyncio.run(create_queries(reference_aware=True))
