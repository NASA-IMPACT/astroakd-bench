"""0.6.0: immutable fixture capture, integrity, network isolation and agent replay."""
from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark.cli import build_parser
from benchmark.agent_runner import run_agents
from benchmark.client import AstroqueryMCPClient
from benchmark.replay import (FixtureStore, ReplayClient, RecordClient, ReplayError,
                              build_reference_fixtures, static_catalog)
from benchmark.validator import load_jsonl
from benchmark.tests.test_client import FakeSession

ROOT=Path(__file__).resolve().parents[2]
TASKS=ROOT/'benchmark/tests/fixtures/legacy/generated/synthetic_queries.jsonl'
REFERENCES=ROOT/'benchmark/tests/fixtures/legacy/validated/reference_answers.jsonl'

class SingleSimbadAgent:
    async def run(self, question, gateway, max_turns):
        match=re.search(r'NGC\s+\d+',question)
        if match is None:
            raise RuntimeError('Cannot find test object')
        outcome=await gateway.call_tool('astroquery_execute',{
            'module_name':'simbad','function_name':'query_object',
            'params':{'object_name':match.group(0)}})
        return {'answer':'Found the requested object.' if outcome['ok'] else 'Archive unavailable.',
                'turns':1,'token_usage':{}}

class Replay060Tests(unittest.TestCase):
    def test_cli_modes_and_defaults(self):
        parser=build_parser()
        self.assertEqual(parser.parse_args(['run']).mcp_mode,'live')
        self.assertEqual(parser.parse_args(['run','--mcp-mode','replay',
                                            '--fixtures','datasets/replay/ref.json']).mcp_mode,'replay')
        self.assertEqual(parser.parse_args(['build-fixtures']).output,
                         Path('datasets/replay/reference_fixtures.json'))

    def test_build_50_and_preserve_frozen_hashes(self):
        start=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (TASKS,REFERENCES)]
        with TemporaryDirectory() as d:
            dst=Path(d)/'fixture.json'
            report=build_reference_fixtures(TASKS,REFERENCES,dst,strict_accepted_020=True)
            self.assertEqual((report['records'],report['network_calls'],report['status']),(50,0,'PASS'))
            store=FixtureStore.load(dst)
            self.assertEqual(len(store.entries),50)
            self.assertEqual(store.fingerprint,report['fixture_fingerprint'])
            with self.assertRaises(ReplayError):
                build_reference_fixtures(TASKS,REFERENCES,dst)
            self.assertEqual(store.catalog,static_catalog())
        self.assertEqual(start,[hashlib.sha256(p.read_bytes()).hexdigest() for p in (TASKS,REFERENCES)])

    def test_reject_tampering_and_unknown_calls(self):
        with TemporaryDirectory() as d:
            dst=Path(d)/'f.json'
            build_reference_fixtures(TASKS,REFERENCES,dst)
            store=FixtureStore.load(dst)
            with self.assertRaisesRegex(ReplayError,'OFFLINE_REPLAY_MISS'):
                store.lookup('astroquery_execute',{'module_name':'simbad',
                                                   'function_name':'query_object',
                                                   'params':{'object_name':'AN_UNRECORDED_NAME'}})
            payload=json.loads(dst.read_text());payload['entries'][0]['payload']['success']=False
            dst.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ReplayError,'SHA-256'):
                FixtureStore.load(dst)

    def test_cli_fixture_is_not_overwritten_by_summary_report(self):
        import subprocess,sys
        with TemporaryDirectory() as d:
            dst=Path(d)/'fixtures.json'
            command=[sys.executable,'-m','benchmark','build-fixtures',
                     '--tasks',str(TASKS),'--references',str(REFERENCES),
                     '--strict-accepted-020','--output',str(dst),'--json-format','pretty']
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(result.stdout.startswith('{\n'))
            self.assertEqual(len(FixtureStore.load(dst).entries),50)
            self.assertNotIn('milestone',json.loads(dst.read_text()))

    def test_fixture_candidate_hash_mismatch_blocks_runner(self):
        with TemporaryDirectory() as d:
            root=Path(d);fixture=root/'f.json'
            store=FixtureStore(static_catalog(),dataset_sha256='0'*64)
            store.publish(fixture)
            with self.assertRaisesRegex(Exception,'dataset SHA-256 mismatch'):
                asyncio.run(run_agents(TASKS,REFERENCES,root/'a.jsonl',root/'r.json',
                    agent_name='echo',mcp_mode='replay',fixtures=fixture,limit=1))
            self.assertFalse((root/'a.jsonl.progress.jsonl').exists())

    def test_fail_closed_on_unsafe_calls(self):
        store=FixtureStore(static_catalog())
        with self.assertRaises(ReplayError):
            store.record('delete_everything',{}, {'success':True})
        with self.assertRaises(Exception):
            store.record('astroquery_execute',{'module_name':'heasarc',
                'function_name':'query_region','params':{'catalog':'xmmmaster',
                'position':'M31','radius':{'value':500,'unit':'arcmin'}}},{'success':True})

    def test_record_and_replay_discovery_without_network(self):
        async def run(tmp):
            file=tmp/'recording.json'
            live=AstroqueryMCPClient(session_factory=FakeSession)
            async with RecordClient(live,file,dataset_hash='test') as client:
                original=await client.call('astroquery_list_modules',{})
                self.assertTrue(file.exists())
            offline=ReplayClient(FixtureStore.load(file))
            async with offline as client:
                self.assertEqual(original,await client.call('astroquery_list_modules',{}))
            self.assertEqual(FixtureStore.load(file).source,'live_mcp_recording')
        with TemporaryDirectory() as d:
            asyncio.run(run(Path(d)))

    def test_run_offline_with_real_task_and_no_network(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            path=root/'fixtures.json'
            build_reference_fixtures(TASKS,REFERENCES,path,strict_accepted_020=True)
            output=root/'agent.jsonl';report=root/'report.json'
            # Prohibit any accidental construction of a live session.
            with patch('benchmark.agent_runner.AstroqueryMCPClient',side_effect=AssertionError('network client created')):
                result=asyncio.run(run_agents(TASKS,REFERENCES,output,report,
                    agent_name='external',adapter='example:run',
                    agent_factory=lambda:SingleSimbadAgent(),mcp_mode='replay',fixtures=path,
                    limit=1,strict_accepted_020=True))
            self.assertEqual((result['processed'],result['successful_execute_calls']), (1,1))
            self.assertEqual(result['mcp_mode'],'replay')
            self.assertEqual(result['endpoint'],'offline://fixture')
            trace=json.loads((root/'agent.jsonl.progress.jsonl').read_text())['trace']
            self.assertEqual(trace[0]['status'],'ok')
            self.assertTrue(trace[0]['response_success'])
            self.assertEqual(json.loads(report.read_text())['fixture_fingerprint'],FixtureStore.load(path).fingerprint)

    def test_replay_missing_call_produces_recorded_error_without_network(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            # Empty fixture catalog is fine but there are no execute responses.
            store=FixtureStore(static_catalog())
            file=root/'f.json';store.publish(file)
            result=asyncio.run(run_agents(TASKS,REFERENCES,root/'a.jsonl',root/'r.json',
                agent_name='external',adapter='test:agent',agent_factory=lambda:SingleSimbadAgent(),
                mcp_mode='replay',fixtures=file,limit=1))
            self.assertEqual(result['successful_execute_calls'],0)
            self.assertEqual(result['failed_mcp_calls'],1)
            event=json.loads((root/'a.jsonl.progress.jsonl').read_text())['trace'][0]
            self.assertIn('OFFLINE_REPLAY_MISS',event['error'])
            self.assertEqual(result['query_evidence'],{'missing':1})

    def test_replay_resume_rejects_changed_fixtures(self):
        with TemporaryDirectory() as d:
            root=Path(d);fixture=root/'f.json'
            build_reference_fixtures(TASKS,REFERENCES,fixture)
            kw=dict(agent_name='external',adapter='test:agent',agent_factory=lambda:SingleSimbadAgent(),
                    mcp_mode='replay',fixtures=fixture,limit=1)
            asyncio.run(run_agents(TASKS,REFERENCES,root/'a.jsonl',root/'r.json',**kw))
            store=FixtureStore.load(fixture)
            store.record('astroquery_list_modules',{}, {'different':'response'})
            store.publish(fixture,replace=True)
            with self.assertRaisesRegex(Exception,'context mismatch'):
                asyncio.run(run_agents(TASKS,REFERENCES,root/'a.jsonl',root/'r.json',resume=True,**kw))

if __name__=='__main__':unittest.main()
