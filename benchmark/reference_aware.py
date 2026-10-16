"""Live, agent-independent feasibility gate for synthetic question *slots*.

Runs BEFORE LLM question authoring.  Only structurally complete, compact,
nonempty archive observations with the required field are admitted.  A probe
is not a scientific gold answer, and collection reruns the call independently.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
import re
from pathlib import Path
import os
import tempfile
from typing import Any, Callable

from .client import AstroqueryMCPClient
from .generator import (
    GenerationError, discover_bindings, generate_candidates, parse_modules,
)
from .seeds import TARGETS, SkyTarget
from .validator import evaluate_response

# Extra, approximately positioned objects are candidate search centers, never
# treated as independently verified astrometry or archive reference answers.
ADDITIONAL_TARGETS = (
    SkyTarget('NGC 4051', 180.790, 44.531),
    SkyTarget('NGC 7469', 345.816, 8.874),
    SkyTarget('NGC 3516', 166.697, 72.568),
    SkyTarget('NGC 1365', 53.401, -36.141),
    SkyTarget('NGC 2992', 146.426, -14.326),
    SkyTarget('NGC 3227', 155.877, 19.865),
    SkyTarget('NGC 4388', 186.445, 12.662),
    SkyTarget('NGC 4593', 189.914, -5.344),
    SkyTarget('Ark 120', 79.047, -0.150),
    SkyTarget('Mrk 335', 1.582, 20.203),
    SkyTarget('Mrk 509', 311.040, -10.724),
    SkyTarget('IC 4329A', 207.330, -30.310),
    SkyTarget('NGC 6302', 258.435, -37.104),
    SkyTarget('NGC 2392', 112.294, 20.911),
    SkyTarget('NGC 6826', 295.201, 50.526),
    SkyTarget('NGC 1535', 63.154, -12.739),
    SkyTarget('NGC 2440', 116.211, -18.208),
    SkyTarget('M13', 250.423, 36.461),
    SkyTarget('M3', 205.548, 28.377),
    SkyTarget('M5', 229.639, 2.081),
    SkyTarget('M15', 322.493, 12.167),
    SkyTarget('M92', 259.281, 43.136),
    SkyTarget('M4', 245.897, -26.526),
    SkyTarget('NGC 6397', 265.175, -53.674),
    SkyTarget('M22', 279.099, -23.905),
    SkyTarget('M67', 132.825, 11.816),
    SkyTarget('Vega', 279.2347, 38.7837),
    SkyTarget('Sirius', 101.2872, -16.7161),
    SkyTarget('Betelgeuse', 88.7929, 7.4071),
    SkyTarget('Rigel', 78.6345, -8.2016),
    SkyTarget('Polaris', 37.9546, 89.2641),
    SkyTarget('Procyon', 114.8255, 5.2250),
    SkyTarget('Deneb', 310.3579, 45.2803),
    SkyTarget('Altair', 297.6958, 8.8683),
    SkyTarget('Arcturus', 213.9153, 19.1824),
    SkyTarget('Spica', 201.2983, -11.1614),
    SkyTarget('Antares', 247.3519, -26.4320),
    SkyTarget('Capella', 79.1723, 45.9979),
    SkyTarget('Fomalhaut', 344.4127, -29.6222),
    SkyTarget('Regulus', 152.0929, 11.9672),
    SkyTarget('NGC 6543', 269.639, 66.633),  # deduplicated against base
)
REFERENCE_AWARE_TARGETS = TARGETS + tuple(
    target for target in ADDITIONAL_TARGETS
    if target.name.casefold() not in {t.name.casefold() for t in TARGETS}
)
# Bounded search sizes: smaller is not automatically better; reject empty
# results and try an alternative radius rather than creating an empty oracle.
RADII = {
    'gaia': (.1, .2, .05, .5, 1.0),
    'mast': (.2, .1, .5, 1.0),
    'heasarc': (.5, .2, 1.0, 2.0),
    'vizier': (.2, .1, .5, 1.0),
}


def evaluate_feasibility(task: dict[str, Any], response: Any, *, max_rows: int = 20,
                         max_bytes: int = 65536) -> tuple[bool, str, dict[str, Any]]:
    """Conservatively require the requested answer column in complete data."""
    try:
        blob = json.dumps(response, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError):
        return False, 'unserializable_response', {}
    if len(blob) > max_bytes:
        return False, 'oversized_response', {'bytes': len(blob)}
    check = evaluate_response(task, response)
    if check.get('disposition') != 'accepted_nonempty':
        return False, str(check.get('disposition', 'invalid_response')), {}
    c = check.get('checks', {})
    if c.get('truncated') or c.get('reported_total_rows', 0) > c.get('returned_rows', 0):
        return False, 'truncated_reference', {}
    n = c.get('returned_rows', 0)
    if n < 1 or n > max_rows:
        return False, 'too_many_rows', {'rows': n}
    if c.get('table_count', 0) != 1:
        return False, 'multiple_tables', {}
    from .validator import _tables
    tables, _ = _tables(response['result'])
    data = tables[0]['data']
    fields = task.get('answer_spec', {}).get('expected_columns', [])
    if not fields:
        return False, 'missing_answer_spec', {}
    available = {str(k).casefold() for row in data for k in row}
    missing = [field for field in fields if field.casefold() not in available]
    if missing:
        return False, 'missing_expected_field', {'fields': missing}
    # All-null fields are not a usable automatic reference answer.
    for field in fields:
        values = [v for row in data for k, v in row.items() if str(k).casefold() == field.casefold()]
        if len(values) != len(data) or any(v is None or v == '' or str(v).strip().lower() in ('nan', '--', 'null', 'none', 'masked') for v in values):
            return False, 'null_answer_field', {'field': field}
    return True, 'complete_bounded_reference', {
        'rows': n, 'bytes': len(blob), 'response_sha256': hashlib.sha256(blob).hexdigest()
    }


def _resize(task: dict[str, Any], radius: float) -> dict[str, Any]:
    item = copy.deepcopy(task)
    params = item['reference_call']['arguments']['params']
    module = item['module']
    alias = 'coordinates' if module in ('mast', 'vizier') else 'position' if module == 'heasarc' else 'coordinate'
    if alias not in params or 'radius' not in params:
        raise GenerationError(f'Reference-aware query cannot safely resize {module} template')
    params['radius'] = {'value': radius, 'unit': 'arcmin'}
    item['constraints']['radius'] = {'value': radius, 'unit': 'arcmin'}
    # Only substitute the radius in the frozen template, not arbitrary GPT text.
    item['question'] = re.sub(r'within\s+[0-9.]+\s+arcmin',
                              f'within {radius:g} arcmin', item['question'], count=1)
    return item


def _checkpoint_hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _save_checkpoint(path: Path, record: dict[str, Any]) -> None:
    """Persist each completed probe atomically; never store raw archive data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = copy.deepcopy(record)
    payload['sha256'] = _checkpoint_hash(record)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8',
            delete=False, prefix='.feasibility-progress-', suffix='.tmp') as file:
        temp = Path(file.name)
        json.dump(payload, file, ensure_ascii=False, sort_keys=True, allow_nan=False)
        file.write('\n'); file.flush(); os.fsync(file.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _load_checkpoint(path: Path, configuration: dict[str, Any]) -> dict[str, Any]:
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = record.pop('sha256', None)
    saved = record.get('configuration', {})
    if expected != _checkpoint_hash(record) or not isinstance(saved, dict):
        raise GenerationError('Reference-aware progress checkpoint checksum is invalid')
    # Only an increased probe ceiling may be changed on resume. This cannot
    # invalidate an already accepted archive reference or change slot order.
    if (any(saved.get(k) != v for k, v in configuration.items() if k != 'max_probes')
            or int(configuration['max_probes']) < int(saved.get('max_probes', 0))):
        raise GenerationError('Reference-aware progress checkpoint settings differ; '
            'only an increase in --max-feasibility-probes is allowed when resuming')
    record['configuration'] = configuration
    if not isinstance(record.get('selected'), list) or not isinstance(record.get('outcomes'), dict):
        raise GenerationError('Malformed reference-aware progress checkpoint')
    return record


def _probe_key(module: str, target: str, radius: float | None) -> str:
    return json.dumps([module, target.casefold(), radius], separators=(',', ':'))


async def select_reference_aware(url: str | None, *, count: int, seed: int,
                                  modules: tuple[str, ...], timeout: float,
                                  targets: tuple[SkyTarget, ...] | None = None,
                                  max_rows: int = 20, max_bytes: int = 65536,
                                  max_probes: int = 500, progress: Callable | None = None,
                                  session_factory: Callable | None = None,
                                  checkpoint_path: Path | None = None,
                                  resume_checkpoint: bool = False,
                                  min_coordinate_tasks: int = 0):
    """Choose compact complete references with durable progress and module fallback.

    The intended round-robin module is preferred.  When it has no feasible
    unused archive-target pairs, another eligible module fills the slot;
    this changes the recorded *actual* module counts, never the reference
    completeness requirements or task IDs.  No GPT calls occur here.
    """
    modules = parse_modules(modules)
    targets = tuple(targets or REFERENCE_AWARE_TARGETS)
    if min_coordinate_tasks < 0 or min_coordinate_tasks > count:
        raise GenerationError('Invalid number of required coordinate questions')
    if min_coordinate_tasks and not any(m != 'simbad' for m in modules):
        raise GenerationError('No coordinate-capable reference-aware archive available')
    if count > len(targets) * len(modules):
        raise GenerationError('Insufficient unique archive-target pairs for reference-aware mix')
    from .mcp_config import resolve_mcp_url
    configuration = {
        'policy': '0.6.7.11.10', 'count': count, 'seed': seed,
        'modules': list(modules),
        'targets': [[t.name, t.ra_deg, t.dec_deg] for t in targets],
        'max_rows': max_rows, 'max_bytes': max_bytes,
        'max_probes': max_probes, 'endpoint': resolve_mcp_url(url),
        'min_coordinate_tasks': min_coordinate_tasks,
    }
    checkpoint = Path(checkpoint_path) if checkpoint_path is not None else None
    if resume_checkpoint and checkpoint is None:
        raise GenerationError('Reference-aware resume requires a checkpoint path')
    if resume_checkpoint:
        if not checkpoint.is_file():
            raise GenerationError(f'Reference-aware progress checkpoint not found: {checkpoint}')
        state = _load_checkpoint(checkpoint, configuration)
        if checkpoint is not None:
            _save_checkpoint(checkpoint, state)
        if progress:
            progress(f'Reference-aware RESUME {len(state["selected"])}/{count} approved slots; '
                     f'{len(state["outcomes"])} probes cached')
    else:
        if checkpoint is not None and checkpoint.exists():
            raise GenerationError('Reference-aware progress already exists; use --resume '
                                  'or choose a new dataset name')
        state = {'configuration': configuration, 'selected': [], 'outcomes': {}}
        if checkpoint is not None:
            _save_checkpoint(checkpoint, state)

    async with AstroqueryMCPClient(url, timeout=timeout, session_factory=session_factory) as client:
        bindings = await discover_bindings(client, modules)
        pool = generate_candidates(bindings, count=len(targets) * len(modules),
                                   seed=seed, modules=modules, targets=targets,
                                   question_style='answer-oriented')
        queues = {module: [item for item in pool if item['module'] == module] for module in modules}
        selected = list(state['selected'])
        if len(selected) > count:
            raise GenerationError('Reference-aware checkpoint has too many selected tasks')
        seen = {(item['module'], item['target'].casefold()) for item in selected}
        reasons = Counter(outcome['reason'] for outcome in state['outcomes'].values()
                          if not outcome['ok'])
        fallbacks = 0
        for index in range(len(selected), count):
            preferred = modules[index % len(modules)]
            # Preserve the familiar distribution when possible; use the least-
            # represented alternative first when the preferred archive is exhausted.
            counts = Counter(t['module'] for t in selected)
            alternatives = sorted((m for m in modules if m != preferred),
                                  key=lambda m: (counts[m], modules.index(m)))
            chosen = None
            for module in (preferred, *alternatives):
                coordinate_so_far = sum(t['module'] != 'simbad' for t in selected)
                remaining_after_this = count - (index + 1)
                if module == 'simbad' and coordinate_so_far + remaining_after_this < min_coordinate_tasks:
                    continue
                for source in queues[module]:
                    key = (module, source['target'].casefold())
                    if key in seen:
                        continue
                    # In a cone search, enlarging a radius cannot repair a
                    # truncated/oversized result at a smaller radius.
                    radii = tuple(sorted(RADII.get(module, (None,)),
                                          key=lambda r: -1.0 if r is None else r))
                    for radius in radii:
                        candidate = _resize(source, radius) if radius is not None else copy.deepcopy(source)
                        probe_key = _probe_key(module, source['target'], radius)
                        cached = state['outcomes'].get(probe_key)
                        if cached is None:
                            if len(state['outcomes']) >= max_probes:
                                raise GenerationError(
                                    f'Reference-aware probe budget exhausted after {len(state["outcomes"])} '
                                    f'calls; accepted {len(selected)}/{count}; rejected {dict(reasons)}. '
                                    f'Progress preserved at {checkpoint}. Retry with --resume '
                                    'using the same settings or start a new named dataset '
                                    'with a larger --max-feasibility-probes.')
                            try:
                                response = await client.call(candidate['reference_call']['tool'],
                                                             candidate['reference_call']['arguments'])
                                ok, reason, detail = evaluate_feasibility(candidate, response,
                                                   max_rows=max_rows, max_bytes=max_bytes)
                            except Exception as exc:
                                ok, reason, detail = False, 'mcp_probe_error', {
                                    'error_type': type(exc).__name__}
                            cached = {'ok': ok, 'reason': reason, 'detail': detail}
                            state['outcomes'][probe_key] = cached
                            if not ok:
                                reasons[reason] += 1
                            if checkpoint is not None:
                                _save_checkpoint(checkpoint, state)
                        if cached['ok']:
                            chosen = candidate
                            chosen.setdefault('provenance', {})['reference_aware_seed_catalog'] = '0.6.7.11.10'
                            chosen['provenance']['reference_aware'] = {
                                'policy': '0.6.7.11.10', 'status': 'PRECHECK_ACCEPTED',
                                'max_rows': max_rows, 'max_bytes': max_bytes,
                                **cached['detail'],
                            }
                            break
                        if radius is not None and cached['reason'] in (
                                'truncated_reference', 'oversized_response', 'too_many_rows'):
                            # No larger sky cone can have fewer matches. Do not
                            # waste requests probing larger radii for this target.
                            break
                    if chosen is not None:
                        break
                if chosen is not None:
                    if module != preferred:
                        fallbacks += 1
                        if progress:
                            progress(f'Reference-aware FALLBACK {index+1}/{count}: '
                                     f'{preferred} unavailable, using {module}')
                    break
            if chosen is None:
                raise GenerationError(f'Could not fill reference-aware slot {index+1}/{count}; '
                    f'accepted={len(selected)}, probes={len(state["outcomes"])}, '
                    f'rejected={dict(reasons)}. Progress saved to {checkpoint}; '
                    'retry with --resume after addressing archive capacity, or '
                    'choose a smaller mix. No GPT question batches were requested.')
            seen.add((chosen['module'], chosen['target'].casefold()))
            chosen['id'] = f'ASTROAKD-020-{index+1:05d}'
            chosen['provenance']['generation_index'] = index + 1
            selected.append(chosen)
            state['selected'] = selected
            if checkpoint is not None:
                _save_checkpoint(checkpoint, state)
            if progress:
                progress(f'Reference-aware ACCEPT {index+1}/{count} '
                         f'{chosen["module"]} {chosen["target"]} '
                         f'({chosen["provenance"]["reference_aware"]["rows"]} rows; '
                         f'{len(state["outcomes"])} probes)')
    probes = len(state['outcomes'])
    if sum(t['module'] != 'simbad' for t in selected) < min_coordinate_tasks:
        raise GenerationError('Reference-aware selection cannot satisfy coordinate-driven mix')
    summary = {
        'milestone': '0.6.7.11.10 - DURABLE_REFERENCE_AWARE_SELECTION',
        'benchmark_version': selected[0]['benchmark_version'],
        'seed': seed, 'count': count, 'modules': list(modules),
        'by_module': dict(sorted(Counter(t['module'] for t in selected).items())),
        'discovered_methods': {k: v.method for k, v in bindings.items()},
        'signature_sources': {k: v.signature_source for k, v in bindings.items()},
        'discovered_schema_sha256': selected[0]['provenance']['discovered_schema_sha256'],
        'validation_status': 'reference_prechecked_not_gold',
        'uniqueness_policy': 'archive-target', 'question_style': 'answer-oriented',
        'distinct_archive_target_pairs': count,
        'distinct_targets': len({t['target'].casefold() for t in selected}),
        'by_intent': dict(sorted(Counter(t['intent'] for t in selected).items())),
        'expected_answers_verified': 0, 'status': 'PASS',
        'reference_aware_selection': {
            'accepted': count, 'probes': probes,
            'rejections_by_reason': dict(sorted(reasons.items())),
            'fallback_slots': sum(t['module'] != modules[i % len(modules)]
                                  for i, t in enumerate(selected)),
            'max_rows': max_rows, 'max_bytes': max_bytes,
            'note': 'Precheck is structural; references are independently recollected after publication.'
        },
        'archive_queries_executed': probes,
    }
    return selected, summary


def save_feasibility_plan(path: Path, *, configuration: dict[str, Any],
                          tasks: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """Atomically persist approved slots before any GPT authoring begins."""
    path = Path(path)
    record = {'configuration': configuration, 'tasks': tasks, 'summary': summary}
    record['sha256'] = hashlib.sha256(json.dumps(record, sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8',
                                     delete=False, prefix='.feasibility-', suffix='.tmp') as file:
        temp = Path(file.name)
        json.dump(record, file, ensure_ascii=False, sort_keys=True, allow_nan=False)
        file.write('\n'); file.flush(); os.fsync(file.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_feasibility_plan(path: Path, *, configuration: dict[str, Any]):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    checksum = data.pop('sha256', None)
    actual = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if checksum != actual or data.get('configuration') != configuration:
        raise GenerationError('Saved reference-aware selection checksum or settings changed; '
                              'do not reuse altered benchmark candidate slots')
    tasks, summary = data['tasks'], data['summary']
    if not isinstance(tasks, list) or len(tasks) != configuration['count']:
        raise GenerationError('Saved reference-aware selection contains wrong task count')
    return tasks, summary
