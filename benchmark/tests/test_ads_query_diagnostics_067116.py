"""No-network regression for exact-query ADS diagnostics and privacy."""
import asyncio
from types import SimpleNamespace as O

import pytest

from benchmark.cli import build_parser, _execute
from benchmark.literature import (_ads_error_class, _ads_query_candidates,
    _search_ads, check_literature_auth, research_literature)
from benchmark.errors import MCPToolError, MCPTransportError
from benchmark.generator import GenerationError
from benchmark.tests.test_literature_0643 import FakeMCP


@pytest.mark.parametrize('message,expected', [
    ('ADS query failed: 400 Client Error: FAKE_SECRET', 'upstream_http_400_bad_query'),
    ('ADS query failed: 401 Unauthorized: FAKE_SECRET', 'upstream_http_401_authentication'),
    ('ADS query failed: 403 Client Error', 'upstream_http_403_forbidden'),
    ('ADS query failed: 429 Too Many Requests', 'upstream_http_429_rate_limit'),
    ('ADS query failed: SSLError certificate', 'upstream_tls_error'),
    ('ADS query failed: something else', 'mcp_ads_tool_error_unclassified'),
])
def test_classifies_ads_error_without_exposing_raw_message(message, expected):
    exc=MCPToolError('ads_query_compact', message,
        code='SERVICE_ERROR', payload={'details':{'error':message+' FAKE_SECRET'}})
    assert _ads_error_class(exc)==expected
    assert 'FAKE_SECRET' not in _ads_error_class(exc)


def test_transport_error_is_distinct():
    assert _ads_error_class(MCPTransportError('connection failed'))=='mcp_transport_error'


def test_query_diagnostic_works_for_specific_query():
    fake=FakeMCP('http://server',ads=True)
    r=asyncio.run(check_literature_auth(query='PG 1211+143',
        session_factory=lambda _:fake))
    assert r['status']=='PASS' and r['query_probe'] and r['ads_probe_success']
    assert any(x['query_string']=='PG 1211+143' for n,x in fake.calls if n=='ads_query_compact')
    assert 'FAKE_SECRET' not in str(r)


def test_query_diagnostic_fails_safely_and_never_invokes_web_search():
    fake=FakeMCP('http://server',ads=True,raise_ads=True)
    r=asyncio.run(check_literature_auth(query='PG 1211+143',
        session_factory=lambda _:fake))
    assert r['status']=='FAIL'
    assert r['reason']=='ads_search_unavailable'
    assert r['query_probe'] is True
    assert 'mcp_transport_error' in r['query_failure_summary']
    assert 'FAKE_SECRET' not in str(r)
    assert [n for n,_ in fake.calls].count('ads_query_compact')==3


def test_cli_exact_query_diagnostic_supported():
    args=build_parser().parse_args(['literature-auth','--probe','--query','PG 1211+143'])
    assert args.query=='PG 1211+143' and args.probe


class ServerLikeMCP:
    def __init__(self): self.calls=[]
    async def call(self,name,args):
        self.calls.append(args)
        if args['query_string']=='"PG 1211 143"':
            return {'success':True,'results':[{'bibcode':'2020A&A...777..123Z'}]}
        raise MCPToolError(name,'ADS query failed: 400 Client Error, token PRIVATE123',
                           code='SERVICE_ERROR',payload={'error': True, 'code':'SERVICE_ERROR'})


def test_uses_conservative_pg_query_when_the_other_forms_fail():
    fake=ServerLikeMCP()
    result=asyncio.run(_search_ads(fake,'PG 1211+143 x-ray outflows',5))
    assert result[1]=='"PG 1211 143"'
    assert result[0][0]['bibcode']=='2020A&A...777..123Z'
    assert result[2][0]['result']=='upstream_http_400_bad_query'
    assert 'PRIVATE123' not in str(result)


class ForbiddenMCP(ServerLikeMCP):
    async def call(self,name,args):
        raise MCPToolError(name,'ADS query failed: 403 Forbidden, token PRIVATE123',
                           code='SERVICE_ERROR')


def test_failed_query_has_actionable_safe_error_classes():
    with pytest.raises(GenerationError,match='upstream_http_403_forbidden=3') as exc:
        asyncio.run(_search_ads(ForbiddenMCP(),'PG 1211+143 X-ray study',5))
    assert 'PRIVATE123' not in str(exc.value)


def test_mixed_literature_plan_without_pg_name_still_searches_pg_target():
    # Original PG 1211+143 plan omits the object name from its science-term query.
    from benchmark.mixed_generation import LITERATURE_PLANS
    from benchmark.literature import _ads_query_candidates
    _, target, _, query = LITERATURE_PLANS[0]
    assert target=='PG 1211+143'
    assert 'PG 1211+143' not in query
    candidate_forms = _ads_query_candidates(query, target_hint=target)
    assert '"PG 1211+143"' in candidate_forms
    assert '"PG 1211 143"' in candidate_forms
    assert candidate_forms[0] == '"PG 1211+143"'


def test_plan_target_passed_into_research_preflight(tmp_path):
    from unittest.mock import AsyncMock, patch
    from benchmark.simple_workflows import create_queries
    from benchmark.generator import GenerationError
    checked=AsyncMock(return_value={'status':'PASS','research_provider':'astroquery_mcp_ads',
        'papers':[{'bibcode':'2020ApJ...555..123Q'}]})
    generated=AsyncMock(side_effect=GenerationError('offline stops before GPT'))
    with patch('benchmark.literature.check_literature_auth',new=AsyncMock(return_value={'status':'PASS'})),\
         patch('benchmark.literature.research_literature',new=checked),\
         patch('benchmark.simple_workflows.generate_mixed',new=generated):
        with pytest.raises(GenerationError,match='offline stops'):
            asyncio.run(create_queries(name='pg-test',output_dir=tmp_path,count=10,require_ads=True))
    assert checked.await_args.kwargs['target_hint']=='PG 1211+143'
