# Paired error and efficiency analysis (0.6.7.8)

AstroAKD-Bench version 0.6.7.8 adds offline, **paired** comparison of the
three GPT-5.2 arms. It neither re-runs the model/MCP tools nor changes the
frozen task or oracle files. These are **reference-snapshot agreement**
statistics, not independently validated scientific accuracy.

## Use the completed 150-run journal

Execute from the repository root. If the complete JSONL lives in the original
0.6.7.2 directory, set `--runs` to its absolute path rather than the bundled
15-run pilot journal. For example:

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_50.jsonl \
  --oracle datasets/gold/scorable_50_reference_oracle.jsonl \
  --runs /absolute/path/to/scorable_50_gpt52_runs.jsonl \
  --comparison-csv datasets/reports/full_ABC_answers.csv \
  --summary-csv datasets/reports/full_rates.csv \
  --performance-csv datasets/reports/full_performance.csv \
  --mcp-calls-csv datasets/reports/full_mcp_calls.csv \
  --mcp-tool-frequency-csv datasets/reports/full_mcp_frequency.csv \
  --overall-csv datasets/reports/overall_results.csv \
  --mcp-ab-summary-csv datasets/reports/mcp_ab_summary.csv \
  --paired-questions-csv datasets/reports/paired_questions.csv \
  --paired-summary-csv datasets/reports/paired_comparison_summary.csv \
  --mismatch-audit-csv datasets/reports/mismatch_audit.csv \
  --plots-dir datasets/reports/full_plots \
  --paired-plots-dir datasets/reports/paired_plots \
  --report datasets/reports/full_scores.json \
  --json-format pretty
```

Use `--replace` **only** when intentionally regenerating existing reports.
Source journals, task files and the oracle are read-only.

## New outputs

| Filename | Contents |
| --- | --- |
| `overall_results.csv` | One row for each A/B/C arm: matches, runtime, prompt/completion/total tokens, MCP attempts/successes/rejections, web searches and run errors. C MCP per-attempt rates remain N/A. |
| `mcp_ab_summary.csv` | A/B-only metrics, error and unsuccessful tool attempts, unique archive functions and gateway details. |
| `paired_questions.csv` | **50 rows**: reference, raw A/B/C answers, match and run statuses, individual durations, tokens, calls, B-minus-A and other paired differences. |
| `paired_comparison_summary.csv` | **Three rows**: A-vs-B, A-vs-C and B-vs-C match contingencies, exact two-sided McNemar p-values, runtime/token paired means/medians/quartiles and reproducible percentile-bootstrap mean-difference intervals. MCP deltas are only meaningful for A/B. |
| `mismatch_audit.csv` | Every *recorded* non-matching arm-answer (41 in the completed example), retaining answers, reference keys and observable categories, all marked for independent review. |

Figures are added under `--paired-plots-dir` as PNG/SVG pairs:
`paired_runtime_deltas`, `paired_token_deltas`, `paired_match_disagreements`,
`paired_mcp_attempt_deltas`. The five existing 0.6.7.7 charts remain
unchanged and go under `--plots-dir`.

## Methodology

The same question ID identifies a matched pair of arms. Each paired difference
is **second arm minus first arm**, so B-minus-A is negative when B uses less
runtime or fewer tokens. For partial journals, a missing observation remains
blank and is excluded from paired denominators. It is never counted as an
incorrect answer or zero duration. A tool call that the gateway rejects is
an attempted call, not a successful call.

For correctness, use the four-outcome contingency (`both_match`,
`first_only_match`, `second_only_match`, `neither_match`). Exact McNemar is a
*two-sided* binomial calculation on **discordant pairs only**; zero discordant
pairs yield p = 1, not evidence that the arms are identical. No adjustment for
multiple comparisons is applied. This is a single 50-question experiment; the
p-values must not be interpreted as independent science validation.

For each paired continuous difference, report the number of comparable
observations, arithmetic mean, median, Q1, Q3, and a fixed-seed (2000
replicates) nonparametric 95% **bootstrap interval for the mean difference**.
The bootstrap is descriptive and does not overcome shared-task dependence,
benchmark construction bias, system jitter, or repeated-trial uncertainty.

An observed `ABSTAIN`, `ABSTAIN_WITH_VALUES`, `INCORRECT_FORMAT`, `RUN_ERROR`,
or `REFERENCE_MISMATCH_UNCLASSIFIED` is not a scientific root-cause diagnosis.
Every mismatch gets `PENDING_INDEPENDENT_REVIEW` and a blank scientific cause.

## Reproducible full-run example

The supplied 150-record journal had SHA-256
`58824a2b71e7063b550c3fa16592f70307f11f6ace7293bf7fe81a47c334daaf`.
It yields 48 A matches, 49 B matches, and 12 C matches; 41 arm-level
mismatches. The A/B paired table yields 48 both-correct, zero A-only, one
B-only and one neither; **two-sided exact McNemar p = 1.0**. This means the
one-match difference does not establish an accuracy advantage for B.

B-minus-A mean runtime is approximately -6.48 seconds; the median is only
about -0.24 seconds. Always show both, because the mean is sensitive to a
small number of slow A runs. The experiment is not a benchmark of all archive
and literature discovery use cases.
