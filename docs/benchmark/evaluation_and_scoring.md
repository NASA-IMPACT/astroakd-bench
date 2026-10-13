# AstroAKD-Bench 0.5.0: deterministic evaluation and readable JSON

0.5.0 scores **saved** MCP agent traces against the accepted candidate and reference datasets. No OpenAI API key or running MCP server is needed for this stage. Evaluation reads the full reference set but sends none of it to the agent.

```bash
uv run python -m benchmark evaluate \
  --strict-accepted-020 \
  --runs datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --output datasets/evaluation/openai_041_scores_recheck.jsonl \
  --report datasets/evaluation/openai_041_report_recheck.json \
  --csv datasets/evaluation/openai_041_scores_recheck.csv \
  --json-format pretty
```

## Observable components of the 100-point evidence score

| Component | Weight | Deterministic checks |
| --- | ---: | --- |
| Archive selection | 20 | Whether a traced `astroquery_execute` targeted the reference archive |
| Function selection | 15 | Whether the traced operation matches the validated reference method |
| Parameter correctness | 25 | Object/catalog, coordinate and radius semantics; optional default `ICRS` frame and numeric tolerance |
| Successful execution | 15 | The actual tool trace records both transport success and MCP `success=true` |
| Reference result agreement | 15 | Returned/total row counts and empty/nonempty status agree with the frozen reference; otherwise review |
| Limited answer claim | 10 | Conservatively parse a few explicit numeric result-count claims or SIMBAD RA/Dec values; abstain for arbitrary prose |

**Interpretation**: mean score measures reproducible technical evidence, *not* general astronomical-answer accuracy. `technical_gate` can be PASS, REVIEW or FAIL (or HARNESS_ONLY for `echo`). `scientific_answer_gate` is always `INDEPENDENT_REVIEW_REQUIRED`; do not treat this as a claim that the model's scientific interpretation is accurate.

If an upstream archive's row count changes, report `ARCHIVE_DRIFT_OR_MISMATCH`, not a categorical hallucination verdict. Truncated trace output yields `INDETERMINATE_TRUNCATED`. A legitimate empty HEASARC result is correctly distinguished from a failed query. An answer count claim is checked only when a stable reference/live count can be established. Unknown or unsupported assertions are **not automatically scored as factual**.

## JSON formatting

`--json-format compact` is the default, optimized for pipelines. `--json-format pretty` renders human-readable CLI JSON and `.json` reports with indentation. JSONL records remain compact (one per line) in both modes to preserve streaming and the accepted dataset fingerprints.

```bash
uv run python -m benchmark inspect \
  --input datasets/evaluation/openai_041_scores.jsonl \
  --limit 2 --json-format pretty \
  --output datasets/evaluation/inspection.json
```

`inspect` reads but does not mutate its input. For `.jsonl`, it emits up to the requested number of records as a formatted JSON array in a wrapper. Other `.json` files can also be inspected. Keep the limit low for large response tables.

## Reproducibility and safety

- Canonical datasets and reference answers preserve the frozen 0.2.0 and 0.3.0 SHA-256 hashes.
- A trace record with a full response is checked against the captured response SHA-256. Tampering fails closed before score publication.
- Duplicate/unknown task IDs, wrong dataset hashes, and incomplete reference coverage fail closed.
- Each run can be partial; the report gives `evaluated_tasks`, `remaining_tasks`, and per-module metrics.
- Existing evaluation artifacts are protected from accidental overwrite; add `--replace` deliberately for a new scoring pass.
- Version 0.6.0 is planned to add deterministic MCP record/replay and scientific benchmark refinements.
