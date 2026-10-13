# AstroAKD-Bench 0.5.1 — PRETTY_SCORE_EXPORT_CLOSURE

## Scope

This is a formatting/export maintenance release over accepted 0.5.0 source. It adds an independent, indented **saved JSON array** of per-task scoring results via `evaluate --pretty-output PATH.json`. It never reformats `.jsonl` in place. AstroAKD-Bench is separate from NASA IMPACT's Astroquery MCP server.

## Offline acceptance

- 100 tests passed, 1 optional live-server test skipped (101 total).
- Historical 0.4.1 OpenAI pilot evaluated: 5 tasks, 3 PASS, 2 REVIEW, mean technical score 94/100.
- `--pretty-output` JSON array parsed successfully and exactly equals the compact JSONL records, task by task.
- File-path collision, wrong `.jsonl` pretty-output extension, and overwrite protection were exercised, plus a subprocess CLI test.
- Candidate dataset SHA-256: `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9` (unchanged).
- Reference dataset SHA-256: `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87` (unchanged).

Offline status: **PASS**. No OpenAI API or live archives used. Real laptop qualification: **PENDING**.

## Host qualification command

```bash
uv run python -m benchmark evaluate \
  --strict-accepted-020 \
  --runs datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --output datasets/evaluation/openai_041_scores_recheck.jsonl \
  --report datasets/evaluation/openai_041_report_recheck.json \
  --csv datasets/evaluation/openai_041_scores_recheck.csv \
  --pretty-output datasets/evaluation/openai_041_scores_recheck_pretty.json \
  --json-format pretty
```

Use new destination names or `--replace` intentionally when files already exist.

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

Scientific answer accuracy remains unverified; this release changes only score export formatting, not scoring weights, evidence, or conclusions.
