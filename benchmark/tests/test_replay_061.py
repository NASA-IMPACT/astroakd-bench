"""0.6.1: semantic ICRS replay with unchanged frozen fixture integrity."""
from __future__ import annotations
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark.api import AstroAKDBench, SkyTarget
from benchmark.replay import (FixtureStore, ReplayClient, ReplayError,
                              semantic_key_for, key_for, static_catalog)
from benchmark.tests.test_generator import FixtureSession

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'benchmark/tests/fixtures/legacy/replay/reference_fixtures.json'
TASKS=ROOT/'benchmark/tests/fixtures/legacy/generated/synthetic_queries.jsonl'
REFERENCES=ROOT/'benchmark/tests/fixtures/legacy/validated/reference_answers.jsonl'


class SemanticReplay061Tests(unittest.TestCase):
    def test_original_fixture_fingerprint_and_frozen_datasets_unchanged(self):
        fixture=FixtureStore.load(FIXTURE)
        self.assertEqual(fixture.fingerprint,
            '31a8ae8644765e6a7a00995883415e32f4412fd9ce7669bf760515567b3522fe')
        self.assertEqual(hashlib.sha256(TASKS.read_bytes()).hexdigest(),
            'e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9')
        self.assertEqual(hashlib.sha256(REFERENCES.read_bytes()).hexdigest(),
            '1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87')
        self.assertEqual(len(fixture.entries), 50)

    def test_all_50_records_match_optional_implicit_frame_without_network(self):
        store=FixtureStore.load(FIXTURE)
        async def check():
            async with ReplayClient(store) as client:
                for entry in store.entries.values():
                    supplied=copy.deepcopy(entry['arguments'])
                    self.assertEqual(key_for(entry['tool'],supplied),entry['key'])
                    if supplied['module_name'] != 'simbad':
                        coord_key={'mast':'coordinates','heasarc':'position','gaia':'coordinate',
                                   'vizier':'coordinates'}[supplied['module_name']]
                        self.assertEqual(supplied['params'][coord_key].pop('frame'), 'icrs')
                        self.assertNotEqual(key_for(entry['tool'],supplied),entry['key'])
                    payload=await client.call(entry['tool'],supplied)
                    self.assertEqual(payload,entry['payload'])
        with patch('benchmark.agent_runner.AstroqueryMCPClient',side_effect=AssertionError('network created')):
            asyncio.run(check())

    def test_five_agent_call_shapes_from_actual_060_pilot(self):
        calls=[t['reference_call'] for t in (json.loads(line) for line in TASKS.read_text().splitlines())][:5]
        store=FixtureStore.load(FIXTURE)
        self.assertEqual([x['arguments']['module_name'] for x in calls],
                         ['simbad','mast','heasarc','gaia','vizier'])
        for call in calls:
            args=copy.deepcopy(call['arguments'])
            k={'mast':'coordinates','heasarc':'position','gaia':'coordinate','vizier':'coordinates'}.get(args['module_name'])
            if k:
                args['params'][k].pop('frame')
            self.assertEqual(store.lookup('astroquery_execute',args).get('success'), True)

    def test_wrong_coordinates_radius_and_catalog_never_match(self):
        store=FixtureStore.load(FIXTURE)
        for entry in store.entries.values():
            module=entry['arguments']['module_name']
            if module=='simbad':
                continue
            args=copy.deepcopy(entry['arguments'])
            k={'mast':'coordinates','heasarc':'position','gaia':'coordinate','vizier':'coordinates'}[module]
            args['params'][k].pop('frame')
            altered=copy.deepcopy(args); altered['params'][k]['ra']+=.00001
            with self.assertRaisesRegex(ReplayError,'OFFLINE_REPLAY_MISS'):
                store.lookup('astroquery_execute',altered)
            altered=copy.deepcopy(args); altered['params']['radius']['value']+=.00001
            with self.assertRaisesRegex(Exception,'OFFLINE_REPLAY_MISS|radius'):
                store.lookup('astroquery_execute',altered)
            if 'catalog' in args['params']:
                altered=copy.deepcopy(args)
                altered['params']['catalog']='chanmaster' if module=='heasarc' else 'I/345'
                if altered['params']['catalog']==args['params']['catalog']:
                    continue
                with self.assertRaisesRegex(Exception,'OFFLINE_REPLAY_MISS|catalog'):
                    store.lookup('astroquery_execute',altered)

    def test_other_fields_are_not_defaulted(self):
        store=FixtureStore.load(FIXTURE)
        mast=next(x for x in store.entries.values() if x['arguments'].get('module_name')=='mast')
        args=copy.deepcopy(mast['arguments'])
        args['max_rows']=20
        with self.assertRaisesRegex(ReplayError,'OFFLINE_REPLAY_MISS'):
            store.lookup('astroquery_execute',args)
        args=copy.deepcopy(mast['arguments']);args['params']['coordinates']['frame']='galactic'
        with self.assertRaisesRegex(ValueError,'ICRS'):
            store.lookup('astroquery_execute',args)

    def test_ambiguous_semantic_fixture_aliases_fail_closed(self):
        existing=next(x for x in FixtureStore.load(FIXTURE).entries.values()
                      if x['arguments']['module_name']=='gaia')
        store=FixtureStore(static_catalog())
        store.add_entry(copy.deepcopy(existing))
        args=copy.deepcopy(existing['arguments']);args['params']['coordinate'].pop('frame')
        with self.assertRaisesRegex(ReplayError,'Ambiguous replay fixture'):
            store.record('astroquery_execute',args,existing['payload'])

    def test_public_api_fixture_import_and_generation(self):
        with TemporaryDirectory() as d:
            api=AstroAKDBench(d)
            sessions=[]
            def factory(url):
                session=FixtureSession(url)
                sessions.append(session)
                return session
            result=asyncio.run(api.generate_queries(backend='template', count=10,seed=7,
                modules=('simbad','mast'),report='datasets/generated/report.json',
                session_factory=factory))
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(len(api.load_records('datasets/generated/synthetic_queries.jsonl')),10)
            self.assertTrue(sessions[0].closed)
            self.assertTrue((Path(d)/'datasets/generated/report.json').is_file())
            with self.assertRaisesRegex(ValueError,'already exists'):
                asyncio.run(api.generate_queries(backend='template', count=10,seed=7,modules=('simbad','mast'),
                                                 session_factory=factory))

    def test_public_api_custom_targets_are_reproducible_and_separate(self):
        targets=(SkyTarget('Custom One', 10.0, -20.0),
                 SkyTarget('Custom Two', 20.0, 35.0))
        hashes=[]
        for _ in range(2):
            with TemporaryDirectory() as d:
                bench=AstroAKDBench(d)
                result=asyncio.run(bench.generate_queries(backend='template', count=4,seed=2026,
                    modules=('mast','heasarc'),targets=targets,
                    session_factory=FixtureSession))
                hashes.append(result['dataset_sha256'])
                records=bench.load_records('datasets/generated/synthetic_queries.jsonl')
                self.assertEqual(len(records),4)
                self.assertTrue(all(t['provenance'].get('custom_seed_catalog_sha256') for t in records))
                self.assertTrue(all(t['target'] in {'Custom One','Custom Two'} for t in records))
        self.assertEqual(hashes[0],hashes[1])
        with TemporaryDirectory() as d:
            b=AstroAKDBench(d)
            for invalid in ((SkyTarget('x', float('nan'),1),),
                            (SkyTarget('dup',10,1),SkyTarget('dup',20,2))):
                with self.assertRaisesRegex(ValueError,'coordinates|Duplicate'):
                    asyncio.run(b.generate_queries(backend='template', count=2,modules=('mast',),targets=invalid,
                                                  session_factory=FixtureSession))
            self.assertFalse(b.tasks_path.exists())

    def test_public_api_offline_echo_run_and_scoring(self):
        with TemporaryDirectory() as d:
            b=AstroAKDBench(d)
            output=Path(d)/'runs.jsonl';report=Path(d)/'report.json'
            result=asyncio.run(b.run_agent(agent='echo',mcp_mode='replay',
                fixtures=FIXTURE,tasks=TASKS,references=REFERENCES,
                output=output,report=report,limit=1,strict_accepted_020=True))
            self.assertEqual(result['quality_gate'],'HARNESS_ONLY')
            self.assertEqual(result['processed'],1)
        with TemporaryDirectory() as d:
            b=AstroAKDBench(d)
            original=ROOT/'benchmark/tests/fixtures/legacy/agent/openai_041_runs.jsonl.progress.jsonl'
            summary=b.evaluate_agent(runs=original,tasks=TASKS,references=REFERENCES,
                output='scores.jsonl',report='report.json',csv='scores.csv',
                pretty_output='scores_pretty.json',strict_accepted_020=True)
            self.assertEqual(summary['status'],'PARTIAL')
            self.assertEqual(len(b.load_records('scores.jsonl')),5)
            self.assertTrue((Path(d)/'scores_pretty.json').exists())

    def test_public_api_offline_scoring_and_fixture_construction(self):
        with TemporaryDirectory() as d:
            root=Path(d);api=AstroAKDBench(root)
            f=api.build_fixtures(tasks=TASKS,references=REFERENCES,
                                 strict_accepted_020=True)
            self.assertEqual(f['records'],50)
            self.assertEqual(api.load_fixtures().fingerprint,f['fixture_fingerprint'])
            with self.assertRaisesRegex(ReplayError,'already exists'):
                api.build_fixtures(tasks=TASKS,references=REFERENCES)


if __name__=='__main__':
    unittest.main()
