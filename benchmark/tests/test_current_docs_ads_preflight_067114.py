"""Current-only docs and fail-fast ADS route checks; all offline."""
import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from benchmark.generator import GenerationError
from benchmark.literature import check_literature_auth
from benchmark.simple_workflows import create_queries
from benchmark.tests.test_literature_0643 import FakeMCP
from benchmark.cli import build_parser

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('ads,raise_ads,reason', [
    (False,False,'ads_not_configured'),
    (True,True,'ads_search_unavailable'),
])
def test_read_only_real_ads_probe(ads, raise_ads, reason):
    fake = FakeMCP('http://mock',ads=ads,raise_ads=raise_ads)
    result = asyncio.run(check_literature_auth(
        session_factory=lambda _: fake, probe=True))
    assert result['status']=='FAIL'
    assert result['reason']==reason
    assert result['ads_probe_success'] is False
    assert result['token_values_exposed'] is False
    assert 'FAKE_SECRET' not in str(result)


def test_successful_ads_probe_reports_usable_route():
    fake = FakeMCP('http://mock',ads=True)
    result = asyncio.run(check_literature_auth(
        session_factory=lambda _: fake,probe=True))
    assert result['status']=='PASS'
    assert result['ads_probe_success'] is True
    assert [name for name,_ in fake.calls]==['astroquery_check_auth','ads_query_compact']


def test_require_ads_fails_before_openai_and_no_files(tmp_path):
    generated = AsyncMock(side_effect=AssertionError('OpenAI invoked before ADS preflight'))
    with patch('benchmark.literature.check_literature_auth',
               new=AsyncMock(return_value={'status':'FAIL','reason':'ads_search_unavailable'})):
        with pytest.raises(GenerationError,match='No OpenAI question-generation calls'):
            asyncio.run(create_queries(count=40,name='early_stop',output_dir=tmp_path,
                require_ads=True,llm_fn=generated))
    assert generated.await_count==0
    assert list(tmp_path.rglob('*.jsonl'))==[]


def test_no_ads_requirement_skips_probe(tmp_path):
    # The no-ADS branch still has the historic ability to use web fallback.
    parsed=build_parser().parse_args(['create-queries','--name','test','--count','10'])
    assert not parsed.require_ads
    assert build_parser().parse_args(['literature-auth','--probe']).probe


def test_current_site_and_archival_separation():
    conf = (ROOT/'docs/conf.py').read_text()
    assert 'tomllib' in conf and 'pyproject.toml' in conf
    assert not any((ROOT/'docs').rglob('*_0_6_*.md'))
    assert not list(ROOT.glob('INSTALL_ASTROAKD_BENCH_*.md'))
    assert not list(ROOT.glob('QUALIFICATION_*.md'))
    assert not list(ROOT.glob('CONVERSATION_HANDOFF_THROUGH_*.md'))
    manifest=json.loads((ROOT/'archives/historical_documentation_manifest_0_6_7_11_4.json').read_text())
    assert manifest['root_historical_count']>70
    assert manifest['docs_source_count']>20
    assert 'version = "'+__import__('benchmark').__version__+'"' in (ROOT/'pyproject.toml').read_text()
    assert '118 files' not in (ROOT/'datasets/README.md').read_text()
    index=(ROOT/'docs/index.md').read_text()
    assert '0_6_7' not in index
    assert index.count('benchmark/') >= 7


def test_science_frozen_fixtures_unchanged():
    expected = {
     'benchmark/tests/fixtures/legacy/generated/scorable_50.jsonl':
        '4744ae4df40381eea635a92a13d8af6f83fd69c0e2274c839e1dbb04f382bbb8',
     'benchmark/tests/fixtures/legacy/gold/scorable_50_reference_oracle.jsonl':
        '58caf910963cdce4e333ae5a0a6d48501ece27bce71352b15664a10a76fc1d5e',
    }
    for path,sha in expected.items():
        f=ROOT/path
        assert f.exists(),path
        assert hashlib.sha256(f.read_bytes()).hexdigest()==sha,path
