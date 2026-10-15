"""Literature evidence discovery through the *external* astroquery MCP server.

ADS authentication is decided by the server's astroquery_check_auth tool. If
unavailable, research falls back to the OpenAI Responses API web_search tool.
Neither result type is a validated scientific answer or an MCP observation call.
No ADS token is transmitted to this client, logged, or saved in artifacts.
"""
from __future__ import annotations
from .mcp_config import resolve_mcp_url

import asyncio
import re
from typing import Any, Callable

from . import DEFAULT_MCP_URL, __version__
from .client import AstroqueryMCPClient
from .generator import GenerationError
from .llm_generation import _openai_client, _create, _observed_urls, _tool_uses, _valid_url
import json


def _ads_server_enabled(auth: Any) -> bool:
    """Use the documented server check_auth response, never reveal credentials."""
    if not isinstance(auth, dict):
        return False
    configured = auth.get('configured', {})
    if isinstance(configured, dict) and configured.get('ads') is True:
        return True
    status = auth.get('status', {})
    ads = status.get('ads', {}) if isinstance(status, dict) else {}
    return (isinstance(ads, dict) and ads.get('configured') is True
            and configured.get('ads') is not False)


def _safe_papers(payload: Any, limit: int) -> list[dict[str, Any]]:
    """Keep bounded public bibliographic fields, not opaque server state."""
    if not isinstance(payload, dict) or payload.get('success') is False:
        raise GenerationError('MCP ADS returned an unsuccessful literature result')
    records = payload.get('results', payload.get('papers', []))
    if not isinstance(records, list):
        raise GenerationError('MCP ADS returned no structured paper list')
    keys = ('bibcode', 'title', 'first_author', 'author', 'year', 'doi', 'pubdate', 'abstract', 'pub')
    return [dict((k, v[:1200] if isinstance(v,str) else v)
                 for k in keys if (v := record.get(k)) is not None)
            for record in records[:limit] if isinstance(record, dict)]


def _ads_query_candidates(query: str) -> list[str]:
    """Try the authored ADS query, then a conservative target-only search.

    The fallback is a search formulation, never an inferred paper/answer.
    Solr can reject unescaped punctuation in long natural-language queries.
    """
    choices = [query.strip()]
    target = re.search(r'\b(?:PG\s*\d{3,5}\s*\+\s*\d{2,4}|NGC\s*\d{1,5}|Haro\s*\d{1,4})\b', query, re.I)
    if target:
        choices.append('"' + ' '.join(target.group(0).split()) + '"')
    else:
        bibcode = re.search(r'\b\d{4}[A-Za-z&.0-9]{10,16}\b', query)
        if bibcode:
            choices.append('bibcode:' + bibcode.group(0))
        else:
            # Do not blindly forward Solr operators or punctuation such as /.
            safe = re.sub(r'[^A-Za-z0-9 ]+', ' ', query)
            safe = ' '.join(safe.split()[:7])
            if safe and safe != query:
                choices.append(safe)
    return list(dict.fromkeys(choices))


async def _search_ads(mcp: AstroqueryMCPClient, query: str, max_results: int):
    """Return real paper evidence or fail without fabricating bibliographic records.

    Keep failures classified and auditable, but never store raw upstream errors
    that might contain credentials or sensitive connection details.
    """
    attempts = []
    for candidate in _ads_query_candidates(query):
        for fields in ('standard', 'minimal'):
            try:
                result = await mcp.call('ads_query_compact', {
                    'query_string':candidate, 'fields':fields,
                    'max_results':max_results})
                papers = _safe_papers(result, max_results)
                if papers and any(isinstance(p.get('bibcode'), str) and p['bibcode'] for p in papers):
                    attempts.append({'query':candidate, 'fields':fields, 'result':'accepted'})
                    return papers, candidate, attempts
                attempts.append({'query':candidate,'fields':fields, 'result':'empty_or_missing_bibcodes'})
            except Exception as exc:
                # Do not write raw ADS exception bodies; they can echo credentials.
                from .errors import MCPToolError, MCPTransportError
                category = ('tool_error' if isinstance(exc, MCPToolError) else
                            'transport_error' if isinstance(exc, MCPTransportError) else
                            'invalid_response')
                attempts.append({'query':candidate,'fields':fields,'result':category})
    raise GenerationError('ADS search returned no usable bibliographic evidence '
                          f'({len(attempts)} query form(s) attempted; '
                          + ', '.join(item['result'] for item in attempts) + ')')


def _message_citation_urls(response: Any) -> set[str]:
    """Collect URL citations from Responses message annotations, not model prose.

    The web_search action.sources field is optional. Modern Responses API
    messages also supply url_citation annotations; both are evidence-bearing.
    """
    urls: set[str] = set()
    for item in getattr(response, 'output', []) or []:
        if getattr(item, 'type', None) != 'message':
            continue
        for content in getattr(item, 'content', []) or []:
            for annotation in getattr(content, 'annotations', []) or []:
                kind = (annotation.get('type') if isinstance(annotation, dict)
                        else getattr(annotation, 'type', None))
                if kind != 'url_citation':
                    continue
                url = (annotation.get('url') if isinstance(annotation, dict)
                       else getattr(annotation, 'url', None))
                if _valid_url(url):
                    urls.add(url)
    return urls


def _web_research_payload(response: Any, fallback_reason: str) -> dict[str, Any]:
    """Normalize an actual searched response, JSON *or* cited prose.

    JSON is still accepted for backward compatibility, but web_search does
    not contractually guarantee model output to be JSON. Do not parse arbitrary
    prose into a fabricated paper or gold answer.
    """
    text = getattr(response, 'output_text', None)
    if not isinstance(text, str) or not text.strip():
        raise GenerationError(f'OpenAI web-search returned no readable response (route: {fallback_reason})')
    text = text.strip()
    if len(text) > 16000:
        text = text[:16000]
    if len(text) < 12:
        raise GenerationError(f'OpenAI web-search returned insufficient text (route: {fallback_reason})')
    if getattr(response, 'status', 'completed') not in ('completed', None):
        raise GenerationError(f'OpenAI web-search response incomplete (route: {fallback_reason})')
    question = None
    summary = None
    fmt = 'text'
    try:
        candidate = json.loads(text)
    except (ValueError, TypeError):
        summary = text
    else:
        if isinstance(candidate, dict):
            suggestions = candidate.get('questions', [])
            if (isinstance(suggestions, list) and len(suggestions) == 1
                and isinstance(suggestions[0], dict)
                and isinstance(suggestions[0].get('question'), str)
                and len(suggestions[0]['question'].strip()) >= 12):
                question = suggestions[0]['question'].strip()[:3000]
                fmt = 'json_questions'
            elif isinstance(candidate.get('summary'), str) and candidate['summary'].strip():
                summary = candidate['summary'].strip()[:16000]
                fmt = 'json_summary'
        if question is None and summary is None:
            summary = text  # searchable evidence, not a structured gold answer
    urls = sorted(_observed_urls(response) | _message_citation_urls(response))
    result = {'research_response_format':fmt,
              'research_sources':urls,
              'source_review_required':not bool(urls),
              'research_summary_unverified':summary,
              'suggested_question_unverified':question}
    return result


async def check_literature_auth(*, url: str | None = None,
                                timeout: float = 180.0,
                                session_factory: Callable | None = None,
                                probe: bool = False) -> dict[str, Any]:
    """Check server authentication and optionally perform one real ADS read.

    Probe failures deliberately do not expose raw server exceptions or tokens.
    The same probe is a fail-fast prerequisite for --require-ads generation.
    """
    try:
        async with AstroqueryMCPClient(url, timeout=timeout,
                                       session_factory=session_factory) as mcp:
            auth = await mcp.call('astroquery_check_auth')
            authenticated = _ads_server_enabled(auth)
            tools = {t['name'] for t in await mcp.list_tools()}
            available = 'ads_query_compact' in tools
            result = {'status':'PASS','benchmark_version':__version__,
                'endpoint':url, 'ads_authenticated':authenticated,
                'ads_tool_available':available, 'token_values_exposed':False}
            if not probe:
                return result
            if not authenticated:
                reason = 'ads_not_configured'
            elif not available:
                reason = 'ads_tool_unavailable'
            else:
                try:
                    # A small, known ADS bibcode probe. Successful auth status
                    # alone cannot establish actual upstream search access.
                    payload = await mcp.call('ads_query_compact', {
                        'query_string':'bibcode:2022MNRAS.514.1217D',
                        'fields':'minimal','max_results':1})
                    papers = _safe_papers(payload, 1)
                    reason = None if papers and isinstance(papers[0].get('bibcode'),str) else 'ads_probe_empty'
                except Exception:
                    reason = 'ads_search_unavailable'
            result.update({'status':'PASS' if reason is None else 'FAIL',
                'ads_probe_success':reason is None,'reason':reason})
            return result
    except Exception:
        if not probe:
            raise
        return {'status':'FAIL','benchmark_version':__version__,
            'endpoint':url,'ads_authenticated':False,'ads_tool_available':False,
            'ads_probe_success':False,'reason':'mcp_auth_check_unavailable',
            'token_values_exposed':False}


async def research_literature(query: str, *, url: str | None = None,
                              max_results: int = 5, timeout: float = 180.0,
                              model: str = 'gpt-5.2', use_mcp: bool = True,
                              session_factory: Callable | None = None,
                              openai_client_factory: Callable[[], Any] | None = None,
                              progress: Callable[[str], None] | None = None,
                              require_ads: bool = False,
                              ) -> dict[str, Any]:
    """Research a literature-driven prompt; fail over to LLM web research.

    With MCP, call astroquery_check_auth on the server. Prefer its
    ads_query_compact tool when authenticated. If ADS is not available, use
    OpenAI web_search. All returns carry explicit, non-gold provenance.
    """
    if not isinstance(query, str) or not 5 <= len(query.strip()) <= 1500:
        raise GenerationError('Literature query must contain 5..1500 characters')
    if not 1 <= max_results <= 20:
        raise GenerationError('Literature max_results must be 1..20')
    query = query.strip()
    fallback_reason = 'mcp_disabled' if not use_mcp else 'ads_not_configured'
    server_ads_authenticated = False
    ads_tool_available = False
    ads_error_category = None
    if use_mcp:
        try:
            async with AstroqueryMCPClient(url, timeout=timeout,
                                          session_factory=session_factory) as mcp:
                auth = await mcp.call('astroquery_check_auth')
                server_ads_authenticated = _ads_server_enabled(auth)
                if server_ads_authenticated:
                    tools = {t['name'] for t in await mcp.list_tools()}
                    ads_tool_available = 'ads_query_compact' in tools
                    if ads_tool_available:
                        try:
                            papers, used, attempts = await _search_ads(mcp, query, max_results)
                            return {'status':'PASS','benchmark_version':__version__,
                                'query':query,'task_type':'literature_driven',
                                'research_provider':'astroquery_mcp_ads',
                                'mcp_tool':'ads_query_compact', 'papers':papers,
                                'ads_query_used':used, 'ads_query_attempts':attempts,
                                'research_sources': ['https://ui.adsabs.harvard.edu/abs/' + p['bibcode']
                                    for p in papers if isinstance(p.get('bibcode'),str)],
                                'ads_authenticated':True,'web_search_calls':0,
                                'scientific_truth_verified':False,
                                'archive_observation_validation':'not_performed'}
                        except GenerationError as exc:
                            # Log a safe summary, never the server's raw exception.
                            ads_error_category = str(exc)
                            fallback_reason = 'ads_search_unavailable'
                    else:
                        fallback_reason = 'ads_tool_unavailable'
                else:
                    fallback_reason = 'ads_not_configured'
        except Exception:
            fallback_reason = 'mcp_auth_check_unavailable'
    if require_ads:
        details = ': ' + ads_error_category if ads_error_category else ''
        raise GenerationError('ADS required: actual literature search unavailable '
                              f'({fallback_reason}){details}. No OpenAI web-search fallback was invoked.')
    if progress is not None:
        progress(f"ADS route unavailable ({fallback_reason}); using OpenAI web_search")
    client = _openai_client(openai_client_factory)
    try:
        response = await asyncio.to_thread(_create, client,
            model=model, tools=[{'type':'web_search'}], tool_choice='required',
            include=['web_search_call.action.sources'],
            input=[{'role':'system','content':
                'Research astronomical literature using web search and provide concise findings '
                'with supporting citations. Plain text with citations is acceptable; JSON is optional. '
                'Do not invent references or claim a research finding is verified gold.'},
                {'role':'user','content':query}], timeout=timeout)
    except Exception as exc:
        raise GenerationError(f'ADS unavailable ({fallback_reason}) and OpenAI web-search fallback failed; '
                              'check OPENAI_API_KEY and network access') from exc
    calls = _tool_uses(response)
    if calls < 1:
        raise GenerationError(f'ADS unavailable ({fallback_reason}) and OpenAI fallback returned no web_search call')
    # Web research is evidence to inspect, not a guaranteed JSON question batch.
    # Retain citations from both the optional web_search sources and message
    # annotations. A prose answer must never be passed through _response_json().
    evidence = _web_research_payload(response, fallback_reason)
    return {'status':'PASS','benchmark_version':__version__,
            'query':query,'task_type':'literature_driven',
            'research_provider':'openai_web_search',
            'fallback_reason':fallback_reason,
            **evidence,
            'papers':[], 'ads_authenticated':server_ads_authenticated,
            'ads_tool_available':ads_tool_available, 'web_search_calls':calls,
            'scientific_truth_verified':False,
            'archive_observation_validation':'not_performed'}
