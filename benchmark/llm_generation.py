"""Optional LLM question authoring with MCP-backed or web-search-backed context.

The LLM never chooses or mutates MCP tool arguments; all executable calls are
pre-bound using the qualified generator. In no-MCP mode, tasks are explicitly
research-only and cannot be mistaken for validated Astroquery reference calls.
"""
from __future__ import annotations
from .mcp_config import resolve_mcp_url

import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlsplit

from . import __version__, DEFAULT_MCP_URL
from .generator import (
    BoundMethod, GenerationError, SUPPORTED_MODULES, generate,
    generate_candidates, parse_modules,
)
from .seeds import SkyTarget
from .diversity import analyze_candidates

INSTRUCTIONS_PATH = Path(__file__).resolve().parent.parent / 'instructions' / 'astroakd_bench' / 'AstroAKD-Bench_Instruction.md'
INSTRUCTIONS_VERSION = 'astro_benchmark_gold_0_6_4_3'
BASE_SYSTEM = (
    'You author astronomical data-discovery benchmark questions as STRICT JSON. '
    'You must preserve the target, archive, and data fields supplied for each slot. '
    'Never fabricate expected answers, observations, dates, filters or unsupported constraints. '
    'Return a JSON object with exactly a "questions" array containing one object per slot: '
    '{"id":"...", "question":"..."}. No markdown.'
)
WEB_SYSTEM = (
    'You author astronomical data-discovery benchmark questions using real web-search evidence. '
    'Use web search before responding. Return a JSON object with a "questions" array. '
    'Each item has "id", "question", and "source_urls" (array of actual https URLs from research, or empty if unavailable). '
    'Never supply an expected answer. Preserve every supplied target and archive. '
    'Do not claim a generated question is a valid Astroquery MCP call. No markdown.'
)


def instruction_text(*, enabled: bool, path: str | Path | None = None) -> str:
    if not enabled:
        if path is not None:
            raise GenerationError('Cannot specify custom instructions with --no-instructions')
        return ''
    source = Path(path) if path is not None else INSTRUCTIONS_PATH
    try:
        text = source.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise GenerationError(f'Cannot read instructions file {source}: {exc}') from exc
    if not 20 <= len(text) <= 65536:
        raise GenerationError('Instructions file must contain 20..65536 characters')
    return text


def _response_json(response: Any) -> dict[str, Any]:
    text = getattr(response, 'output_text', None)
    if not isinstance(text, str) or not text.strip():
        raise GenerationError('OpenAI Responses API returned no text question batch')
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenerationError('OpenAI output is not valid JSON; no candidate file published') from exc
    if not isinstance(result, dict) or not isinstance(result.get('questions'), list):
        raise GenerationError('OpenAI output must contain a questions array')
    return result


def _tool_uses(response: Any) -> int:
    return sum(1 for item in getattr(response, 'output', [])
               if getattr(item, 'type', None) == 'web_search_call')


def _observed_urls(response: Any) -> set[str]:
    """Only URLs surfaced by the actual tool response count as observed search sources."""
    urls: set[str] = set()
    for item in getattr(response, 'output', []):
        if getattr(item, 'type', None) != 'web_search_call':
            continue
        action = getattr(item, 'action', None)
        for source in getattr(action, 'sources', []) or []:
            url = getattr(source, 'url', None)
            if _valid_url(url):
                urls.add(url)
    return urls


def _valid_url(url: Any) -> bool:
    if not isinstance(url, str) or len(url) > 2048:
        return False
    parsed = urlsplit(url)
    return parsed.scheme == 'https' and bool(parsed.netloc) and not parsed.username and not parsed.password


def _fixed_bindings(modules: tuple[str, ...]) -> dict[str, BoundMethod]:
    """Local *unverified* bindings for choosing research slots; never published as MCP calls."""
    names = {
        'simbad': ('query_object', {'object': 'object_name'}),
        'mast': ('query_region', {'coordinate': 'coordinates', 'radius': 'radius'}),
        'heasarc': ('query_region', {'coordinate': 'position', 'radius': 'radius', 'catalog': 'catalog'}),
        'gaia': ('query_object', {'coordinate': 'coordinate', 'radius': 'radius'}),
        'vizier': ('query_region', {'coordinate': 'coordinates', 'radius': 'radius', 'catalog': 'catalog'}),
    }
    return {m: BoundMethod(m, names[m][0], names[m][1],
                           tuple({'name': key, 'type': 'Any', 'required': False}
                                 for key in names[m][1].values()), 'unverified_no_mcp')
            for m in modules}


def _slots_prompt(tasks: list[dict[str, Any]], *, mode: str, use_mcp: bool) -> str:
    slots = []
    for task in tasks:
        spec = task.get('answer_spec', {})
        slots.append({'id': task['id'], 'archive': task['module'], 'target': task['target'],
                      'intent': task['intent'], 'allowed_result_fields': spec.get('expected_columns', []),
                      'constraints': task['constraints'],
                      'current_question': task['question'] if mode == 'hybrid' else None})
    return (
        f'Generate exactly {len(slots)} varied, concise English questions, one for each slot in order. '
        'Do NOT edit or add slots. Return exactly the same IDs. Each question MUST contain its target name. '
        'For MCP-backed slots, ONLY refer to fields and constraints given. '
        'No invented date/year, observation ID, telescope filter or specific proposal unless provided. '
        + ('Rephrase the existing question conservatively but improve variety.' if mode == 'hybrid'
           else 'Write a fresh natural question grounded in the given intent and fields.')
        + (' Research relevant source context using the web_search tool. Search is not proof of a valid MCP function.'
           if not use_mcp else ' MCP signatures were already discovered by the benchmark; do not request web research.')
        + '\nSLOTS JSON:\n' + json.dumps(slots, ensure_ascii=False, separators=(',', ':'))
    )


# Routing is derived from text in the question, not from hidden reference answers.
# The archive itself, however, was already selected before asking the model.
ARCHIVE_DISPLAY_NAMES = {
    'simbad': 'SIMBAD', 'mast': 'MAST', 'heasarc': 'HEASARC',
    'gaia': 'Gaia', 'vizier': 'VizieR',
}
_ARCHIVE_NAME_PATTERN = re.compile(r'\b(?:simbad|mast|heasarc|gaia|vizier)\b', re.I)


def _ensure_named_archive(question: str, task: dict[str, Any]) -> tuple[str, bool]:
    """Supply the prebound archive label when a model simply omitted it.

    This only edits question wording, never MCP tool/params, expected fields,
    constraints, reference answers, or validation status. Fail closed if the
    model explicitly names another archive: prefixing would be misleading.
    """
    module = task['module']
    named = {m.group(0).casefold() for m in _ARCHIVE_NAME_PATTERN.finditer(question)}
    if named - {module}:
        raise GenerationError(
            f'OpenAI question {task["id"]} names conflicting archive(s) '
            f'{", ".join(sorted(named - {module}))}; expected {module}'
        )
    if module in named:
        return question, False
    # Adding this neutral prefix is semantically transparent: the archive is
    # an already frozen, MCP-discovered query constraint for this task.
    return f'Using {ARCHIVE_DISPLAY_NAMES[module]}, {question[0].lower() + question[1:]}', True


def _guard_question(question: Any, task: dict[str, Any], *, use_mcp: bool) -> str:
    if not isinstance(question, str) or not 20 <= len(question) <= 450 or '\n' in question:
        raise GenerationError(f'Invalid question for {task["id"]}: must be 20..450 chars, single line')
    if not _target_in_question(task['target'], question):
        raise GenerationError(f'OpenAI question {task["id"]} omits target {task["target"]}')
    # Repair of a missing named archive belongs to the controlled authoring
    # boundary; this guard still rejects missing/ambiguous archive labels.
    found_archives = {m.group(0).casefold() for m in _ARCHIVE_NAME_PATTERN.finditer(question)}
    if found_archives != {task['module']}:
        raise GenerationError(f'OpenAI question {task["id"]} does not uniquely name archive {task["module"]}')
    if not question.strip().endswith('?'):
        raise GenerationError(f'OpenAI question {task["id"]} must be a question')
    if use_mcp:
        # Disallow new date constraints or numerical observing restrictions absent from input.
        digits = set(re.findall(r'\b(?:19|20)\d{2}\b', question))
        allowed = set(re.findall(r'\b(?:19|20)\d{2}\b', task['question']))
        if digits - allowed:
            raise GenerationError(f'OpenAI question {task["id"]} invented a year not in MCP reference constraints')
        q = question.casefold()
        # Prevent known mismatch: asking for a filter that was never included in the selected result.
        fields = ' '.join(task['answer_spec']['expected_columns']).casefold()
        for word, columns in [('filter',('filter',)), ('grating',('grating',)),
                              ('start time',('start_time','t_min','start')), ('proposal id',('proposal',))]:
            if word in q and not any(token in fields for token in columns):
                raise GenerationError(f'OpenAI question {task["id"]} asks about unsupported field {word}')
    return question.strip()



def _target_in_question(target: str, question: str) -> bool:
    """Match a target as a complete name, not as a substring (M1 != M101)."""
    pattern = r'(?<![\w])' + r'\s+'.join(re.escape(part) for part in target.split()) + r'(?![\w])'
    return bool(re.search(pattern, question, re.I))


def _prepare_authored_question(question: Any, task: dict[str, Any], *, use_mcp: bool) -> tuple[str, bool]:
    """Validate wording before it can be associated with an immutable task slot."""
    if not isinstance(question, str) or not 20 <= len(question) <= 450 or '\n' in question:
        raise GenerationError(f'Invalid question for {task["id"]}: must be 20..450 chars, single line')
    if not _target_in_question(task['target'], question):
        raise GenerationError(f'OpenAI question {task["id"]} omits target {task["target"]}')
    if not question.strip().endswith('?'):
        raise GenerationError(f'OpenAI question {task["id"]} must be a question')
    normalized, repaired = _ensure_named_archive(question.strip(), task)
    return _guard_question(normalized, task, use_mcp=use_mcp), repaired


def _resolve_batch_slots(found: list[Any], batch: list[dict[str, Any]], *, use_mcp: bool
                         ) -> list[tuple[dict[str, Any], dict[str, Any], str, bool]]:
    """Reconcile a model's *untrusted* slot labels with pre-bound scientific tasks.

    Exact IDs win only when their questions match their assigned constraints.
    Otherwise a unique perfect matching of validated target/archive question
    content is required. Never publish an ambiguous permutation or change an
    MCP reference call to accommodate generated text.
    """
    if len(found) != len(batch):
        raise GenerationError(f'OpenAI returned {len(found)} questions for {len(batch)} slots')
    if any(not isinstance(row, dict) for row in found):
        raise GenerationError('OpenAI returned non-object question rows')

    expected = {t['id']: i for i, t in enumerate(batch)}
    given_ids = [r.get('id') for r in found]
    exact_error: GenerationError | None = None
    if all(isinstance(v, str) for v in given_ids) and set(given_ids) == set(expected) and len(set(given_ids)) == len(batch):
        aligned = [found[given_ids.index(t['id'])] for t in batch]
        try:
            prepared = [_prepare_authored_question(r.get('question'), t, use_mcp=use_mcp)
                        for t, r in zip(batch, aligned)]
        except GenerationError as exc:
            exact_error = exc  # May be swapped questions; try unique scientific matching.
        else:
            return [(t, r, q, fix) for t, r, (q, fix) in zip(batch, aligned, prepared)]

    # Detect scientific compatibility independent of model-written IDs/order.
    compatible: list[list[tuple[int, str, bool]]] = []
    for row in found:
        options = []
        for slot, task in enumerate(batch):
            try:
                q, fixed = _prepare_authored_question(row.get('question'), task, use_mcp=use_mcp)
            except GenerationError:
                continue
            options.append((slot, q, fixed))
        compatible.append(options)
    if any(not choices for choices in compatible):
        if exact_error is not None:
            raise exact_error
        raise GenerationError('OpenAI task IDs changed/omitted and question target/archive cannot be safely assigned to frozen slots')

    # At most two solutions need to be discovered: ambiguity must fail closed.
    assignments: list[list[tuple[int, str, bool]]] = []
    def find_unique(row_index: int, selected: list[tuple[int, str, bool]], used: set[int]) -> None:
        if len(assignments) >= 2:
            return
        if row_index == len(found):
            assignments.append(list(selected))
            return
        for option in compatible[row_index]:
            if option[0] not in used:
                used.add(option[0]); selected.append(option)
                find_unique(row_index + 1, selected, used)
                selected.pop(); used.remove(option[0])
                if len(assignments) >= 2:
                    return
    find_unique(0, [], set())
    if len(assignments) != 1:
        raise GenerationError('OpenAI task IDs changed/omitted and target/archive matching is ambiguous or incomplete')
    result: list[Any] = [None] * len(batch)
    for row, (slot, question, fixed) in zip(found, assignments[0]):
        result[slot] = (batch[slot], row, question, fixed)
    return result

def _openai_client(factory: Callable[[], Any] | None) -> Any:
    if factory:
        return factory()
    if not os.environ.get('OPENAI_API_KEY'):
        raise GenerationError('OpenAI backend needs OPENAI_API_KEY; use --backend template for no API key')
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise GenerationError('Install the OpenAI SDK: uv run --with openai python -m benchmark generate ...') from exc
    return OpenAI()


def _create(client: Any, **kwargs: Any) -> Any:
    return client.responses.create(**kwargs)


async def generate_llm(url: str | None = None, *, count: int = 50, seed: int = 42,
                       modules: tuple[str, ...] = SUPPORTED_MODULES, timeout: float = 180,
                       uniqueness: str = 'archive-target', question_style: str = 'answer-oriented',
                       backend: str = 'openai', model: str = 'gpt-5.2',
                       use_instructions: bool = True, use_mcp: bool = True,
                       instructions_file: str | Path | None = None,
                       batch_size: int = 5, session_factory: Callable | None = None,
                       progress: Callable[[str], None] | None = None,
                       targets: tuple[SkyTarget, ...] | None = None,
                       openai_client_factory: Callable[[], Any] | None = None,
                       on_batch: Callable[[int, list[dict]], None] | None = None,
                       cached_batches: dict[int, list[dict]] | None = None,
                       ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if backend not in ('openai', 'hybrid'):
        raise GenerationError('LLM generator requires --backend openai or hybrid')
    modules = parse_modules(modules)
    if isinstance(batch_size, bool) or not 1 <= batch_size <= 10:
        raise GenerationError('--batch-size must be 1..10')
    if not isinstance(model, str) or not model.strip():
        raise GenerationError('--model must be nonempty')
    client = _openai_client(openai_client_factory)
    if use_mcp:
        tasks, summary = await generate(url, count=count, seed=seed, modules=modules,
                                        timeout=timeout, session_factory=session_factory,
                                        targets=targets, uniqueness=uniqueness,
                                        question_style=question_style)
    else:
        # Use local seed/method placeholders exclusively for the question-writing plan;
        # no artifact may falsely claim these placeholders are executable MCP calls.
        tasks = generate_candidates(_fixed_bindings(modules), count=count, seed=seed,
                                    modules=modules, targets=targets, uniqueness=uniqueness,
                                    question_style=question_style)
        summary = {'milestone': '0.6.4 — LLM_ASSISTED_SYNTHETIC_QUERY_GENERATION',
                   'benchmark_version': __version__, 'endpoint': None, 'seed': seed,
                   'count': len(tasks), 'modules': list(modules),
                   'by_module': dict(sorted(Counter(t['module'] for t in tasks).items())),
                   'validation_status': 'candidate_unvalidated', 'uniqueness_policy': uniqueness,
                   'question_style': question_style, 'archive_queries_executed': 0,
                   'expected_answers_verified': 0, 'status': 'PASS'}
    instructions = instruction_text(enabled=use_instructions, path=instructions_file)
    system = (BASE_SYSTEM if use_mcp else WEB_SYSTEM) + ('\n' + instructions if instructions else '')
    model_calls = web_calls = 0
    seen_questions: set[str] = set()
    archive_name_repairs = 0
    task_id_repairs = 0
    openai_retries = 0
    reused_batches = 0
    from .generation_checkpoint import slot_signature
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        batch_number = i // batch_size + 1
        cached = (cached_batches or {}).get(batch_number)
        if cached is not None:
            if len(cached) != len(batch):
                raise GenerationError(f'Resumed batch {batch_number} size mismatch')
            for task, saved in zip(batch, cached):
                if saved.get('signature') != slot_signature(task):
                    raise GenerationError(f'Resumed batch {batch_number} slot signature differs')
                authored = saved.get('task', {})
                if authored.get('id') != task['id'] or not isinstance(authored.get('question'), str):
                    raise GenerationError(f'Resumed batch {batch_number} lacks its validated question')
                question, _ = _prepare_authored_question(authored['question'], task, use_mcp=use_mcp)
                key = ' '.join(question.casefold().split())
                if key in seen_questions:
                    raise GenerationError('Duplicate question in resumed generation')
                seen_questions.add(key)
                task['question'] = authored['question']
                task['provenance'] = authored['provenance']
                task['execution_track'] = authored['execution_track']
            reused_batches += 1
            if progress:
                progress(f'OpenAI REUSED batch {batch_number} from durable journal ({len(batch)} questions)')
            continue
        opts: dict[str, Any] = {'model': model,
                                'input': [{'role': 'system', 'content': system},
                                          {'role': 'user', 'content': _slots_prompt(batch, mode=backend, use_mcp=use_mcp)}]}
        if not use_mcp:
            opts['tools'] = [{'type': 'web_search'}]
            opts['tool_choice'] = 'required'
        opts['timeout'] = timeout
        resolved = None
        for attempt in range(2):
            if progress is not None:
                message = f'OpenAI START batch {i // batch_size + 1}/{(len(tasks)+batch_size-1)//batch_size} ({len(batch)} questions)'
                progress(message if attempt == 0 else message + ' RETRY (unsafe/unresolved task IDs)')
            try:
                response = await asyncio.to_thread(_create, client, **opts)
            except Exception as exc:
                raise GenerationError(f'OpenAI generation request failed at batch {i // batch_size + 1}: {exc}') from exc
            model_calls += 1
            if progress is not None:
                progress(f'OpenAI DONE batch {i // batch_size + 1}/{(len(tasks)+batch_size-1)//batch_size}')
            uses = _tool_uses(response)
            web_calls += uses
            if not use_mcp and uses == 0:
                raise GenerationError('No-MCP mode requires a completed OpenAI web_search call; none observed')
            payload = _response_json(response)
            try:
                resolved = _resolve_batch_slots(payload['questions'], batch, use_mcp=use_mcp)
                break
            except GenerationError as exc:
                if attempt == 1:
                    raise GenerationError(f'OpenAI batch {i // batch_size + 1} could not be safely aligned after retry: {exc}') from exc
                if progress is not None:
                    progress(f'OpenAI batch {i // batch_size + 1} has unresolvable slot/question assignment; requesting one corrected batch')
                # Never rewrite bound MCP calls or accept a guess. Retry this
                # single batch with the immutable IDs and intended targets.
                opts['input'] = opts['input'] + [
                    {'role': 'user', 'content':
                        'Your last response could not be unambiguously matched to the supplied task slots. '
                        'Regenerate this entire batch. Include each exact ID once, and each question must name '
                        'the corresponding target and archive. Do not invent new constraints. '
                        'Previous error: ' + str(exc)}]
                openai_retries += 1
        assert resolved is not None
        for task, row, question, repaired in resolved:
            original_id = row.get('id')
            id_repaired = original_id != task['id']
            if id_repaired:
                task_id_repairs += 1
                if progress is not None:
                    progress(f'OpenAI normalized task ID {original_id!r} -> {task["id"]} ({task["module"]}; target={task["target"]})')
            raw_question = row['question']
            if repaired:
                archive_name_repairs += 1
                if progress is not None:
                    progress(f'OpenAI normalized missing archive name for {task["id"]} ({task["module"]})')
            key = ' '.join(question.casefold().split())
            if key in seen_questions:
                raise GenerationError('OpenAI generated a duplicate question; change seed/model/batch')
            seen_questions.add(key)
            task['question'] = question
            provenance = task['provenance']
            provenance.update({'generation_backend': backend, 'openai_model': model,
                               'instructions_used': use_instructions,
                               'instructions_version': (INSTRUCTIONS_VERSION if instructions_file is None else 'custom_file') if use_instructions else None,
                               'instructions_sha256': hashlib.sha256(instructions.encode()).hexdigest()
                               if use_instructions else None,
                               'mcp_enabled': use_mcp,
                               'archive_name_repaired': repaired,
                               'task_id_repaired': id_repaired,
                               'original_llm_task_id': original_id if id_repaired else None,
                               'original_llm_question': raw_question.strip() if repaired else None,
                               'search_tool': 'none' if use_mcp else 'openai_web_search',
                               'model_generation_reproducibility': 'best_effort_nondeterministic'})
            if not use_mcp:
                urls = row.get('source_urls', [])
                if not isinstance(urls, list) or any(not _valid_url(u) for u in urls):
                    raise GenerationError(f'OpenAI returned invalid source URLs for {task["id"]}')
                observed = _observed_urls(response)
                task['research_sources'] = sorted(set(urls) & observed)
                task['source_verification'] = 'provider_reported_search_sources_only' if observed else 'no_provider_source_metadata'
                task['suggested_answer_fields_unverified'] = list(task['answer_spec']['expected_columns'])
                task['answer_spec']['expected_columns'] = []
                task['reference_call'] = None
                task['validation_status'] = 'research_candidate_unvalidated_no_mcp'
                task['execution_track'] = 'openai_web_search_research'
                task['answer_spec']['expected_answer_status'] = 'unverified_web_research'
            else:
                task['execution_track'] = 'astroquery_mcp'
        if on_batch is not None:
            on_batch(batch_number, batch)
    check = analyze_candidates(tasks)
    if any(check['counts'].values()):
        raise GenerationError('Generated questions fail diversity audit')
    summary.update({'milestone': '0.6.4.2 — OPENAI_TASK_ID_RECONCILIATION',
                    'benchmark_version': __version__, 'status': 'PASS',
                    'generation_backend': backend, 'model': model, 'use_instructions': use_instructions,
                    'use_mcp': use_mcp, 'instructions_sha256': hashlib.sha256(instructions.encode()).hexdigest() if instructions else None, 'research_tool': 'none' if use_mcp else 'openai_web_search',
                    'openai_requests': model_calls, 'web_search_calls': web_calls,
                    'archive_name_repairs': archive_name_repairs,
                    'task_id_repairs': task_id_repairs, 'openai_batch_retries': openai_retries,
                    'resumed_openai_batches': reused_batches,
                    'openai_requests_this_invocation': model_calls,
                    'scientific_truth_verified': False,
                    'expected_answers_verified': 0,
                    'archive_queries_executed': 0,
                    'mcp_calls_executable': use_mcp,
                    'distinct_archive_target_pairs': check['distinct_archive_target_pairs'],
                    'by_intent': check['by_intent'],
                    'notes': ['The model writes questions, never a gold answer.',
                              'Missing single-archive names may be inserted deterministically; each repair is audited.',
                              'LLM task IDs are never authoritative; safe ID corrections use unique target/archive matches and are audited.',
                              'OpenAI results are not guaranteed byte-reproducible even with fixed seed.',
                              'No-MCP tasks require a future adapter/validation track; benchmark validate uses MCP.']})
    return tasks, summary
