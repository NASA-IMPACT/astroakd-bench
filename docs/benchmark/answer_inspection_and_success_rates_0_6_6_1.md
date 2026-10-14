# 0.6.6.1 — Inspect generated questions, reference values and AstroAKD answers

## Scope and evidence levels

AstroAKD-Bench (independent evaluation package) created 50 mixed synthetic questions:
32 archive-driven, 10 coordinate-driven, and 8 literature-driven. The separate AstroAKD
agent was run against 5 questions under A (MCP only), B (MCP + `AstroAKD_Instruction.md`),
and C (OpenAI hosted web search only), yielding 15 completed model runs.

The **42/42** archive/coordinate MCP reference calls returned nonempty evidence
(`datasets/validated/gold_mixed_065_ref_42.jsonl`), but no independently verified
scientific gold answers exist. Some MAST result sets report thousands of total rows
while delivering just 20 to the saved response. Returned table values therefore are
**reference candidates**, not ground-truth complete sets.

## Generate the review files

Run from the AstroAKD-Bench repository root:

```bash
uv run python -m benchmark export-answer-csv \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --references datasets/validated/gold_mixed_065_ref_42.jsonl \
  --reference-tasks datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --runs datasets/agent/astroakd_three_arm_runs.jsonl.progress.jsonl \
  --questions-csv datasets/reports/gold_mixed_065_questions_references_ABC.csv \
  --arms-csv datasets/reports/astroakd_three_arm_answers_150_rows.csv \
  --summary-csv datasets/reports/astroakd_three_arm_success_rates.csv \
  --reference-values-csv datasets/reports/gold_mixed_065_reference_values_all.csv \
  --per-arm-dir datasets/reports/per_arm \
  --report datasets/reports/astroakd_csv_review_report.json \
  --json-format pretty
```

If these outputs already exist, pass `--replace` intentionally, or choose new names.
It is safe to export repeatedly: the command does not call MCP/ADS/OpenAI or modify
original JSONL traces. The 50-row CSV shows the *full actual final-answer text* for
A, B and C, with `not_run` for 45 questions in the pilot; the 150-row file is ideal
for filtering and review; the three per-arm files contain 50 rows each.

The `reference_candidate_values_json` field contains every nonnull returned value
from fields listed in the question's `answer_spec.expected_columns`, including table
and row indexes. The value-level CSV splits these into 1,709 source rows. It does not
complete or correct truncated results, deduplicate the scientific answer set, infer
missing science constraints, or merge multiple archive catalogs into a gold set.

## Percentage definitions

| Statistic | Denominator | Interpretation |
| --- | --- | --- |
| `completion_rate_attempted_pct` | Run attempts for this arm | Technical runner completion; not science accuracy |
| `coverage_all_questions_pct` | All 50 tasks | How much of the experiment is completed |
| `structured_answer_rate_completed_pct` | Completed model runs | Machine-readable output contract adherence |
| `nonempty_answer_rate_completed_pct` | Completed runs | Merely answer text present |
| `scientific_success_rate_pct` | Gold-scored runs with measurable answers | Independently graded correctness; blank if none |

On the supplied five-task pilot: A, B and C each have 5/5 technical completions
(100%) and 5/50 overall coverage (10%). Structured output success is 1/5 for A (20%),
0/5 for B (0%) and 0/5 for C (0%). All 15 answers contain nonempty text, but this
**does not** imply they answered the actual science question. There are zero approved
gold answers, so all three science success percentages are blank.

## Scoring after gold verification

Finish separate scientific review using `gold-draft` and `gold-finalize`. The
`export-answer-csv --gold datasets/gold/approved.jsonl` command can then report
scientific percentages, restricted to the approved and actually graded subset.
The separate `score-three-arm` command remains the authoritative structured
scientific scorer and requires the finalized 150-record run output (not the pilot journal).

Keep the full evidence provenance in the frozen gold file. `gold-finalize` enforces
reviewer attribution, independent citations and special truncation safeguards.

## Known experimental problems

The initial PG 1211+143 pilot used incorrect coordinates and the evaluation tool
guard blocked an intermediate SIMBAD resolution in the instructed MCP arm.
MAST is row-limited at the server, and some Gaia/VizieR responses exceeded the
agent input budget. The pilot is diagnostic; do not publish its completion rates as
scientific answer-accuracy results. Rerun affected tasks under a single corrected
policy with **fresh journals**, not `--resume` on an incompatible run policy.
