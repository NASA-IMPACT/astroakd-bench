"""0.6.7.3: ASTROAKD-namespaced endpoint and bearer-token configuration."""
from __future__ import annotations
import asyncio
from contextlib import contextmanager
import io
import json
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from benchmark import DEFAULT_MCP_URL
from benchmark.cli import build_parser, main
from benchmark.client import AstroqueryMCPClient, _make_fastmcp_client
from benchmark.mcp_config import resolve_mcp_url, resolve_mcp_token, mcp_token_scope
from benchmark.tests.test_client import FakeSession
from benchmark.diagnostics import doctor
from benchmark.errors import MCPConnectionError


class MCPConfig0673Tests(unittest.TestCase):
    def test_endpoint_priority_and_no_legacy_env(self):
        with patch.dict(os.environ, {'ASTROAKD_MCP_URL':'https://new.example/mcp',
                                    'MCP_URL':'https://legacy.example/mcp'}):
            self.assertEqual(resolve_mcp_url(), 'https://new.example/mcp')
            self.assertEqual(resolve_mcp_url('https://explicit.example/mcp'), 'https://explicit.example/mcp')
            self.assertEqual(resolve_mcp_url(''), 'https://new.example/mcp')
        with patch.dict(os.environ, {'ASTROAKD_MCP_URL':'', 'MCP_URL':'https://legacy.example/mcp'}):
            self.assertEqual(resolve_mcp_url(), DEFAULT_MCP_URL)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_mcp_url(), DEFAULT_MCP_URL)
        for value in ('not-a-url', 'ftp://server/mcp', 'https://username:secret@server/mcp'):
            with self.subTest(url=value), self.assertRaises(ValueError):
                resolve_mcp_url(value)

    def test_token_priority_empty_and_no_legacy_env(self):
        with patch.dict(os.environ, {'ASTROAKD_MCP_TOKEN':'env-secret', 'MCP_TOKEN':'legacy-secret'}):
            self.assertEqual(resolve_mcp_token(), 'env-secret')
            self.assertEqual(resolve_mcp_token('explicit-secret'), 'explicit-secret')
            with mcp_token_scope('scoped-secret'):
                self.assertEqual(resolve_mcp_token(), 'scoped-secret')
            with mcp_token_scope(''):
                self.assertIsNone(resolve_mcp_token())
            self.assertEqual(resolve_mcp_token(), 'env-secret')
        with patch.dict(os.environ, {'ASTROAKD_MCP_TOKEN':'', 'MCP_TOKEN':'legacy-secret'}):
            self.assertIsNone(resolve_mcp_token())
        with patch.dict(os.environ, {'MCP_TOKEN':'legacy-secret'}, clear=True):
            self.assertIsNone(resolve_mcp_token())

    def test_cli_aliases_and_namespaced_help(self):
        parser = build_parser()
        args = parser.parse_args(['doctor','--mcp-server','https://custom.example/mcp',
                                  '--mcp-server-token','hidden'])
        self.assertEqual(args.mcp_url,'https://custom.example/mcp')
        self.assertEqual(args.mcp_token,'hidden')
        self.assertIn('ASTROAKD_MCP_URL',parser.parse_args(['doctor']).__dict__.__repr__() if False else
                      next(a.help for a in parser._subparsers._group_actions[0].choices['doctor']._actions if a.dest=='mcp_url'))

    def test_fake_client_receives_env_token_and_visible_url_without_leak(self):
        with patch.dict(os.environ,{'ASTROAKD_MCP_URL':'https://nonexistent.example/mcp',
                                    'ASTROAKD_MCP_TOKEN':'private-123'},clear=True):
            session = FakeSession('https://nonexistent.example/mcp',failures={'connect':True})
            async def go():
                async with AstroqueryMCPClient(session_factory=lambda _: session):
                    pass
            with self.assertRaises(MCPConnectionError) as error:
                asyncio.run(go())
            self.assertIn('Cannot connect to MCP server at https://nonexistent.example/mcp',str(error.exception))
            self.assertNotIn('private-123',str(error.exception))

    def test_error_scrubs_secret_from_remote_text(self):
        class LeakSession(FakeSession):
            async def ping(self):
                raise RuntimeError('bad bearer value: private-123')
        with patch.dict(os.environ,{'ASTROAKD_MCP_TOKEN':'private-123'}):
            r = asyncio.run(doctor('https://unavailable.example/mcp',session_factory=lambda url:LeakSession(url)))
            self.assertEqual(r['status'],'FAIL')
            self.assertIn('https://unavailable.example/mcp',r['error']['message'])
            self.assertIn('[REDACTED]',r['error']['message'])
            self.assertNotIn('private-123',str(r))

    def test_fastmcp_constructs_explicit_bearer_auth(self):
        root=ModuleType('fastmcp')
        client_pkg=ModuleType('fastmcp.client')
        auth_pkg=ModuleType('fastmcp.client.auth')
        class BearerAuth:
            def __init__(self, token): self.token=token
        class Client:
            def __init__(self, url, auth=None): self.url=url;self.auth=auth
        root.Client=Client
        auth_pkg.BearerAuth=BearerAuth
        with patch.dict(sys.modules,{'fastmcp':root,'fastmcp.client':client_pkg,'fastmcp.client.auth':auth_pkg}):
            secured=_make_fastmcp_client('https://cloud.example/mcp','secret-test')
            local=_make_fastmcp_client('http://127.0.0.1:8000/mcp')
        self.assertEqual(secured.auth.token,'secret-test')
        self.assertIsNone(local.auth)

    def test_cli_defaults_to_env_server_and_reports_disconnection(self):
        from benchmark import client as client_module
        class Disconnected(FakeSession):
            async def __aenter__(self): raise ConnectionError('unavailable')
        with patch.dict(os.environ,{'ASTROAKD_MCP_URL':'https://offline.example/mcp'},clear=True), \
             patch.object(client_module,'_make_fastmcp_client',side_effect=lambda url,token=None:Disconnected(url)), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            rc=main(['tools','--json-format','pretty'])
        self.assertEqual(rc,1)
        report=json.loads(output.getvalue())
        self.assertEqual(report['endpoint'],'https://offline.example/mcp')
        self.assertIn('Cannot connect to MCP server at https://offline.example/mcp',report['error']['message'])

if __name__=='__main__': unittest.main()

class ThreeArmOfflinePreflight0673(unittest.TestCase):
    def test_real_runner_refuses_offline_server_without_poisoning_journal(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from benchmark.three_arm import run_three_arm
        from benchmark.validator import atomic_jsonl
        from benchmark import client as client_module
        from benchmark.tests.test_gold_three_arm_066 import FakeSDK
        async def go():
            with TemporaryDirectory() as d:
                root=Path(d); tasks=root/'tasks.jsonl'; instruction=root/'instructions.md'; output=root/'results.jsonl'; report=root/'report.json'
                atomic_jsonl(tasks,[{'id':'T1','task_type':'archive_driven','question':'What is SIMBAD identifier for M31?',
                                    'module':'simbad','target':'M31','answer_spec':{'expected_columns':['main_id']}}])
                instruction.write_text('# AstroAKD agent instructions\n' + ('Please use astronomy tools. '*20))
                class Offline(FakeSession):
                    async def __aenter__(self): raise ConnectionError('refused')
                with patch.object(client_module,'_make_fastmcp_client',side_effect=lambda u,t=None:Offline(u)):
                    with self.assertRaises(MCPConnectionError) as e:
                        await run_three_arm(tasks,instruction,output,report,url='https://offline.example/mcp',sdk=FakeSDK())
                self.assertIn('https://offline.example/mcp',str(e.exception))
                self.assertFalse(output.with_name(output.name+'.progress.jsonl').exists())
                self.assertFalse(output.with_name(output.name+'.manifest.json').exists())
        asyncio.run(go())

class ExplicitCLITokenRedaction0673(unittest.TestCase):
    def test_explicit_cli_token_cannot_leak_even_after_token_scope_exit(self):
        from benchmark import client as client_module
        class LeakingSession(FakeSession):
            async def ping(self): raise ConnectionError('Authorization: Bearer cli-secret-leak')
        with patch.dict(os.environ,{'ASTROAKD_MCP_TOKEN':''},clear=True), \
             patch.object(client_module,'_make_fastmcp_client',side_effect=lambda u,t=None:LeakingSession(u)), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            rc=main(['tools','--mcp-url','https://protected.example/mcp',
                     '--mcp-token','cli-secret-leak'])
        self.assertEqual(rc,1)
        data=json.loads(output.getvalue())
        self.assertEqual(data['endpoint'],'https://protected.example/mcp')
        self.assertNotIn('cli-secret-leak',output.getvalue())
        self.assertIn('[REDACTED]',data['error']['message'])
