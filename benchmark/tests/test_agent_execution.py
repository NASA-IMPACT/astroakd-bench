"""0.4.1 offline tests: no gold leakage, routed tools, recovery, evidence."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from benchmark.agent_runner import (AgentRunError, EchoAgent, ExternalAgent, OpenAIAgent,
                                    TracedMCPGateway, load_run_inputs, explicit_question_archive,
                                    run_agents, validate_tool_args)
from benchmark.tests.test_client import FakeSession
from benchmark.tests.test_reference_validation import make_test_dataset
from benchmark.validator import atomic_jsonl, load_jsonl
from benchmark.cli import build_parser


class CountingAgent:
    def __init__(self):
        self.questions = []
    async def run(self, question, gateway, max_turns):
        self.questions.append(question)
        output = await gateway.call_tool('astroquery_list_modules', {})
        if not output['ok']:
            raise AssertionError(output)
        return {'answer': 'A catalog query would be required; observed available modules.',
                'turns': 1, 'token_usage': {'total_tokens': 0}}


class FailingAgent:
    async def run(self, question, gateway, max_turns):
        await gateway.call_tool('delete_everything', {})
        raise RuntimeError('agent failure')


class FailingSession(FakeSession):
    async def call_tool(self, name, args, *, timeout=None):
        if name == 'astroquery_list_modules':
            raise RuntimeError('no archive')
        return await super().call_tool(name, args, timeout=timeout)


def fixture_paths(root, count=5):
    tasks_file, tasks = make_test_dataset(root, count=count)
    # Independent reference evidence is loaded for completeness but never
    # furnished to the agent. The fixture holds a unique trap string.
    from hashlib import sha256
    sha = sha256(tasks_file.read_bytes()).hexdigest()
    refs = []
    for task in tasks:
        refs.append({'task_id': task['id'], 'input_dataset_sha256': sha,
                     'module': task['module'], 'disposition': 'accepted_nonempty',
                     'reference_call': task['reference_call'],
                     'response': {'classified': 'GOLD_SECRET_DO_NOT_LEAK'}})
    ref_file = root / 'references.jsonl'
    atomic_jsonl(ref_file, refs)
    return tasks_file, ref_file, tasks


class GatewayTests(unittest.TestCase):
    def test_safe_discovery_and_query(self):
        self.assertEqual(validate_tool_args('astroquery_list_modules', {}), {})
        self.assertEqual(validate_tool_args('astroquery_execute', {
            'module_name': 'simbad', 'function_name':'query_object',
            'params':{'object_name':'M31'}})['module_name'], 'simbad')
        with self.assertRaises(AgentRunError):
            validate_tool_args('astroquery_execute', {
                'module_name':'simbad', 'function_name':'delete_tables', 'params': {}})

    def test_reject_unsafe_and_oversized_queries(self):
        cases = [
            ('delete_file', {}),
            ('astroquery_execute', {'module_name':'heasarc','function_name':'query_region',
                'params':{'position':'M31', 'radius':{'value':999, 'unit':'arcmin'}, 'catalog':'chanmaster'}}),
            ('astroquery_execute', {'module_name':'simbad','function_name':'query_object',
                'params':{'object_name':'M31', 'unexpected':'x'}}),
            ('astroquery_execute', {'module_name':'gaia','function_name':'query_object',
                'params':{'coordinate':{'ra':0,'dec':999}, 'radius':{'value':2,'unit':'arcmin'}}}),
            ('astroquery_list_functions', {'module_name':'outside'}),
            ('astroquery_execute', {'module_name':'vizier','function_name':'query_region',
                'params':{'coordinates':'M31', 'radius':{'value':2,'unit':'arcmin'}, 'catalog':'../../etc'}}),
        ]
        for tool, args in cases:
            with self.subTest(tool=tool, args=args), self.assertRaises(AgentRunError):
                validate_tool_args(tool, args)

    def test_gateway_records_accepted_and_rejected(self):
        async def go():
            from benchmark.client import AstroqueryMCPClient
            async with AstroqueryMCPClient(session_factory=FakeSession) as client:
                gate = TracedMCPGateway(client, max_calls=2, max_tool_bytes=1024)
                a = await gate.call_tool('astroquery_list_modules', {})
                b = await gate.call_tool('nonexistent', {})
                c = await gate.call_tool('astroquery_list_modules', {})
                self.assertTrue(a['ok'])
                self.assertFalse(b['ok'])
                self.assertFalse(c['ok'])
                self.assertEqual(len(gate.events), 3)
                self.assertEqual(gate.events[0]['status'], 'ok')
                self.assertEqual(gate.events[1]['status'], 'rejected')
                self.assertEqual(gate.events[2]['status'], 'rejected')
                self.assertIn('response_sha256', gate.events[0])
        asyncio.run(go())

    def test_tool_response_size_and_secret_redaction(self):
        class Faux:
            async def call(self, tool, args):
                return {'token':'would-leak', 'data':'x'*3000}
        gate = TracedMCPGateway(Faux(), max_tool_bytes=1024)
        result = asyncio.run(gate.call_tool('astroquery_list_modules', {}))
        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['truncated'])
        self.assertNotIn('would-leak', json.dumps(gate.events))

    def test_advertised_only_allowlisted_tools(self):
        gate = TracedMCPGateway(None, available=[{'name':'astroquery_execute'}, {'name':'danger_tool'}])
        self.assertEqual([t['name'] for t in gate.advertised_tools()], ['astroquery_execute'])


class AgentRunnerTests(unittest.TestCase):
    def test_real_accepted_dataset_load(self):
        from benchmark.tests.test_reference_validation import REAL_ACCEPTED
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks = REAL_ACCEPTED
            records, _ = load_jsonl(tasks)
            from hashlib import sha256
            h = sha256(tasks.read_bytes()).hexdigest()
            ref = root / 'refs.jsonl'
            atomic_jsonl(ref, [{'task_id':t['id'], 'input_dataset_sha256':h,
                                'disposition':'accepted_empty'} for t in records])
            loaded, observed, _ = load_run_inputs(tasks, ref, strict_sha=True)
            self.assertEqual(len(loaded), 50)
            self.assertEqual(h, observed)

    def test_reference_missing_duplicate_unaccepted_or_hash_mismatch(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, ref, _ = fixture_paths(root)
            originals, _ = load_jsonl(ref)
            variants = [originals[:-1], originals[:-1] + [originals[0]],
                        [dict(r, disposition='rejected_arguments') if i==0 else r for i,r in enumerate(originals)],
                        [dict(r, input_dataset_sha256='wrong') if i==0 else r for i,r in enumerate(originals)]]
            for bad in variants:
                atomic_jsonl(ref, bad, replace=True)
                with self.assertRaises(AgentRunError):
                    load_run_inputs(tasks, ref)

    def test_end_to_end_pilot_resume_no_gold_leak_and_checksums(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, refs, records = fixture_paths(root)
            out, report = root/'agent.jsonl', root/'report.json'
            agent = CountingAgent()
            kwargs = dict(agent_name='external', adapter='test:agent',
                          agent_factory=lambda: agent, session_factory=FakeSession,
                          limit=2)
            pilot = asyncio.run(run_agents(tasks, refs, out, report, **kwargs))
            self.assertEqual(pilot['status'], 'PARTIAL')
            self.assertEqual(pilot['processed'], 2)
            self.assertEqual(pilot['total_mcp_calls'], 2)
            self.assertFalse(out.exists())
            kwargs.pop('limit')
            whole = asyncio.run(run_agents(tasks, refs, out, report, resume=True, **kwargs))
            self.assertEqual(whole['status'], 'COMPLETE')
            # CountingAgent only lists modules and never executes an archive
            # query; do not label that as scientific query evidence.
            self.assertEqual(whole['quality_gate'], 'REVIEW')
            self.assertEqual(whole['query_evidence']['missing'], len(records))
            self.assertEqual(whole['processed'], len(records))
            self.assertEqual(whole['total_mcp_calls'], len(records))
            evidence, hashval = load_jsonl(out)
            self.assertEqual(hashval, whole['agent_runs_sha256'])
            self.assertNotIn('GOLD_SECRET_DO_NOT_LEAK', out.read_text())
            self.assertEqual([x['task_id'] for x in evidence], [x['id'] for x in records])
            self.assertEqual(len(agent.questions), len(records))
            self.assertTrue(all(len(x['trace']) == 1 for x in evidence))

    def test_manifest_mismatch_preserves_partial_state(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, refs, _ = fixture_paths(root)
            out, report = root/'agent.jsonl', root/'report.json'
            kwargs=dict(agent_name='echo', limit=1, session_factory=FakeSession)
            asyncio.run(run_agents(tasks, refs, out, report, **kwargs))
            manifest = out.with_name(out.name+'.manifest.json')
            prev = manifest.read_bytes()
            with self.assertRaisesRegex(AgentRunError, 'context mismatch'):
                asyncio.run(run_agents(tasks, refs, out, report,
                       agent_name='echo', resume=True, max_calls=3,
                       session_factory=FakeSession))
            self.assertEqual(manifest.read_bytes(), prev)

    def test_no_overwrite_and_early_failed_connection_preserves_files(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, refs, _ = fixture_paths(root)
            out, report = root/'agent.jsonl', root/'report.json'
            out.write_text('KEEP')
            with self.assertRaises(AgentRunError):
                asyncio.run(run_agents(tasks, refs, out, report, agent_name='echo', session_factory=FakeSession))
            with self.assertRaises(Exception):
                asyncio.run(run_agents(tasks, refs, out, report, agent_name='echo', replace=True,
                                      session_factory=lambda url: FakeSession(url, failures={'connect':True})))
            self.assertEqual(out.read_text(), 'KEEP')

    def test_per_task_error_journal_and_review_gate(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, refs, _ = fixture_paths(root)
            out, report = root/'agent.jsonl', root/'report.json'
            r = asyncio.run(run_agents(tasks, refs, out, report, agent_name='external',
                       adapter='mock:runner', agent_factory=FailingAgent,
                       session_factory=FakeSession))
            self.assertEqual(r['quality_gate'], 'REVIEW')
            self.assertEqual(r['dispositions']['agent_error'], 5)
            entries, _ = load_jsonl(out)
            self.assertEqual(entries[0]['trace'][0]['status'], 'rejected')
            self.assertEqual(entries[0]['error']['type'], 'RuntimeError')

    def test_echo_harness_not_scored_as_agent(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            tasks, refs, _ = fixture_paths(root)
            r = asyncio.run(run_agents(tasks, refs, root/'agent.jsonl',root/'report.json',
                         agent_name='echo', session_factory=FakeSession))
            self.assertEqual(r['quality_gate'], 'HARNESS_ONLY')
            self.assertEqual(r['total_mcp_calls'], 0)

    def test_cli_parses_runner(self):
        cmd=build_parser().parse_args(['run', '--agent','external','--adapter','yourpkg.agent:run',
                                        '--max-calls','7','--limit','3'])
        self.assertEqual(cmd.adapter,'yourpkg.agent:run')
        self.assertEqual(cmd.max_calls,7)


class OpenAIAdapterTests(unittest.TestCase):
    def test_fake_openai_tool_call_then_answer(self):
        def toolcall(name, args):
            return SimpleNamespace(id='call_1', function=SimpleNamespace(name=name, arguments=json.dumps(args)))
        m1 = SimpleNamespace(content=None, tool_calls=[toolcall('astroquery_execute', {
            'module_name': 'simbad', 'function_name': 'query_object',
            'params': {'object_name': 'M31'}})])
        m2 = SimpleNamespace(content='Found archive modules.', tool_calls=[])
        responses = [SimpleNamespace(choices=[SimpleNamespace(message=m)],
                       usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7,total_tokens=18))
                     for m in (m1,m2)]
        class Chat:
            async def create(self, **kwargs):
                return responses.pop(0)
        sdk=SimpleNamespace(chat=SimpleNamespace(completions=Chat()))
        ai=OpenAIAgent('test-model', sdk_client=sdk)
        async def go():
            from benchmark.client import AstroqueryMCPClient
            async with AstroqueryMCPClient(session_factory=FakeSession) as cli:
                tools=await cli.list_tools()
                gate=TracedMCPGateway(cli, available=tools)
                result=await ai.run('List modules', gate, 3)
                self.assertEqual(result['answer'],'Found archive modules.')
                self.assertEqual(result['turns'],2)
                self.assertEqual(result['token_usage']['total_tokens'],36)
                self.assertEqual(gate.calls,1)
        asyncio.run(go())

    def test_openai_requires_key_when_not_injected(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(AgentRunError, 'OPENAI_API_KEY'):
            OpenAIAgent()


if __name__=='__main__':
    unittest.main()


class ArchiveRecovery041Tests(unittest.TestCase):
    """Real pilot regression: HEASARC/Gaia misrouted to VizieR in 0.4.0."""

    def test_explicit_archive_is_derived_only_from_question(self):
        self.assertEqual(explicit_question_archive('Search the HEASARC xmmmaster catalog.'), 'heasarc')
        self.assertEqual(explicit_question_archive('Query Gaia sources around NGC 253.'), 'gaia')
        self.assertIsNone(explicit_question_archive('Search the region around M31.'))
        self.assertIsNone(explicit_question_archive('Combine Gaia and HEASARC data.'))
        self.assertEqual(explicit_question_archive('Using SIMBAD, query M31.'), 'simbad')

    def test_wrong_archive_is_rejected_with_actionable_guidance(self):
        async def go():
            from benchmark.client import AstroqueryMCPClient
            session = FakeSession('http://127.0.0.1:8000/mcp')
            async with AstroqueryMCPClient(session_factory=lambda _: session) as client:
                gate = TracedMCPGateway(client, question='Search the HEASARC xmmmaster catalog near M31.')
                bad = await gate.call_tool('astroquery_execute', {
                    'module_name':'vizier', 'function_name':'query_region', 'max_rows':20,
                    'params':{'coordinates':{'ra':10.6847,'dec':41.2688},
                              'radius':{'value':10,'unit':'arcmin'},'catalog':'II/246'}})
                self.assertFalse(bad['ok'])
                self.assertIn('HEASARC', bad['error']['message'])
                self.assertIn('position', bad['error']['message'])
                self.assertEqual(gate.successful_query_count, 0)
                self.assertFalse(session.calls)
                good = await gate.call_tool('astroquery_execute', {
                    'module_name':'heasarc', 'function_name':'query_region',
                    'params':{'position':{'ra':10.6847,'dec':41.2688},
                              'radius':{'value':10,'unit':'arcmin'},'catalog':'xmmmaster'}})
                self.assertTrue(good['ok'])
                self.assertEqual(gate.successful_query_count, 1)
                self.assertEqual([x['status'] for x in gate.events], ['rejected','ok'])
        asyncio.run(go())

    def test_gaia_uses_gaia_not_vizier_and_vizier_max_rows_recovery(self):
        async def go():
            from benchmark.client import AstroqueryMCPClient
            async with AstroqueryMCPClient(session_factory=FakeSession) as client:
                gate = TracedMCPGateway(client, question='Query Gaia sources within 3 arcmin of M31.')
                bad = await gate.call_tool('astroquery_execute', {
                    'module_name':'vizier', 'function_name':'query_region',
                    'params':{'coordinates':{'ra':10,'dec':41},
                              'radius':{'value':3,'unit':'arcmin'},'catalog':'II/246'}})
                self.assertFalse(bad['ok'])
                self.assertIn('gaia', bad['error']['message'])
                correct = await gate.call_tool('astroquery_execute', {
                    'module_name':'gaia', 'function_name':'query_object',
                    'params':{'coordinate':{'ra':10,'dec':41},
                              'radius':{'value':3,'unit':'arcmin'}}})
                self.assertTrue(correct['ok'])
                other = TracedMCPGateway(client, question='Query VizieR catalog II/246 near M31.')
                wrong = await other.call_tool('astroquery_execute', {
                    'module_name':'vizier', 'function_name':'query_region', 'max_rows':20,
                    'params':{'coordinates':{'ra':10,'dec':41},
                              'radius':{'value':2,'unit':'arcmin'},'catalog':'II/246'}})
                self.assertFalse(wrong['ok'])
                self.assertIn('remove', wrong['error']['message'])
                self.assertTrue((await other.call_tool('astroquery_execute', {
                    'module_name':'vizier', 'function_name':'query_region',
                    'params':{'coordinates':{'ra':10,'dec':41},
                              'radius':{'value':2,'unit':'arcmin'},'catalog':'II/246'}}))['ok'])
        asyncio.run(go())

    def test_openai_one_recovery_prompt_after_rejected_query(self):
        from benchmark.client import AstroqueryMCPClient
        def toolcall(key, name, args):
            return SimpleNamespace(id=key, function=SimpleNamespace(name=name,
                                      arguments=json.dumps(args)))
        wrong = toolcall('c1', 'astroquery_execute', {
            'module_name':'vizier', 'function_name':'query_region',
            'params':{'coordinates':{'ra':10.6847, 'dec':41.2688},
                      'radius':{'value':10,'unit':'arcmin'},'catalog':'II/246'}})
        corrected = toolcall('c2', 'astroquery_execute', {
            'module_name':'heasarc', 'function_name':'query_region',
            'params':{'position':{'ra':10.6847, 'dec':41.2688},
                      'radius':{'value':10,'unit':'arcmin'},'catalog':'xmmmaster'}})
        replies = [SimpleNamespace(content=None,tool_calls=[wrong]),
                   SimpleNamespace(content='I cannot perform this query.',tool_calls=[]),
                   SimpleNamespace(content=None,tool_calls=[corrected]),
                   SimpleNamespace(content='HEASARC returned the requested catalog.',tool_calls=[])]
        class Chat:
            def __init__(self):
                self.requests = []
            async def create(self, **kwargs):
                self.requests.append(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(message=replies.pop(0))], usage=None)
        chat = Chat()
        sdk=SimpleNamespace(chat=SimpleNamespace(completions=chat))
        async def go():
            async with AstroqueryMCPClient(session_factory=FakeSession) as client:
                gate=TracedMCPGateway(client, available=await client.list_tools(),
                                      question='Search HEASARC xmmmaster within 10 arcmin of M31.')
                result=await OpenAIAgent('fake', sdk_client=sdk).run('Search HEASARC xmmmaster within 10 arcmin of M31.',gate,5)
                self.assertIn('HEASARC returned', result['answer'])
                self.assertEqual(result['turns'], 4)
                self.assertEqual(gate.successful_query_count,1)
                self.assertEqual(len(gate.events),2)
                self.assertEqual(gate.events[0]['status'],'rejected')
                self.assertEqual(gate.events[1]['status'],'ok')
                self.assertNotIn('GOLD_SECRET_DO_NOT_LEAK', json.dumps(chat.requests))
        asyncio.run(go())

    def test_successful_transport_without_success_true_is_not_query_evidence(self):
        class NoSuccess:
            async def call(self, tool, args):
                return {'result': {'data':[]}}
        gate=TracedMCPGateway(NoSuccess())
        asyncio.run(gate.call_tool('astroquery_execute', {'module_name':'simbad',
            'function_name':'query_object', 'params':{'object_name':'M31'}}))
        self.assertEqual(gate.successful_query_count,0)
        self.assertFalse(gate.events[0]['response_success'])
