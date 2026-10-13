# Query diversity, answer intents and deduplication (0.6.3)

AstroAKD-Bench is independent of the NASA IMPACT astroquery-mcp server.
This version improves *candidate diversity* before attempting broader agent
benchmarking. The original formally accepted dataset is intentionally frozen;
new generation produces a **different** task suite with a new SHA-256.

## Motivation and historical evidence

The user's `Astro Benchmark V1.xlsx` contains example questions about archive
observation IDs, instruments, filters, proposals and exposure times together
with expected answers. These are examples of useful **answer-oriented**
benchmarks; the workbook's expected answers are not copied into newly generated
tasks or claimed to have been independently verified.

A prior 50-task seed=123 generator produced 50 distinct strings and MCP calls
but only 22 archive-target combinations (28 repeated combinations); one MAST
target appeared repeatedly at radii 2, 3, 5, 8 and 10 arcmin. This violates
the independence desired for a 50-task diversity benchmark.

## Generate a diverse 50-task set

Start the external MCP server from its own checkout:

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

From the **AstroAKD-Bench** checkout:

```bash
uv run python -m benchmark generate \
  --backend template \
 --count 50 --seed 123 --modules simbad,mast,heasarc,gaia,vizier \
 --uniqueness archive-target --question-style answer-oriented \
 --output datasets/generated/diverse_063.jsonl \
 --csv-output datasets/generated/diverse_063.csv \
 --pretty-output datasets/generated/diverse_063_pretty.json \
 --report datasets/generated/diverse_063_report.json \
 --json-format pretty
```

The new generator selects a **new target for each successive question within
an archive**, not another radius for the same target. Duplicate normalized
questions, exact MCP calls and archive-target pairs are rejected. If the pool
cannot support the requested count and policy, generation fails with the count
of available seeds and actionable options.

Policies: `archive-target` (default, enough capacity for 50 with 22 targets
across five archives) and `global-target` (requires 50 distinct targets for
50 tasks, so add 50 custom `SkyTarget` objects through the Python API).
The stricter policy never silently downgrades to the weaker policy.

Question styles: `answer-oriented` (default) asks for scientifically distinct
returned fields, and `discovery` provides the earlier simple lookup/search
style. Both generate identical read-only **kinds** of MCP operations and
perform only MCP function discovery, not astronomical archive queries.

## Gold answers are NOT synthesized

Task metadata include `intent`, `answer_spec.expected_columns` and
`answer_spec.expected_answer_status=unverified_candidate`. Column examples:
SIMBAD main identifiers and coordinates, MAST proposal IDs and instruments,
HEASARC observation IDs/status/appropriate exposure-or-duration columns,
Gaia source IDs, parallax and proper motion, VizieR II/246 2MASS magnitudes,
VizieR I/355 Gaia DR3 positions, IDs and G magnitude. The reference validator
must query the live archive and verify whether columns and values are present.
No specific proposal ID, observation identifier, instrument, flux or science
value may be considered correct just because a template expects a field.

## Offline audit (no network)

```bash
uv run python -m benchmark audit-diversity \
 --input datasets/generated/diverse_063.jsonl \
 --report datasets/generated/diverse_063_audit.json --json-format pretty
```

With existing completed references:

```bash
uv run python -m benchmark audit-diversity \
 --input datasets/generated/synthetic_queries.jsonl \
 --references datasets/validated/reference_answers.jsonl \
 --report datasets/validated/diversity_audit.json --json-format pretty
```

Report sections: `candidate_diversity`, `reference_provenance`,
`reference_redundancy`, `answerability_advisory`. `reference_provenance`
requires exact agreement of stored task calls and reports candidate-file
SHA-256 equality separately. When comparing historical data across package
versions, equivalent calls are *not* a replacement for byte-exact provenance.

Returned-data duplication fingerprints are computed only from **nonempty**
serialized table column names and row dictionaries; per-query parameters,
service metadata and truncated row totals are omitted from the signature.
Matching fingerprints imply matching **returned subsets**; they do not prove
identical astrophysical result sets. Empty results cannot support a claim of
identical observed sources. Two separate archives are never placed in the same
fingerprint group. A `diversity_gate=REVIEW` does not override the validator's
structural acceptance assessment.

## Live validation on a laptop

Start with one task for diagnostics, then resume with the same paths:

```bash
uv run python -m benchmark validate \
 --input datasets/generated/diverse_063.jsonl --limit 1 \
 --attempts 1 --timeout 45 --delay 0 \
 --output datasets/validated/diverse_063_references.jsonl \
 --pretty-output datasets/validated/diverse_063_references_pretty.json \
 --csv-output datasets/validated/diverse_063_references.csv \
 --report datasets/validated/diverse_063_validation_report.json \
 --json-format pretty

uv run python -m benchmark validate \
 --input datasets/generated/diverse_063.jsonl --resume \
 --attempts 1 --timeout 45 --delay 2 \
 --output datasets/validated/diverse_063_references.jsonl \
 --pretty-output datasets/validated/diverse_063_references_pretty.json \
 --csv-output datasets/validated/diverse_063_references.csv \
 --report datasets/validated/diverse_063_validation_report.json \
 --json-format pretty
```

**Do not use `--strict-accepted-020` on a new 0.6.3 dataset.** This option
checks the historical frozen seed=42 dataset hash and intentionally rejects
new candidate files. A structurally accepted reference need not contain
scientifically verified gold answers. Observe the `answerability_advisory`,
empty-result counts, truncation flags and redundancy findings before running
large LLM evaluations.

## Reusable Python API

```python
import asyncio
from benchmark.api import AstroAKDBench, SkyTarget

async def main():
    bench = AstroAKDBench(root='.', mcp_url='http://127.0.0.1:8000/mcp')
    tasks = await bench.generate_queries(
        count=50, seed=123, uniqueness='archive-target',
        question_style='answer-oriented',
        output='datasets/generated/diverse_063.jsonl',
        csv_output='datasets/generated/diverse_063.csv',
        pretty_output='datasets/generated/diverse_063_pretty.json',
    )
    print(tasks['distinct_archive_target_pairs'])
    print(bench.audit_diversity(tasks='datasets/generated/diverse_063.jsonl')['status'])

asyncio.run(main())
```

For **global target uniqueness with 50 questions**, provide a tuple of 50+
distinct real targets using `SkyTarget(name, ra_deg, dec_deg)`. Their names
and coordinates must be scientifically checked by the benchmark author; the
API validates only shape, ranges, uniqueness and reproducibility.

## Next scientific milestones

- Validate actual answer values for identifier/instrument/photometry tasks,
  recording precise row-selection conditions and independently verifiable gold.
- Expand archive/query-function coverage and realistic multi-archive steps
  beyond five allowlisted operations, with explicit MCP contract tests.
- Add calibrated scoring of answers against validated gold values and handle
  truncated/paginated response data; do not equate tool success with science.
- Use the Excel benchmark as a *curated dataset source* only after checking
  reused workbook IDs, provenance, expected-answer truth and licenses.
