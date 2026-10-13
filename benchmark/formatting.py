"""Machine-stable JSONL and opt-in readable JSON rendering.

Never pretty-print a .jsonl stream: a record must occupy exactly one line.
The JSON formatter is intentionally presentation-only, not part of the frozen
candidate/reference SHA-256 contract.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

FORMATS = ('compact', 'pretty')


def json_text(value: Any, style: str = 'compact') -> str:
    if style not in FORMATS:
        raise ValueError(f'Unknown JSON format: {style}')
    if style == 'pretty':
        return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def inspect_file(path: Path, limit: int = 3) -> dict[str, Any]:
    """Bounded JSON/JSONL inspection without modifying the source."""
    if not path.is_file():
        raise ValueError(f'JSON input not found: {path}')
    if not 1 <= limit <= 100:
        raise ValueError('--limit must be 1..100')
    if path.suffix == '.jsonl':
        records = []
        total = 0
        with path.open(encoding='utf-8') as fp:
            for line in fp:
                if not line.strip():
                    continue
                total += 1
                if len(records) < limit:
                    records.append(json.loads(line))
        return {'source': str(path), 'format': 'jsonl', 'records_total': total,
                'records_shown': len(records), 'records': records}
    if path.suffix != '.json':
        raise ValueError('Inspect supports .json and .jsonl sources only')
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('JSON input larger than 64 MiB; use a bounded JSONL view')
    return {'source': str(path), 'format': 'json',
            'data': json.loads(path.read_text(encoding='utf-8'))}
