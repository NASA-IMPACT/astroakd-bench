"""Safe one-time migration from benchmark/datasets to root datasets/.

Use from the AstroAKD-Bench repository root. Rename leaves bytes and their
SHA256 fingerprints intact. Never overwrite an existing destination.
"""
from pathlib import Path
import hashlib
import sys

OLD = Path('benchmark/datasets')
NEW = Path('datasets')
EXPECTED = {
    'generated/synthetic_queries.jsonl': 'e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9',
    'validated/reference_answers.jsonl': '1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87',
}

def main() -> int:
    if OLD.exists() and NEW.exists():
        print('Refusing to merge: both benchmark/datasets/ and datasets/ exist. Resolve manually.', file=sys.stderr)
        return 2
    if not OLD.exists():
        print('No old benchmark/datasets/ directory; root layout already in use or files are absent.')
        return 0
    checks = {}
    for name, expected in EXPECTED.items():
        file = OLD / name
        if file.is_file():
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if digest != expected:
                print(f'Refusing to move: accepted fingerprint changed for {name}', file=sys.stderr)
                return 2
            checks[name] = digest
    OLD.rename(NEW)
    print(f'Moved {OLD} -> {NEW}; accepted SHA256 preserved for {len(checks)} files')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
