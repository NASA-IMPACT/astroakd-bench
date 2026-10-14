"""ADS routing over the external Astroquery MCP connection; no real credentials."""
import asyncio
import json
import unittest
from types import SimpleNamespace as O
from unittest.mock import patch
from benchmark.literature import research_literature, _ads_server_enabled
from benchmark.cli import build_parser
from benchmark.api import AstroAKDBench
from benchmark.generator import GenerationError


class FakeMCP:
    def __init__(self, url, *, ads=True, raise_ads=False):
        self.ads=ads
        self.raise_ads=raise_ads
        self.calls=[]
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def ping(self): pass
    async def list_tools(self):
        return [O(name='ads_query_compact',description='',inputSchema={})]
    async def call_tool(self, name, args, timeout=None):
        self.calls.append((name,args))
        if name=='astroquery_check_auth':
            data={'status':{'ads':{'configured':self.ads,'env_var':'API_DEV_KEY'}},
                  'configured':{'ads':self.ads}, 'diagnostics':{'API_DEV_KEY':'set' if self.ads else 'not set'}}
        elif name=='ads_query_compact':
            if self.raise_ads: raise RuntimeError('ADS token not valid: FAKE_SECRET')
            data={'success':True,'results':[{'bibcode':'2023ApJ...111..222A',
                 'title':'A paper','year':2023,'abstract':'Scientific abstract'}]}
        else: raise AssertionError(name)
        return O(data=data, is_error=False)


class FakeResponses:
    def __init__(self, *, search=True): self.calls=[];self.search=search
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return O(output=[O(type='web_search_call',action=O(sources=[O(url='https://example.org/paper')]))] if self.search else [],
                 output_text=json.dumps({'questions':[{'id':'research','question':'Which paper describes the source?'}]}))

class LiteratureTests(unittest.TestCase):
    def test_documented_auth_shape(self):
        self.assertTrue(_ads_server_enabled({'configured':{'ads':True}}))
        self.assertFalse(_ads_server_enabled({'configured':{'ads':False},'status':{'ads':{'configured':True}}}))
        self.assertFalse(_ads_server_enabled({'status':{'ads':{'configured':False}}}))

    def test_ads_mcp_path_no_openai_and_no_secret(self):
        server=FakeMCP('http://local',ads=True)
        result=asyncio.run(research_literature('NGC 3783 outflow',session_factory=lambda u:server,
            openai_client_factory=lambda: (_ for _ in ()).throw(AssertionError('OpenAI should not run'))))
        self.assertEqual(result['research_provider'],'astroquery_mcp_ads')
        self.assertEqual([n for n,_ in server.calls], ['astroquery_check_auth','ads_query_compact'])
        self.assertIn('2023ApJ',result['research_sources'][0]);self.assertNotIn('API_DEV_KEY',str(result))
        self.assertFalse(result['scientific_truth_verified'])

    def test_missing_ads_key_falls_back_even_with_mcp(self):
        client=FakeResponses(); server=FakeMCP('http://local',ads=False)
        res=asyncio.run(research_literature('Nearest TDE source papers',session_factory=lambda u:server,
                     openai_client_factory=lambda:O(responses=client)))
        self.assertEqual(res['research_provider'],'openai_web_search')
        self.assertEqual(res['fallback_reason'],'ads_not_configured')
        self.assertEqual(res['web_search_calls'],1)
        self.assertEqual(res['research_sources'],['https://example.org/paper'])
        self.assertEqual(len(server.calls),1)
        self.assertIn('web_search',str(client.calls[0]['tools']))

    def test_ads_error_redacted_then_fallback(self):
        client=FakeResponses(); server=FakeMCP('http://local',ads=True,raise_ads=True)
        res=asyncio.run(research_literature('Chandra papers',session_factory=lambda u:server,
                              openai_client_factory=lambda:O(responses=client)))
        self.assertEqual(res['fallback_reason'],'ads_search_unavailable')
        self.assertNotIn('FAKE_SECRET',str(res))

    def test_no_mcp_skips_client_and_uses_web(self):
        client=FakeResponses()
        r=asyncio.run(research_literature('FAST telescope bibliography',use_mcp=False,
                     session_factory=lambda u: (_ for _ in ()).throw(AssertionError('MCP connected')),
                     openai_client_factory=lambda:O(responses=client)))
        self.assertEqual(r['fallback_reason'],'mcp_disabled')
        self.assertFalse(r['ads_authenticated'])

    def test_mcp_connection_failure_fallback_and_web_search_requirement(self):
        def offline(url): raise OSError('unreachable')
        res=asyncio.run(research_literature('HST COS quasar outflow',session_factory=offline,
                              openai_client_factory=lambda:O(responses=FakeResponses())))
        self.assertEqual(res['fallback_reason'],'mcp_auth_check_unavailable')
        with self.assertRaisesRegex(GenerationError,'web_search call'):
            asyncio.run(research_literature('HST COS quasar outflow',use_mcp=False,
                 openai_client_factory=lambda:O(responses=FakeResponses(search=False))))

    def test_cli_and_public_api(self):
        opts=build_parser().parse_args(['literature-search','--query','nearest Lyman break analog'])
        self.assertEqual(opts.max_results,5)
        self.assertTrue(opts.mcp)
        r=asyncio.run(AstroAKDBench(root='.').research_literature('literature survey',
                     session_factory=lambda url:FakeMCP(url,ads=True)))
        self.assertEqual(r['mcp_tool'],'ads_query_compact')

if __name__=='__main__': unittest.main()
