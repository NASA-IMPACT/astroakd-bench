"""0.6.7.11.5: protect paid GPT question batches against late ADS failures.

Entirely offline: generated questions, MCP, ADS and OpenAI are fixtures.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from benchmark.generator import GenerationError
from benchmark.mixed_generation import generate_mixed
from benchmark.simple_workflows import create_queries, dataset_paths
from benchmark.tests.test_mixed_generation_065 import Responses, FixtureSession, fake_research


class LateResearchFailure(Responses):
    def __init__(self):
        super().__init__()
        self.fail_research = True
        self.archive_calls = 0
        self.literature_calls = 0

    def create(self, **kwargs):
        prompt = kwargs['input'][-1]['content']
        if 'SLOTS JSON:\n' in prompt:
            self.archive_calls += 1
        else:
            self.literature_calls += 1
            if self.fail_research:
                raise ConnectionError('simulated transient OpenAI literature failure')
        return super().create(**kwargs)


async def _offline(*args, **kwargs):
    return await generate_mixed(*args,
        session_factory=lambda url: FixtureSession(url), **kwargs)


def test_durable_batches_survive_literature_failure_and_resume_without_repeat(tmp_path):
    client = LateResearchFailure()
    kwargs = dict(name='astroakd_10', root=tmp_path, count=10,
                  research_fn=fake_research,
                  openai_client_factory=lambda:SimpleNamespace(responses=client))
    with patch('benchmark.simple_workflows.generate_mixed', _offline):
        with pytest.raises(GenerationError, match='OpenAI literature question request 1 failed'):
            asyncio.run(create_queries(**kwargs))
        paths = dataset_paths(tmp_path, 'astroakd_10')
        assert not paths['tasks'].exists()
        assert paths['generation_journal'].is_file()
        partial = [json.loads(x) for x in paths['generation_partial'].read_text().splitlines()]
        assert len(partial) == 9
        assert all(x['generation_progress_status']=='PARTIAL_NOT_VALIDATED_NOT_GOLD' for x in partial)
        assert client.archive_calls == 2
        assert client.literature_calls == 1
        with pytest.raises(FileExistsError, match='--resume'):
            asyncio.run(create_queries(**kwargs))
        client.fail_research = False
        final = asyncio.run(create_queries(**kwargs, resume=True))
        assert final['count'] == 10
        assert final['resumed_openai_batches'] == 2
        assert final['openai_requests_this_invocation'] == 0
        assert client.archive_calls == 2  # no repeated question-generation billing
        assert client.literature_calls == 2
        assert len(paths['tasks'].read_text().splitlines()) == 10
        assert not paths['generation_journal'].exists()
        assert not paths['generation_partial'].exists()


def test_incompatible_resume_rejected_before_gpt(tmp_path):
    client = LateResearchFailure()
    kwargs = dict(name='study10', root=tmp_path, count=10,
                  research_fn=fake_research,
                  openai_client_factory=lambda:SimpleNamespace(responses=client))
    with patch('benchmark.simple_workflows.generate_mixed', _offline):
        with pytest.raises(GenerationError):
            asyncio.run(create_queries(**kwargs))
        original_calls = client.archive_calls
        with pytest.raises(GenerationError, match='configuration differs'):
            asyncio.run(create_queries(**kwargs, resume=True, seed=42))
        assert client.archive_calls == original_calls


def test_generation_journal_detects_tampering(tmp_path):
    client = LateResearchFailure()
    kwargs = dict(name='study10', root=tmp_path, count=10,
                  research_fn=fake_research,
                  openai_client_factory=lambda:SimpleNamespace(responses=client))
    with patch('benchmark.simple_workflows.generate_mixed', _offline):
        with pytest.raises(GenerationError):
            asyncio.run(create_queries(**kwargs))
        journal = dataset_paths(tmp_path,'study10')['generation_journal']
        text = journal.read_text().replace('PARTIAL_GENERATION_NOT_A_BENCHMARK_DATASET','COMPLETE_VERIFIED')
        journal.write_text(text)
        with pytest.raises(GenerationError,match='corrupted'):
            asyncio.run(create_queries(**kwargs, resume=True))


def test_checkpoint_cli_accepts_resume():
    from benchmark.cli import build_parser
    args = build_parser().parse_args(['create-queries','--name','astroakd_100',
                                      '--count','100','--resume'])
    assert args.resume is True


def test_ads_minimal_fields_avoids_redundant_standard_query():
    from benchmark.literature import research_literature
    from benchmark.tests.test_literature_0643 import FakeMCP
    from types import SimpleNamespace as N
    class FieldsFallback(FakeMCP):
        async def call_tool(self, name, args, timeout=None):
            if name == 'ads_query_compact' and args['fields'] == 'standard':
                self.calls.append((name,args))
                raise ValueError('ADS standard field retrieval failed')
            return await super().call_tool(name,args,timeout=timeout)
    fake = FieldsFallback('http://test')
    result = asyncio.run(research_literature('PG 1211+143 X-ray outflow',
        session_factory=lambda u:fake, require_ads=True,
        openai_client_factory=lambda: (_ for _ in ()).throw(AssertionError('web invoked'))))
    assert result['research_provider']=='astroquery_mcp_ads'
    assert result['papers'][0]['bibcode']
    assert result['ads_query_attempts'][0]['fields']=='minimal'
    assert len(result['ads_query_attempts']) == 1
    assert all(args['fields']=='minimal' for name,args in fake.calls if name=='ads_query_compact')
