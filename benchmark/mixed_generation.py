"""Native Gold-inspired mixed question generation, integrated in benchmark generate.

OpenAI composes archive questions against live-discovered MCP signatures and
literature questions against actual MCP ADS or web-search evidence. Research
is not a gold answer. Multi-step tasks are intentionally not single-call
validator inputs. No external offline dataset builder is used.
"""
from __future__ import annotations
from .mcp_config import resolve_mcp_url

import asyncio
from collections import Counter
import json
import random
from pathlib import Path
from typing import Any, Callable

from . import __version__, DEFAULT_MCP_URL
from .generator import GenerationError, SUPPORTED_MODULES, parse_modules
from .llm_generation import generate_llm, _openai_client, _create, _response_json, instruction_text
from .literature import research_literature
from .seeds import TARGETS, SkyTarget
from .diversity import analyze_candidates

# *Research anchors*, not expected answers or pre-generated benchmark questions.
# The targets and astronomical intent are informed by Gold Benchmark Dataset.xlsx.
# All literature research is re-executed at generation time through MCP ADS or
# OpenAI web_search. The OpenAI model composes the final question from evidence.
LITERATURE_PLANS = (
    ('heasarc','PG 1211+143','Chandra HETGS observation IDs',
     'quasar redshift 0.0809 outflow velocity 17300 km/s Chandra HETGS 2018'),
    ('mast','PG 1211+143','HST COS program and dataset identifiers',
     'PG 1211+143 simultaneous ultraviolet HST COS Chandra ultrafast outflow paper'),
    ('heasarc','NGC 3783','paper-linked Chandra HETGS observation identifiers',
     '2025ApJ...982...25D NGC 3783 Chandra HETGS ObsIDs'),
    ('heasarc','Haro 11','paper-linked XMM-Newton observations',
     '10.1051/0004-6361/202449388 Haro 11 XMM Newton observations'),
    ('heasarc','tidal disruption transient identified by a paper','NICER observations',
     'nearest tidal disruption event discovery NICER observations published study'),
    ('simbad','planetary nebulae in 2022MNRAS.514.1217D','SIMBAD object identifiers',
     '2022MNRAS.514.1217D planetary nebula names identification'),
    ('heasarc','NGC 1068','Chandra grating observation identifiers from a paper',
     'NGC 1068 Chandra grating high ionization spectroscopy paper ObsIDs'),
    ('mast','NGC 5548','HST COS program and observation identifiers from a paper',
     'NGC 5548 HST COS monitoring paper program and observation IDs'),
)


def parse_task_mix(value: str | None, *, count: int) -> dict[str, int] | None:
    if value is None:
        return None
    if value.strip().casefold() in ('balanced100', 'mixed100', 'science100'):
        if not 1 <= count <= 100:
            raise GenerationError('The current mixed generator supports 1..100 unique tasks with the built-in astronomical target catalog; expand targets for larger datasets')
        # Preserve the qualified 60/20/8/12 mix at N=100. Smaller pilot
        # datasets avoid multi-archive pairs until there are sufficient
        # independently generated same-target archive candidates.
        literature = min(8, round(count * .08))
        coordinate = round(count * .20)
        multi = round(count * .12) if count >= 30 else 0
        archive = count - literature - coordinate - multi
        result = {'archive_driven':archive, 'coordinate_driven':coordinate,
                  'literature_driven':literature, 'multi_archive':multi}
    elif value.strip().casefold() in ('gold50', 'gold-50', 'gold'):
        result = {'archive_driven':32, 'coordinate_driven':10, 'literature_driven':8}
    else:
        result: dict[str,int] = {}
        for part in value.split(','):
            if part.count('=') != 1:
                raise GenerationError('--task-mix must be gold50 or archive_driven=N,coordinate_driven=N,literature_driven=N')
            key, number = (x.strip() for x in part.split('='))
            if key not in ('archive_driven','coordinate_driven','literature_driven','multi_archive') or key in result:
                raise GenerationError(f'Invalid or repeated --task-mix family: {key!r}')
            if not number.isascii() or not number.isdecimal():
                raise GenerationError(f'Invalid --task-mix count for {key}: {number!r}')
            result[key] = int(number)
        if not {'archive_driven','coordinate_driven','literature_driven'}.issubset(result):
            raise GenerationError('--task-mix requires archive_driven,coordinate_driven,literature_driven; multi_archive optional')
        result.setdefault('multi_archive', 0)
    if sum(result.values()) != count:
        raise GenerationError(f'--task-mix requests {sum(result.values())} tasks but --count is {count}')
    if result['archive_driven']+result['coordinate_driven'] < 1:
        raise GenerationError('--task-mix requires at least one archive or coordinate task')
    if result['literature_driven'] > len(LITERATURE_PLANS):
        raise GenerationError(f'Only {len(LITERATURE_PLANS)} literature seed plans available; cannot generate '
                              f'{result["literature_driven"]} literature tasks. Expand seed plans first.')
    return result


def build_multi_archive_tasks(tasks: list[dict[str, Any]], count: int, *, seed: int) -> list[dict[str, Any]]:
    """Convert distinct single-call slots into two-archive tasks, without fabricating evidence.

    The second archive is a separate pre-generated candidate for the same target.
    It remains a normal standalone question; a multi-archive task has no
    single-call reference key and must be separately reviewed after multi-step
    evidence collection. Choosing a unique target for each composite avoids
    treating two multi-step questions as independent confirmations.
    """
    from collections import defaultdict
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        if task['task_type'] == 'archive_driven' and isinstance(task.get('reference_call'), dict):
            by_target[task['target'].casefold()].append(task)
    rng = random.Random(seed + 777)
    eligible = [key for key, group in by_target.items() if len({t['module'] for t in group}) >= 2]
    rng.shuffle(eligible)
    if len(eligible) < count:
        raise GenerationError(f'Only {len(eligible)} cross-archive target pairs available; need {count}. '
                              'Change the task mix/target inventory rather than inventing a second archive call.')
    selected = []
    for key in eligible[:count]:
        group = by_target[key]
        first = next(t for t in group if t not in selected)
        other = next(t for t in group if t['module'] != first['module'])
        modules = [first['module'], other['module']]
        original_call = first['reference_call']
        original_fields = first['answer_spec'].get('expected_columns', [])
        original_question = first['question']
        other_question = other['question']
        first['task_type'] = 'multi_archive'
        first['module'] = 'multi_archive'
        first['source_archive'] = ' + '.join(m.upper() for m in modules)
        first['category'] = 'multi_archive_cross_check'
        first['intent'] = 'cross_archive_evidence_and_association'
        first['question'] = (f'For {first["target"]}, consult both {modules[0].upper()} and '
                             f'{modules[1].upper()}. {original_question.rstrip(" ?")}? '
                             f'Also investigate: {other_question.rstrip(" ?")}? '
                             'Report results separately by archive and discuss whether their '
                             'different observations can be associated; do not assume every row matches.')
        first['constraints'] = {'multi_archive_steps': [
            {'module': modules[0], 'reference_call': original_call,
             'expected_columns': original_fields},
            {'module': modules[1], 'reference_call': other['reference_call'],
             'expected_columns': other['answer_spec'].get('expected_columns', [])}]}
        first['answer_spec'] = {'answer_type': 'multi_archive_comparison',
                                'expected_columns': [], 'expected_answer_status': 'unverified_candidate'}
        first['reference_call'] = None
        first['validation_status'] = 'multistep_candidate_unvalidated'
        first['execution_track'] = 'mcp_multi_archive_two_step'
        first['provenance']['multi_archive_composition'] = 'two_generated_same_target_archive_steps'
        selected.append(first)
    return selected


def _coordinate_variant(task: dict[str,Any]) -> None:
    """Add explicit sky-position constraints without changing the MCP call."""
    center = task['constraints'].get('center_icrs')
    if not isinstance(center, dict) or 'ra_deg' not in center or 'dec_deg' not in center:
        raise GenerationError('Coordinate-driven task lacks a defined ICRS sky center')
    radius = task['constraints'].get('radius')
    region = ''
    if isinstance(radius, dict) and isinstance(radius.get('value'), (int,float)):
        region = f" and search radius {radius['value']} {radius.get('unit','arcmin')}"
    ra=float(center['ra_deg'])/15.0
    rh=int(ra); rm=int((ra-rh)*60); rs=((ra-rh)*60-rm)*60
    dd=abs(float(center['dec_deg'])); dh=int(dd); dm=int((dd-dh)*60); ds=((dd-dh)*60-dm)*60
    sign='+' if center['dec_deg'] >= 0 else '-'
    prefix = (f"At ICRS J2000 RA {rh:02d} {rm:02d} {rs:06.3f}, "
              f"Dec {sign}{dh:02d} {dm:02d} {ds:05.2f} "
              f"(RA {center['ra_deg']} deg, Dec {center['dec_deg']} deg){region}, ")
    task['question'] = prefix + task['question'][0].lower() + task['question'][1:]
    task['task_type'] = 'coordinate_driven'
    task['provenance']['coordinate_question_grounding'] = 'benchmark_supplied_center_and_radius'


def _literature_question(response: Any, plan: tuple[str,str,str,str]) -> str:
    payload = _response_json(response)
    entries = payload['questions']
    if len(entries) != 1 or not isinstance(entries[0],dict):
        raise GenerationError('Literature authoring must return exactly one question')
    question = entries[0].get('question')
    if not isinstance(question,str) or not 35 <= len(question.strip()) <= 1200:
        raise GenerationError('Literature question must contain 35..1200 characters')
    # Do not trust model task ID, paper bibcode, or model-provided MCP calls.
    if plan[1].casefold() not in question.casefold() and plan[1] not in (
        'tidal disruption transient identified by a paper', 'planetary nebulae in 2022MNRAS.514.1217D'):
        raise GenerationError('Literature question dropped the anchored target')
    if '?' not in question:
        raise GenerationError('Literature output is not a question')
    return question.strip()


def _evidence_snippet(evidence: dict[str,Any]) -> str:
    papers = evidence.get('papers') or []
    if papers:
        return json.dumps([{'bibcode':p.get('bibcode'), 'title':p.get('title'), 'year':p.get('year')}
                           for p in papers[:4]], ensure_ascii=False)[:2200]
    return str(evidence.get('research_summary_unverified') or evidence.get('suggested_question_unverified') or
               'No corroborating paper found; ask an explicitly open research question.')[:2200]


async def generate_mixed(url: str | None = None, *, count: int = 50, seed: int = 123,
                         modules: tuple[str,...] = SUPPORTED_MODULES, mix: dict[str,int],
                         timeout: float = 180, uniqueness: str = 'archive-target',
                         backend: str = 'openai', model: str = 'gpt-5.2',
                         use_instructions: bool = True, use_mcp: bool = True,
                         instructions_file: str | Path | None = None,
                         batch_size: int = 5, progress: Callable[[str],None] | None = None,
                         session_factory: Callable | None = None,
                         openai_client_factory: Callable[[],Any] | None = None,
                         research_fn: Callable | None = None,
                         llm_fn: Callable | None = None,
                         targets: tuple[SkyTarget,...] | None = None,
                         require_ads: bool = False,
                         on_batch: Callable[[int, list[dict]], None] | None = None,
                         cached_batches: dict[int, list[dict]] | None = None,
                         on_literature: Callable[[int, dict], None] | None = None,
                         cached_literature: dict[int, dict] | None = None,
                         ) -> tuple[list[dict[str,Any]], dict[str,Any]]:
    if backend not in ('openai','hybrid'):
        raise GenerationError('Mixed Gold generation requires --backend openai or hybrid for literature authoring')
    modules = parse_modules(modules)
    if uniqueness == 'global-target' and count > len(TARGETS):
        raise GenerationError('global-target mixed Gold generation requires more distinct science targets; '
                              'use archive-target or provide an expanded curated seed catalog')
    non_literature = mix['archive_driven']+mix['coordinate_driven']+mix.get('multi_archive', 0)
    if sum(mix.values()) != count:
        raise GenerationError('Mixed family counts must total --count')
    if mix['coordinate_driven'] and not any(x in modules for x in ('mast','heasarc','gaia','vizier')):
        raise GenerationError('coordinate_driven requires a coordinate-capable MCP module')
    # Exclude literature-object names from archive slots so literature follow-up
    # tasks don't collide with the same target and archival module.
    reserved = {p[1].casefold() for p in LITERATURE_PLANS[:mix['literature_driven']]}
    use_targets = targets if targets is not None else TARGETS
    filtered = tuple(t for t in use_targets if t.name.casefold() not in reserved)
    if not filtered:
        raise GenerationError('No archive targets remain after reserving literature targets')
    generate_fn = llm_fn or generate_llm
    tasks, base = await generate_fn(url, count=non_literature, seed=seed, modules=modules,
        timeout=timeout, uniqueness=uniqueness, question_style='answer-oriented',
        backend=backend, model=model, use_instructions=use_instructions,
        use_mcp=use_mcp, instructions_file=instructions_file, batch_size=batch_size,
        session_factory=session_factory, progress=progress, targets=filtered,
        openai_client_factory=openai_client_factory,
        **({'on_batch': on_batch, 'cached_batches': cached_batches} if
           generate_fn is generate_llm and (on_batch is not None or cached_batches) else {}))
    # Select coordinate slots among the modules that can express a sky position.
    coords = [i for i,t in enumerate(tasks) if t['module'] in ('mast','heasarc','gaia','vizier')
              and isinstance(t.get('constraints',{}).get('center_icrs'),dict)]
    if len(coords) < mix['coordinate_driven']:
        raise GenerationError(f'Only {len(coords)} coordinate-capable tasks available; '
                              f'cannot make {mix["coordinate_driven"]} coordinate questions')
    indices = set(random.Random(seed + 79).sample(coords,mix['coordinate_driven']))
    for i,t in enumerate(tasks):
        if i in indices:
            _coordinate_variant(t)
        else:
            t['task_type'] = 'archive_driven'
        t['provenance']['gold_mixed_generation'] = True
    multi = build_multi_archive_tasks(tasks, mix.get('multi_archive', 0), seed=seed)
    # Run real research *at generation time*. These are research and drafting
    # calls, not archive result validation. Keep all source and routing metadata.
    search = research_fn or research_literature
    openai = _openai_client(openai_client_factory)
    instructions = instruction_text(enabled=use_instructions,path=instructions_file)
    literature = []
    auth_stats = Counter()
    for j,plan in enumerate(LITERATURE_PLANS[:mix['literature_driven']],1):
        mod, target, goal, query = plan
        saved = (cached_literature or {}).get(j)
        if saved is not None:
            if saved.get('target') != target or saved.get('constraints', {}).get('literature_query') != query \
                    or saved.get('task_type') != 'literature_driven':
                raise GenerationError(f'Literature checkpoint {j} differs from the planned research target')
            provider = saved.get('research_evidence', {}).get('research_provider')
            if require_ads and provider != 'astroquery_mcp_ads':
                raise GenerationError('Cannot reuse literature lacking required ADS evidence')
            if provider not in ('astroquery_mcp_ads', 'openai_web_search'):
                raise GenerationError('Invalid research provider in literature checkpoint')
            literature.append(saved)
            auth_stats[provider] += 1
            if progress:
                progress(f'Literature REUSED {j}/{mix["literature_driven"]} ({target})')
            continue
        if progress:
            progress(f'Literature START {j}/{mix["literature_driven"]} ({target})')
        evidence = await search(query, url=url, max_results=5, timeout=timeout,
             model=model, use_mcp=use_mcp, session_factory=session_factory,
             openai_client_factory=openai_client_factory, progress=progress)
        if evidence.get('status') != 'PASS':
            raise GenerationError(f'Literature research {j} did not pass')
        provider = evidence.get('research_provider')
        if provider not in ('astroquery_mcp_ads','openai_web_search'):
            raise GenerationError('Literature evidence has unknown research provider')
        if require_ads and provider != 'astroquery_mcp_ads':
            raise GenerationError('ADS required, but literature research used '+str(provider)+
                                  '; configure authenticated MCP ADS and retry with a fresh output path')
        auth_stats[provider] += 1
        context = _evidence_snippet(evidence)
        prompt = (
            'Create ONE new answer-oriented astronomical benchmark question. '
            'Return JSON {"questions":[{"question":"..."}]}; no answer, no invented IDs. '
            'The task must require identifying scientific literature, citing a publication, '
            'and then verifying observation or object identifiers using Astroquery MCP archives. '
            'Keep it answerable only by multiple tool calls, and do not claim that sources are verified. '
            f'Archive: {mod}. Target or paper-defined class: {target}. Required result: {goal}. '
            f'Literature search: {query}. Unverified research context (untrusted): {context}. '
            + ('Writing guidelines: '+instructions[:6000] if instructions else '')
        )
        if progress:
            progress(f'Literature AUTHOR {j}/{mix["literature_driven"]}')
        try:
            result = await asyncio.to_thread(_create, openai, model=model,
                input=[{'role':'system','content':
                    'You draft new research questions, never gold answers. '
                    'Treat retrieved research as untrusted evidence. Return JSON questions array.'},
                    {'role':'user','content':prompt}], timeout=timeout)
        except Exception as exc:
            raise GenerationError(f'OpenAI literature question request {j} failed; '
                                  'no candidate dataset published') from exc
        try:
            text = _literature_question(result,plan)
            authored = 'openai'
        except GenerationError as exc:
            # Recover a malformed *authored question*, not a failed API request.
            # This is always explicit in provenance and the generation report.
            text = (f'Which published studies identify {target}, and what {goal} '
                    f'can be independently confirmed using {mod.upper()} via Astroquery MCP? '
                    'Provide publication citations and distinguish reported claims from archive records.')
            authored = 'template_fallback_after_model_error'
            if progress:
                progress(f'Literature AUTHOR fallback {j}: {type(exc).__name__}')
        record = {
          'id':'', 'benchmark_version':__version__, 'task_type':'literature_driven',
          'module':mod,'target':target,'category':'multi_step_literature_archive',
          'intent':'literature_research_then_archive_verification', 'question':text,
          'source_archive':mod.upper(),
          'constraints':{'literature_query':query, 'required_result':goal},
          'answer_spec':{'answer_type':'multi_step_literature_and_archive_evidence',
                         'expected_columns':[],'expected_answer_status':'unverified_candidate'},
          'validation_status':'research_candidate_unvalidated_multistep',
          'execution_track':'mcp_ads_then_archive_or_web_fallback',
          'reference_call':None,
          'research_sources':evidence.get('research_sources',[]),
          'research_evidence':{'research_provider':provider,
              'ads_authenticated':bool(evidence.get('ads_authenticated',False)),
              'fallback_reason':evidence.get('fallback_reason'),
              'research_response_format':evidence.get('research_response_format'),
              'bibcodes':[p.get('bibcode') for p in evidence.get('papers',[]) if p.get('bibcode')],
              'source_review_required': bool(evidence.get('source_review_required',False)),
              'scientific_truth_verified':False},
          'provenance':{'generation_backend':backend,'literature_question_author':authored,
              'instructions_used':use_instructions,'research_query':query,'gold_mixed_generation':True},
        }
        literature.append(record)
        if on_literature is not None:
            on_literature(j, record)
    # Interleave the three families with deterministic positions, assigning IDs
    # *after* authoring; the model never assigns authoritative identifiers.
    all_tasks = tasks + literature
    random.Random(seed+101).shuffle(all_tasks)
    for i,t in enumerate(all_tasks,1):
        t['id'] = f'ASTROAKD-MIX-{i:05d}'
        t['benchmark_version'] = __version__
        t['provenance']['generation_index'] = i
    audit = analyze_candidates(all_tasks)
    if any(audit['counts'].values()):
        raise GenerationError('Mixed generator failed duplicate audit: '+str(audit['counts']))
    actual = Counter(t['task_type'] for t in all_tasks)
    if any(actual[k] != n for k,n in mix.items()):
        raise GenerationError('Mixed task-family quotas not satisfied')
    summary = dict(base)
    summary.update({'milestone':'0.6.5 — NATIVE_GOLD_MIXED_QUERY_GENERATION',
       'benchmark_version':__version__, 'status':'PASS','count':len(all_tasks),
       'task_mix':dict(mix),'actual_task_types':dict(actual),
       'research_provider_counts':dict(auth_stats),
       'literature_research_requests':len(literature),
       'literature_question_author_fallbacks':sum(t['provenance']['literature_question_author']!='openai' for t in literature),
       'archive_queries_executed':0,'expected_answers_verified':0,
       'scientific_truth_verified':False,'single_call_candidates':len(tasks),
       'executable_single_call_candidates':len(tasks) if use_mcp else 0,
       'multistep_literature_candidates':len(literature),
       'multistep_multi_archive_candidates':len(multi),
       'distinct_archive_target_pairs':audit['distinct_archive_target_pairs'],
       'duplicate_counts':audit['counts'],
       'notes': ['All tasks are created inside AstroAKD-Bench, not using an external dataset builder.',
                 'MCP ADS/search and model question drafting are performed live for literature tasks.',
                 'Literature and multi-archive tasks are multistep, unverified candidates excluded from single-call validation.',
                 'An OpenAI-generated question, successful search, or source citation is not a validated answer.']})
    return all_tasks,summary
