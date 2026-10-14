"""Literature evidence discovery through the *external* astroquery MCP server.

ADS authentication is decided by the server's astroquery_check_auth tool. If
unavailable, research falls back to the OpenAI Responses API web_search tool.
Neither result type is a validated scientific answer or an MCP observation call.
No ADS token is transmitted to this client, logged, or saved in artifacts.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from . import DEFAULT_MCP_URL, __version__
from .client import AstroqueryMCPClient
from .generator import GenerationError
from .llm_generation import _openai_client, _create, _observed_urls, _response_json, _tool_uses


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


async def research_literature(query: str, *, url: str = DEFAULT_MCP_URL,
                              max_results: int = 5, timeout: float = 180.0,
                              model: str = 'gpt-4.1-mini', use_mcp: bool = True,
                              session_factory: Callable | None = None,
                              openai_client_factory: Callable[[], Any] | None = None,
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
    if use_mcp:
        try:
            async with AstroqueryMCPClient(url, timeout=timeout,
                                          session_factory=session_factory) as mcp:
                auth = await mcp.call('astroquery_check_auth')
                if _ads_server_enabled(auth):
                    tools = {t['name'] for t in await mcp.list_tools()}
                    if 'ads_query_compact' in tools:
                        try:
                            payload = await mcp.call('ads_query_compact',
                                    {'query_string':query,'fields':'standard',
                                     'max_results':max_results})
                            papers = _safe_papers(payload, max_results)
                            return {'status':'PASS','benchmark_version':__version__,
                                'query':query,'task_type':'literature_driven',
                                'research_provider':'astroquery_mcp_ads',
                                'mcp_tool':'ads_query_compact', 'papers':papers,
                                'research_sources': ['https://ui.adsabs.harvard.edu/abs/' + p['bibcode']
                                    for p in papers if isinstance(p.get('bibcode'),str)],
                                'ads_authenticated':True,'web_search_calls':0,
                                'scientific_truth_verified':False,
                                'archive_observation_validation':'not_performed'}
                        except Exception:
                            # MCP returned a tool error (including expired ADS token)
                            # or malformed response: do not leak raw error payload.
                            fallback_reason = 'ads_search_unavailable'
                    else:
                        fallback_reason = 'ads_tool_unavailable'
                else:
                    fallback_reason = 'ads_not_configured'
        except Exception:
            fallback_reason = 'mcp_auth_check_unavailable'
    client = _openai_client(openai_client_factory)
    try:
        response = await asyncio.to_thread(_create, client,
            model=model, tools=[{'type':'web_search'}], tool_choice='required',
            input=[{'role':'system','content':
                'Research astronomical literature using web search. Reply with JSON containing '
                'a questions array of one object: {"id":"research", "question":"..."}. '
                'The question must be grounded in the user request and must not assert that '
                'a source, object identification, or dataset was verified. Do not invent citations.'},
                {'role':'user','content':query}], timeout=timeout)
    except Exception as exc:
        raise GenerationError('ADS unavailable and OpenAI web-search fallback failed; '
                              'check OPENAI_API_KEY and network access') from exc
    calls = _tool_uses(response)
    if calls < 1:
        raise GenerationError('ADS unavailable and OpenAI fallback returned no web_search call')
    # Demand a usable response; the model's text is a research suggestion, not gold.
    payload = _response_json(response)
    suggestions = payload.get('questions', [])
    if len(suggestions) != 1 or not isinstance(suggestions[0],dict) or not isinstance(suggestions[0].get('question'),str):
        raise GenerationError('Fallback model did not return a valid literature question')
    return {'status':'PASS','benchmark_version':__version__,
            'query':query,'task_type':'literature_driven',
            'research_provider':'openai_web_search',
            'fallback_reason':fallback_reason,
            'suggested_question_unverified':suggestions[0]['question'],
            'research_sources':sorted(_observed_urls(response)),
            'papers':[], 'ads_authenticated':False, 'web_search_calls':calls,
            'scientific_truth_verified':False,
            'archive_observation_validation':'not_performed'}
