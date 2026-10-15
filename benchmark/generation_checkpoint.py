"""Durable, auditable mixed-generation progress journals.

Only fully validated question batches and authored literature steps are saved.
A partial file is never a published benchmark dataset or scientific gold.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .generator import GenerationError


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def slot_signature(task: dict) -> str:
    """Fingerprint only slot-defining data, never an LLM's authored question."""
    return _digest({k: task.get(k) for k in (
        'id', 'module', 'target', 'category', 'intent', 'constraints',
        'reference_call', 'answer_spec')})


class GenerationJournal:
    def __init__(self, path: Path, partial: Path, configuration: dict[str, Any]):
        self.path, self.partial = Path(path), Path(partial)
        self.config_hash = _digest(configuration)
        self.batches: dict[int, list[dict]] = {}
        self.literature: dict[int, dict] = {}

    def load(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(f'No generation journal to resume: {self.path}')
        rows = self.path.read_text(encoding='utf-8').splitlines()
        if not rows:
            raise GenerationError('Generation journal is empty')
        for line_number, line in enumerate(rows, 1):
            try:
                entry = json.loads(line)
                checksum = entry.pop('sha256')
                if not isinstance(checksum, str) or _digest(entry) != checksum:
                    raise ValueError('checksum mismatch')
                if entry['config_sha256'] != self.config_hash:
                    raise GenerationError('Generation journal configuration differs: use the original '
                        '--name, --count, --seed, --model, --mix, --modules, --batch-size, '
                        'ADS requirement, and MCP endpoint')
                kind = entry['kind']
                if line_number == 1:
                    if kind != 'header':
                        raise ValueError('missing journal header')
                elif kind == 'batch':
                    index = entry['index']
                    if index != len(self.batches) + 1 or not isinstance(entry['tasks'], list):
                        raise ValueError('out-of-sequence question batch')
                    self.batches[index] = entry['tasks']
                elif kind == 'literature':
                    index = entry['index']
                    if index != len(self.literature) + 1 or not isinstance(entry['task'], dict):
                        raise ValueError('out-of-sequence literature task')
                    self.literature[index] = entry['task']
                else:
                    raise ValueError('unknown journal event')
            except GenerationError:
                raise
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise GenerationError(f'Generation journal corrupted at line {line_number}; '
                                      'preserve this file for recovery and inspect its checksums') from exc
        self._save_partial()

    def start(self, *, replace: bool = False) -> None:
        if self.path.exists() and not replace:
            raise FileExistsError(f'Incomplete generation checkpoint exists: {self.path}; '
                                  'use --resume to reuse paid GPT batches')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if replace:
            self.batches.clear(); self.literature.clear()
        # Defer journal creation until the first *successful* GPT batch. If
        # ADS preflight or MCP discovery fails, no false "saved work" exists.
        if replace:
            self.path.unlink(missing_ok=True)
        if self.partial.exists():
            self.partial.unlink()

    def _append(self, payload: dict[str, Any]) -> None:
        if not self.path.exists():
            header = {'kind': 'header', 'config_sha256': self.config_hash,
                      'status': 'PARTIAL_GENERATION_NOT_A_BENCHMARK_DATASET'}
            with self.path.open('w', encoding='utf-8') as out:
                out.write(_canonical(dict(header, sha256=_digest(header)))+'\n')
                out.flush(); os.fsync(out.fileno())
        entry = dict(payload, config_sha256=self.config_hash)
        line = _canonical(dict(entry, sha256=_digest(entry)))+'\n'
        with self.path.open('a', encoding='utf-8') as out:
            out.write(line)
            out.flush(); os.fsync(out.fileno())

    def _save_partial(self) -> None:
        """Atomically publish inspectable *unfinalized* authored questions."""
        rows = [t['task'] for batch in self.batches.values() for t in batch]
        rows += list(self.literature.values())
        if not rows:
            return
        self.partial.parent.mkdir(parents=True, exist_ok=True)
        staging = self.partial.with_name(self.partial.name + '.tmp')
        with staging.open('w', encoding='utf-8') as out:
            for value in rows:
                record = dict(value)
                record['generation_progress_status'] = 'PARTIAL_NOT_VALIDATED_NOT_GOLD'
                out.write(_canonical(record)+'\n')
            out.flush(); os.fsync(out.fileno())
        os.replace(staging, self.partial)

    def save_batch(self, index: int, batch: list[dict]) -> None:
        if index != len(self.batches)+1:
            raise GenerationError(f'Nonsequential generation checkpoint batch {index}')
        snapshots = [{'signature': slot_signature(task), 'task': task} for task in batch]
        self._append({'kind': 'batch', 'index': index, 'tasks': snapshots})
        self.batches[index] = snapshots
        self._save_partial()

    def save_literature(self, index: int, record: dict) -> None:
        if index != len(self.literature)+1:
            raise GenerationError(f'Nonsequential literature checkpoint {index}')
        self._append({'kind': 'literature', 'index': index, 'task': record})
        self.literature[index] = record
        self._save_partial()

    def finish(self) -> None:
        self.path.unlink(missing_ok=True)
        self.partial.unlink(missing_ok=True)
