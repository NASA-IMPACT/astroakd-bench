"""0.6.4.4: real-world Responses web_search prose + MCP routing guards."""
import asyncio
import unittest
from types import SimpleNamespace as O
from benchmark.literature import (research_literature, check_literature_auth,
                                  _web_research_payload)
from benchmark.generator import GenerationError
from benchmark.cli import build_parser
from benchmark.tests.test_literature_0643 import FakeMCP, FakeResponses


class ProseResponses:
    def __init__(self, *, annotation=True, sources=False, text=None, status='completed'):
        self.calls=[]
        self.annotation=annotation
        self.sources=sources
        self.text=text if text is not None else (
            'The search identifies possible HETGS and outflow publications; '
            'inspect the cited sources before using them as a gold answer.')
        self.status=status
    def create(self, **kwargs):
        self.calls.append(kwargs)
        citation = O(type='url_citation',url='https://ui.adsabs.harvard.edu/abs/2020ApJ...123..456Z')
        return O(status=self.status, output_text=self.text,
            output=[O(type='web_search_call',action=O(sources=(
                [O(url='https://example.org/article')] if self.sources else []))),
                O(type='message',content=[O(type='output_text',annotations=(
                    [citation] if self.annotation else []))])])

class Literature0644Tests(unittest.TestCase):
    def test_realistic_web_prose_accepted_with_citation_annotation(self):
        client=ProseResponses()
        r=asyncio.run(research_literature('quasar high velocity outflow', use_mcp=False,
                           openai_client_factory=lambda:O(responses=client)))
        self.assertEqual(r['research_provider'],'openai_web_search')
        self.assertEqual(r['research_response_format'],'text')
        self.assertIn('publications',r['research_summary_unverified'])
        self.assertEqual(r['research_sources'],['https://ui.adsabs.harvard.edu/abs/2020ApJ...123..456Z'])
        self.assertFalse(r['source_review_required'])
        self.assertEqual(r['web_search_calls'],1)
        self.assertFalse(r['scientific_truth_verified'])

    def test_literature_web_json_backward_compatible(self):
        r=asyncio.run(research_literature('AGN outflow papers', use_mcp=False,
            openai_client_factory=lambda:O(responses=FakeResponses())))
        self.assertEqual(r['research_response_format'],'json_questions')
        self.assertEqual(r['suggested_question_unverified'],'Which paper describes the source?')

    def test_realistic_ads_missing_does_not_fail_when_web_returns_prose(self):
        events=[]
        r=asyncio.run(research_literature('Chandra high velocity outflows',
            session_factory=lambda u:FakeMCP(u,ads=False),
            openai_client_factory=lambda:O(responses=ProseResponses(sources=True)),
            progress=events.append))
        self.assertEqual(r['fallback_reason'],'ads_not_configured')
        self.assertIn('ads_not_configured', events[0])
        self.assertEqual(len(r['research_sources']),2)

    def test_unauthenticated_web_search_without_citations_is_review_only(self):
        r=asyncio.run(research_literature('AGN high velocity papers',use_mcp=False,
            openai_client_factory=lambda:O(responses=ProseResponses(annotation=False))))
        self.assertTrue(r['source_review_required'])
        self.assertEqual(r['research_sources'],[])

    def test_invalid_web_response_still_fails(self):
        for output, status in [('', 'completed'),('tiny','completed'),('A plausible but incomplete survey response.','incomplete')]:
            with self.subTest(output=output,status=status):
                with self.assertRaisesRegex(GenerationError,'OpenAI web-search'):
                    asyncio.run(research_literature('AGN outflow papers',use_mcp=False,
                        openai_client_factory=lambda:O(responses=ProseResponses(text=output,status=status))))

    def test_literature_auth_probe_never_exposes_token(self):
        fake=FakeMCP('http://local',ads=True)
        result=asyncio.run(check_literature_auth(session_factory=lambda u:fake))
        self.assertEqual(result['status'],'PASS')
        self.assertTrue(result['ads_authenticated'])
        self.assertTrue(result['ads_tool_available'])
        self.assertNotIn('API_DEV_KEY',str(result))
        self.assertEqual([name for name, _ in fake.calls], ['astroquery_check_auth'])
        args=build_parser().parse_args(['literature-auth','--json-format','pretty'])
        self.assertEqual(args.command,'literature-auth')

    def test_authenticated_ads_error_retains_true_auth_provenance(self):
        r=asyncio.run(research_literature('AGN HETGS outflow papers',
            session_factory=lambda u:FakeMCP(u,ads=True,raise_ads=True),
            openai_client_factory=lambda:O(responses=ProseResponses())))
        self.assertTrue(r['ads_authenticated'])
        self.assertTrue(r['ads_tool_available'])
        self.assertEqual(r['fallback_reason'],'ads_search_unavailable')
        self.assertEqual(r['research_provider'],'openai_web_search')

    def test_mcp_ads_remains_first_choice_without_openai(self):
        r=asyncio.run(research_literature('AGN papers with HETGS outflows',
            session_factory=lambda u:FakeMCP(u,ads=True),
            openai_client_factory=lambda:(_ for _ in ()).throw(AssertionError('Do not use OpenAI'))))
        self.assertEqual(r['research_provider'],'astroquery_mcp_ads')
        self.assertEqual(r['web_search_calls'],0)

if __name__=='__main__':unittest.main()
