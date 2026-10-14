# Detailed GPT-5.2 A/B/C answer and performance reporting — 0.6.7.1

## Scientific boundary

`AstroAKD` is the agent being evaluated; `AstroAKD-Bench` is the separate benchmark runner and evaluator. Agent instruction `docs/agent/AstroAKD_Instruction.md` applies **only** to B. Synthetic generation instructions **never** serve as the AstroAKD agent instruction.

All values in the `scorable_50_reference_oracle.jsonl` key derive from a **frozen MCP archive response**, and were not yet independently approved as scientific gold. Match rates must always be labeled **reference-snapshot match rates**, not verified astronomical truth. The results are also **pilot-only** until all 150 arm executions are complete.

## Reproduce from saved GPT-5.2 pilot journal

This command needs **no API keys and no running MCP server**. Run from the project root:

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_50.jsonl \
  --oracle datasets/gold/scorable_50_reference_oracle.jsonl \
  --runs datasets/agent/scorable_50_gpt52_runs.jsonl.progress.jsonl \
  --comparison-csv datasets/reports/scorable_50_gpt52_ABC_answers.csv \
  --summary-csv datasets/reports/scorable_50_gpt52_rates.csv \
  --detailed-csv datasets/reports/scorable_50_gpt52_detailed_150.csv \
  --performance-csv datasets/reports/scorable_50_gpt52_performance.csv \
  --task-performance-csv datasets/reports/scorable_50_gpt52_per_task_performance.csv \
  --plots-dir datasets/reports/scorable_50_gpt52_plots \
  --report datasets/reports/scorable_50_gpt52_scores.json \
  --replace --json-format pretty
```

`--replace` is needed to overwrite reports from the earlier 0.6.7 scoring command; it **never edits** `--tasks`, `--oracle`, or `--runs`.

## Output files

- `scorable_50_gpt52_ABC_answers.csv` — original wide 50-row comparison, including unrun tasks.
- `scorable_50_gpt52_rates.csv` — original 3-row A/B/C reference match rates.
- `scorable_50_gpt52_detailed_150.csv` — new 150-row long comparison, including **all** answers (even wrong, empty, free-text, abstained and error), original source IDs, compact tool-event summary (complete raw traces remain in the JSONL journal), total/prompt/output tokens and response status.
- `scorable_50_gpt52_performance.csv` — one row per arm (3 total): run coverage, completion, match rates, mean/total time, prompt/output/total tokens, mean tokens, MCP and web counts, errors. `scientific_accuracy_pct` is blank until an independent gold review.
- `scorable_50_gpt52_per_task_performance.csv` — 150 resource-use rows for plotting further distributions.
- `scorable_50_gpt52_plots/match_rate.png` + `.svg` — percent of **attempted questions** matching the snapshot.
- `scorable_50_gpt52_plots/mean_runtime.png` + `.svg` — mean per-attempt wall seconds (including failed runs if timed).
- `scorable_50_gpt52_plots/total_tokens.png` + `.svg` — sum of **reported** token usage, not monetary cost.

All figures show attempted counts, so a 5/50 pilot cannot be mistaken for full coverage. If an arm has no attempts, its attempted match rate and runtime plot values display **N/A** rather than zero. Blank `scientific_accuracy_pct` means no independent approved gold, not scientific accuracy 0%. Report file columns are stable for reusing the same plotting procedure after completion of the full 150-run experiment.

## Performance normalization

- `reference_match_pct_attempted = correct / attempted × 100`; run errors and abstentions count as nonmatches.
- `reference_match_pct_all_questions = correct / total_questions × 100`, a progress-aware figure distinct from scientific accuracy.
- `mean_runtime_seconds` is the average of available nonnegative wall-clock durations per arm, while `total_runtime_seconds` sums the same durations.
- Token totals unify Chat Completions (`prompt_tokens`, `completion_tokens`) and Responses (`input_tokens`, `output_tokens`) fields. If a provider supplied `total_tokens`, it takes precedence; missing token usage counts as zero **and** is flagged in `token_usage_reported_runs`.
- `web_search_calls` counts hosted web-search actions, not number of questions using web search. `successful_mcp_calls` counts successful tool events, and `rejected_tool_calls` counts blocked tool calls. The count of question runs using web is a separate metric.
- The runner's `completed` status means the SDK call finished, not that its answer matches the reference. `ABSTAIN_WITH_VALUES` is a *diagnostic sublabel* of a scored abstention if the agent supplied a numeric/text value while claiming to abstain.

## Experimental interpretation

A/B/C should use the same GPT-5.2 model, question IDs, budgets and tool isolation. A can access Astroquery MCP without the specialist AstroAKD instruction; B uses the same MCP tools plus that instruction; C uses web search without MCP. The saved 0.6.7 pilot produced A 5/5, B 5/5, C 1/5 snapshot matches; A/B matched equally, so **no instruction benefit is established by five questions**. Full 50-task comparisons will need independent scientific gold verification for publication-level accuracy claims.
