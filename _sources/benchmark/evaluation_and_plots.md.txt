# Question-aware automatic reference-answer scoring (0.6.7.11.12)

The following commands evaluate saved agent answers against saved independent Astroquery MCP reference observations; they do not run LLMs or the MCP server. Baseline A/B/C runs remain frozen.

```bash
uv run --with matplotlib python -m benchmark score-reference-answers \
  --name astroakd_100_v2 --output-dir datasets
```

Outputs: `reports/astroakd_100_v2/automated/{match_rate,accuracy_by_archive,accuracy_by_question_type}.{png,svg}`, `automated_scores_per_question.csv`, `accuracy_breakdown.csv`, and `automated_scoring_summary.json`. Use `--replace` to regenerate reports. Each score is `correct`, `partially_correct`, `incorrect`, `abstained`, or `failed`, and the JSON includes an explicit exclusion count for tasks without complete, usable reference evidence. Strict match rates count only **correct**, not partial credit, over evaluable tasks.

For missing independent multi-step evidence, `collect-multistep-references --name astroakd_100_v2 --output-dir datasets --timeout 900 --limit 5` creates a resumable journal; continue with `--resume`. The twelve two-archive questions have explicit per-step MCP read-only plans. The eight literature-driven questions require independent observation reference plans and verified paper–observation association evidence; ADS bibliographic searches alone do not supply complete ground truth. Existing questions, single-call reference results, and 300 agent traces are not regenerated or overwritten.

**Current saved study (2026-10-19):** The six previously incomplete VizieR multi-archive steps have now been recovered. The 80 single-call plus 12 multi-archive references make **92/100 questions evaluable**. The eight literature-driven questions remain excluded. With the original frozen A/B/C runs, strict archive-reference matches are **87/92 (94.57%)** for A, **88/92 (95.65%)** for B, and **13/92 (14.13%)** for C. The separate offline `draft-literature-plans` result (`draft_ready=6`, `requires_resolution=2`) does **not** change these denominators: drafts are unverified templates, not independently established observation references. See [Reference collection and scientific review](references_and_review.md) for the eight task IDs and safe interpretation.

**Scope:** Automated comparison is archive-reference agreement, not independently reviewed scientific accuracy. Tolerances, row multiplicity and matching decisions are described in the JSON scoring policy. Partial/abstained/failed counts remain distinct. Diagnostic higher-turn retries must not replace the original common-budget comparison.

## View the published example

The frozen [`astroakd_100_v2` example](example_results.md) includes question/reference tables, per-task scoring CSVs, and plots. The strict-match figure below uses **92 evaluable questions**, not the earlier 69-question legacy snapshot:

![Saved strict archive-reference match rate](../_static/examples/match_rate.png)

---

# Run and report the A/B/C benchmark

Run the three-agent experiment on one saved question dataset. Reference evidence and gold answers are hidden from the evaluated agents.

```bash
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --limit 5

uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --resume
```

The run journal is under `datasets/agent/`. The three arms are **A: MCP only**, **B: MCP plus the frozen AstroAKD specialist instruction**, **C: Web only**. The complete 100-question experiment has up to 300 question/arm results. Resume the same configuration to preserve comparisons.

## Offline reports and figures

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets
```

`run-benchmark` **does not create plots**; it writes the A/B/C run journal under `datasets/agent/`. Run **`agent-report` afterwards** (or during an unfinished experiment for provisional figures). It reads saved runs offline without new OpenAI or MCP calls. Use `--replace` to regenerate existing report files, not the run journal:

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets --replace
```

The main A/B/C figures are saved in **`datasets/reports/astroakd_100_v2/agents/`**:

| Figure | Meaning | Comparison with the earlier GPT-5.2 plots |
| --- | --- | --- |
| `mean_runtime.png` / `.svg` | Mean seconds per *recorded* agent run, by arm | Comparable to historical `mean_runtime.png`, subject to dataset/run-count differences |
| `total_tokens.png` / `.svg` | Sum of recorded token usage, by arm | Comparable to historical `total_tokens.png` only when run coverage is considered |
| `completed_runs.png` / `.svg` | Number of completed runs | Operational completion, **not** matching/science accuracy |
| `mean_mcp_events.png` / `.svg` | Mean MCP tool events per run | Additional operational comparison |
| `web_search_calls.png` / `.svg` | Total web searches by arm | Additional operational comparison |

CSV output includes `arm_operational_summary.csv`, `per_task_operational.csv`, and `abc_answers.csv` (retains answers). A partial run is summarized as partial; do not compare total tokens between arms without checking their recorded run counts.

### Match-rate figure: provisional reference-snapshot agreement

The legacy 0.6.7.11.8 scorer now writes **`strict_snapshot_match_rate.png` / `.svg`** (kept for audit comparison); 0.6.7.11.11 writes the enhanced `match_rate.png` when `datasets/validated/astroakd_100_v2_references_review.csv` exists and contains complete, automatically comparable reference evidence. This is **not independently verified scientific accuracy**. The figure explicitly says “UNREVIEWED” and reports the number of eligible questions. Its exact-match denominator includes only supported complete single values, complete single-column record lists, and coordinate pairs; truncated, null, multifield, uncollected/multi-step and structurally unsuitable references are excluded. Errors and abstentions on eligible tasks are nonmatches. See `reference_agreement_summary.json` and `reference_agreement_per_question.csv` for a complete audit trail and exclusion reasons. If no usable snapshots exist, the program reports `NOT_SCORABLE` and does not invent a match rate.

The provisional snapshot match report does **not** establish verified scientific correctness.

**A reference-snapshot match is not an independently reviewed gold answer.** Do not label this scientific accuracy or compare its percentage directly with the frozen earlier 50-question experiment without naming both score definitions and scorable populations. To claim verified scientific accuracy, use reviewed gold and the separate `score-three-arm` workflow.

### Retry only the failed MCP-only questions, preserving the original experiment

After the baseline run is finalized, `--resume` will not reopen the journal and `--replace` would overwrite the experiment. **Use `--retry-errors` instead:**

```bash
# Offline preview: no OpenAI or MCP requests
uv run python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --retry-errors --dry-run --max-turns 16 --max-calls 20

# Two additional MCP-only attempts for the observed 2 error records
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --retry-errors --max-turns 16 --max-calls 20 \
  --timeout 900 --task-timeout 2400
```

The original `datasets/agent/astroakd_100_v2_ABC_runs.jsonl` remains untouched. New files are named `astroakd_100_v2_mcp_only_turn16_retries.jsonl` and `astroakd_100_v2_ABC_runs_turn16_diagnostic.jsonl`. Only successes replace error records in the latter *derived*, visibly changed-budget diagnostic journal. To produce separate plots including provisional match rate:

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets \
  --runs datasets/agent/astroakd_100_v2_ABC_runs_turn16_diagnostic.jsonl
```

Its outputs are under `datasets/reports/astroakd_100_v2/agents_diagnostic/`. Never merge these changed-budget retries silently into the original A/B/C result. Scientific gold remains unavailable.

For reference-side **archive completeness and response-time figures**, use the separate offline command documented in [Reference collection and scientific review](references_and_review.md).

**Interpretation:** Successful agent execution or agreement with an unreviewed reference snapshot is not scientific accuracy. Report verified correctness only with a separate reviewed gold oracle and transparent denominators. Keep paper claims about the historical 50-question result separate from any new 100-question run.

## Multi-archive scoring closure in 0.6.7.11.12

The archive-reference comparator now checks each retrieved record with its **archive and field provenance** and preserves exact observation IDs, row multiplicity and mixed-field units. A comma-separated list of explicit HEASARC ObsIDs or archive-labelled SIMBAD matched IDs is parsed without accidentally extracting unrelated numbers from source descriptions. If one unlabeled value matches multiple archives or fields, the scorer refuses to invent its association. Extra records prevent a strict full match. Reported percentages are conditioned on *complete independent reference evidence*, not on independent scientific gold review.

Run `uv run --with matplotlib python -m benchmark score-reference-answers --name astroakd_100_v2 --output-dir datasets --replace` after incomplete-step retries. The plotted denominator and explicit exclusion causes can change as independently collected references become complete; keep earlier figures archived when comparing results across scoring-policy versions.
