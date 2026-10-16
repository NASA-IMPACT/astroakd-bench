"""Regression: one-step named workflow accepts long reference policies.

This suite uses only mocked ADS, model and archive calls; no live API access.
"""
import asyncio
import math
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from benchmark.api import AstroAKDBench
from benchmark.cli import build_parser, _execute
from benchmark.generator import GenerationError
from benchmark.simple_workflows import create_queries
from benchmark.tests.test_flexible_counts_067111 import fixture_generator
from benchmark.literature import _ads_query_candidates, research_literature
from benchmark.tests.test_literature_0643 import FakeMCP

POLICY='mast=900,simbad=180,heasarc=900,gaia=900,vizier=300'
ATTEMPTS='mast=2,simbad=1,heasarc=2,gaia=2,vizier=1'


def test_exact_user_one_step_command_parses_and_forwards():
    options=build_parser().parse_args(['create-queries', '--name','astroakd_100', '--count','100',
        '--output-dir','datasets', '--require-ads', '--with-reference-answers',
        '--archive-timeouts',POLICY,'--archive-attempts',ATTEMPTS,'--reference-deadline','2100'])
    assert options.archive_timeouts==POLICY
    assert options.archive_attempts==ATTEMPTS
    assert options.reference_deadline==2100
    with patch('benchmark.simple_workflows.create_queries',new_callable=AsyncMock,
               return_value={'status':'PASS'}) as mocked:
        result=asyncio.run(_execute(options))
    assert result['status']=='PASS'
    assert mocked.await_args.kwargs['archive_timeouts']==POLICY
    assert mocked.await_args.kwargs['archive_attempts']==ATTEMPTS
    assert mocked.await_args.kwargs['reference_deadline']==2100


def test_one_step_forwards_reference_policy_and_api_exposes_it(tmp_path):
    reference=AsyncMock(return_value={'status':'COMPLETE','processed':8,'remaining':0,
                                    'dispositions':{'accepted_nonempty':8}})
    with patch('benchmark.simple_workflows.generate_mixed',fixture_generator), \
         patch('benchmark.simple_workflows.collect_references',reference):
        report=asyncio.run(AstroAKDBench(root=tmp_path).create_synthetic_queries(
            name='study10', count=10, with_reference_answers=True, reference_aware=False,
            archive_timeouts=POLICY,archive_attempts=ATTEMPTS,reference_deadline=2100))
    kw=reference.await_args.kwargs
    assert kw['archive_timeouts']==POLICY and kw['archive_attempts']==ATTEMPTS
    assert kw['reference_deadline']==2100
    assert report['reference_collection']['processed']==8


@pytest.mark.parametrize('timeout,expected', [('mast=0','timeouts'),('mast=nan','timeouts')])
def test_invalid_policy_rejected_before_generator(tmp_path,timeout,expected):
    with patch('benchmark.simple_workflows.generate_mixed',new_callable=AsyncMock) as generator:
        with pytest.raises(Exception,match=expected):
            asyncio.run(create_queries(name='bad', count=10, output_dir=tmp_path,
                archive_timeouts=timeout, with_reference_answers=True))
        generator.assert_not_awaited()


def test_reference_deadline_rejected_before_generator(tmp_path):
    with patch('benchmark.simple_workflows.generate_mixed',new_callable=AsyncMock) as generator:
        with pytest.raises(ValueError,match='reference-deadline'):
            asyncio.run(create_queries(name='bad',count=10,output_dir=tmp_path,
                reference_deadline=math.inf,with_reference_answers=True))
        generator.assert_not_awaited()


def test_ads_query_canonicalization_includes_target_form():
    candidates=_ads_query_candidates('Which X-ray outflows of PG 1211+143 are observed?')
    assert len(candidates)==3
    assert '"PG 1211+143"' in candidates
    assert '"PG 1211 143"' in candidates


def test_require_ads_never_web_fallback_on_query_error():
    fake=FakeMCP('http://test',ads=True,raise_ads=True)
    with pytest.raises(GenerationError,match='No OpenAI web-search fallback'):
        asyncio.run(research_literature('PG 1211+143 X-ray outflows',require_ads=True,
            session_factory=lambda url:fake,
            openai_client_factory=lambda: (_ for _ in ()).throw(AssertionError('web invoked'))))
    assert [name for name,_ in fake.calls].count('ads_query_compact')==3


def test_ads_plans_checked_before_openai_and_cached(tmp_path):
    # Preflight must use the real research plan rather than a generic check only.
    ready={'status':'PASS','papers':[{'bibcode':'2023ApJ...111..222A'}],
           'research_provider':'astroquery_mcp_ads', 'research_sources':[],
           'ads_authenticated':True, 'scientific_truth_verified':False}
    fake_research=AsyncMock(return_value=ready)
    gen=AsyncMock(side_effect=GenerationError('offline fixture stops before GPT'))
    with patch('benchmark.literature.check_literature_auth',new=AsyncMock(return_value={'status':'PASS'})), \
         patch('benchmark.literature.research_literature',fake_research), \
         patch('benchmark.simple_workflows.generate_mixed',gen):
        with pytest.raises(GenerationError,match='offline fixture'):
            asyncio.run(create_queries(name='planned',count=10,output_dir=tmp_path,require_ads=True))
    assert fake_research.await_count==1
    assert fake_research.await_args.kwargs['require_ads'] is True
    assert gen.await_args.kwargs['research_fn'] is not None
    assert not list(tmp_path.rglob('*.jsonl'))
