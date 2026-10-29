"""Offline integrity checks for the frozen published AstroAKD-Bench study."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'examples' / 'astroakd_100_v2'


def test_public_example_question_and_reference_coverage():
    with (DATA / 'astroakd_100_v2_questions_and_references.csv').open(newline='') as fh:
        records = list(csv.DictReader(fh))
    assert len(records) == 100
    assert len({r['task_id'] for r in records}) == 100
    assert sum(bool(r['reference_answer_values_json'].strip()) for r in records) == 92
    assert sum(not r['reference_answer_values_json'].strip() for r in records) == 8
    with (DATA / 'astroakd_100_v2.csv').open(newline='') as fh:
        original = list(csv.DictReader(fh))
    assert len(original) == 100
    assert {r['task_id'] for r in records} == {r['task_id'] for r in original}


def test_public_example_scoring_counts_and_checksums():
    summary = json.loads((DATA / 'automated_scoring_summary.json').read_text())
    assert summary['evaluable_questions'] == 92
    assert summary['excluded_questions'] == 8
    assert [summary['arms'][arm]['correct'] for arm in ('mcp_only','mcp_instruction','web_only')] == [87,88,13]
    manifest = json.loads((DATA / 'MANIFEST.json').read_text())
    assert manifest['file_count_excluding_manifest'] == len(manifest['files'])
    for name, meta in manifest['files'].items():
        content = (DATA / name).read_bytes()
        assert len(content) == meta['bytes'], name
        assert hashlib.sha256(content).hexdigest() == meta['sha256'], name


def test_docs_example_figures_match_published_originals():
    for figure in ('match_rate.png', 'accuracy_by_question_type.png','mean_runtime.png'):
        original = (DATA / 'figures' / figure).read_bytes()
        mirror = (ROOT / 'docs/_static/examples' / figure).read_bytes()
        assert original == mirror, figure
    assert '(examples/README.md)' in (ROOT / 'README.md').read_text()
    assert '(benchmark/example_results.md)' in (ROOT / 'docs/index.md').read_text()
    assert 'examples/**' in (ROOT / '.github/workflows/publish-docs.yml').read_text()
