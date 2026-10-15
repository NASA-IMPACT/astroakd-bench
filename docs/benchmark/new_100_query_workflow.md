# New 100-query experiment: local MCP, generation, validation and scoring

This workflow applies to **AstroAKD-Bench 0.6.7.8**. Apart from the first
terminal, run commands from the AstroAKD-Bench repository root. All filenames
are **new** and must not replace the frozen 50-question experiment artifacts.

## 1. Start the independent Astroquery MCP server

In terminal 1, in a separate working directory:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

The upstream [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp)
is **not** part of AstroAKD-Bench. Keep this process running. Bind only to
loopback; its dynamic archive executor should not be publicly exposed.

In terminal 2, from AstroAKD-Bench:

```bash
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN
# Set OPENAI_API_KEY using your existing secure shell/key-management workflow.
uv sync
uv run python -m benchmark doctor --fast --json-format pretty
```

A remote HTTPS server can instead be selected with `ASTROAKD_MCP_URL` and
`ASTROAKD_MCP_TOKEN`, or CLI options. Generic `MCP_URL` and `MCP_TOKEN` are ignored.

## 2. Generate 100 new synthetic candidates

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --instructions --mcp \
  --model gpt-5.2 --count 100 --batch-size 5 --seed 20261015 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --output datasets/generated/synthetic_100_gpt52.jsonl \
  --csv-output datasets/generated/synthetic_100_gpt52.csv \
  --pretty-output datasets/generated/synthetic_100_gpt52_pretty.json \
  --report datasets/generated/synthetic_100_gpt52_report.json \
  --json-format pretty

wc -l datasets/generated/synthetic_100_gpt52.jsonl
```

The expected JSONL count is **100**. With 22 curated target seeds and five
archives, `archive-target` uniqueness supports 20 slots per archive. Do not use
`--uniqueness global-target` (only 22 distinct seeds) or `--task-mix gold50`
(which requires precisely 50 tasks). The generator uses MCP **discovery only**;
no archive observations or accepted reference answers are obtained here.
The questions are `candidate_unvalidated`, not scientific gold. A seed fixes
candidate-slot selection but cannot guarantee identical wording from a live LLM.

## 3. Validate archive evidence: five-task pilot, then resume

Real MCP archive queries are issued only in this phase. First validate five:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_100_gpt52.jsonl \
  --output datasets/validated/synthetic_100_gpt52_references.jsonl \
  --report datasets/validated/synthetic_100_gpt52_validation_report.json \
  --csv-output datasets/validated/synthetic_100_gpt52_references.csv \
  --attempts 2 --delay 2 --timeout 180 \
  --limit 5 --json-format pretty
```

Review these results and resume with the **same endpoint, arguments, input and
output paths**, removing `--limit`:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_100_gpt52.jsonl \
  --output datasets/validated/synthetic_100_gpt52_references.jsonl \
  --report datasets/validated/synthetic_100_gpt52_validation_report.json \
  --csv-output datasets/validated/synthetic_100_gpt52_references.csv \
  --attempts 2 --delay 2 --timeout 180 \
  --resume --json-format pretty
```

The partial journal is `synthetic_100_gpt52_references.jsonl.progress.jsonl`;
the final `.jsonl` is published after 100 dispositions are recorded.
**Every one of the 100 dispositions must be `accepted_nonempty`** to pass the
current `build-scorable` gate. This is not guaranteed: some live archive
queries will return no usable records or fail. If this happens, manually review
and correct/replace tasks, revalidate under a **new dataset hash and new output
prefix**, and do not fabricate reference answers or alter in-progress inputs.

## 4. Build a 100-question source-anchored reference oracle

Only if all 100 completed references are `accepted_nonempty` and contain
suitable unambiguous field values:

```bash
uv run python -m benchmark build-scorable \
  --source-tasks datasets/generated/synthetic_100_gpt52.jsonl \
  --references datasets/validated/synthetic_100_gpt52_references.jsonl \
  --count 100 \
  --tasks-output datasets/generated/scorable_100_gpt52.jsonl \
  --oracle-output datasets/gold/scorable_100_gpt52_reference_oracle.jsonl \
  --answers-csv datasets/gold/scorable_100_gpt52_question_answers.csv \
  --report datasets/gold/scorable_100_gpt52_report.json
```

If the builder finds fewer than 100 usable field-level answers, it fails
instead of silently filling missing keys. `reference_anchored_unreviewed`
means archived reference agreement, **not independent scientific validation**.

## 5. Run all three GPT-5.2 arms (300 records)

First pilot five scorable questions per arm (**15** runs):

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_100_gpt52.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --limit 5 \
  --max-turns 8 --max-calls 12 --max-tool-bytes 262144 \
  --timeout 180 --task-timeout 900 \
  --output datasets/agent/scorable_100_gpt52_runs.jsonl \
  --report datasets/agent/scorable_100_gpt52_report.json \
  --json-format pretty
```

Resume the same experiment with **no `--limit`**:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_100_gpt52.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 \
  --max-turns 8 --max-calls 12 --max-tool-bytes 262144 \
  --timeout 180 --task-timeout 900 \
  --output datasets/agent/scorable_100_gpt52_runs.jsonl \
  --report datasets/agent/scorable_100_gpt52_report.json \
  --resume --json-format pretty
```

The final `.jsonl` is published once **300 task/arm pairs** have been recorded;
interrupted runs use `.jsonl.progress.jsonl`. Never run two writers on one
journal, use `--replace` to resume, or change manifest-bound settings while
resuming. This step issues paid OpenAI requests and uses the live MCP endpoint.

## 6. Score offline; produce combined CSVs and paired figures

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_100_gpt52.jsonl \
  --oracle datasets/gold/scorable_100_gpt52_reference_oracle.jsonl \
  --runs datasets/agent/scorable_100_gpt52_runs.jsonl \
  --comparison-csv datasets/reports/scorable_100_ABC_answers.csv \
  --summary-csv datasets/reports/scorable_100_rates.csv \
  --performance-csv datasets/reports/scorable_100_performance.csv \
  --mcp-calls-csv datasets/reports/scorable_100_mcp_calls.csv \
  --mcp-tool-frequency-csv datasets/reports/scorable_100_mcp_frequency.csv \
  --overall-csv datasets/reports/scorable_100_overall_results.csv \
  --mcp-ab-summary-csv datasets/reports/scorable_100_mcp_ab_summary.csv \
  --paired-questions-csv datasets/reports/scorable_100_paired_questions.csv \
  --paired-summary-csv datasets/reports/scorable_100_paired_comparison_summary.csv \
  --mismatch-audit-csv datasets/reports/scorable_100_mismatch_audit.csv \
  --plots-dir datasets/reports/scorable_100_plots \
  --paired-plots-dir datasets/reports/scorable_100_paired_plots \
  --report datasets/reports/scorable_100_scores.json \
  --json-format pretty
```

The scorer creates overall A/B/C and MCP-specific A/B summary CSVs,
question-paired correctness/efficiency records, mismatch audit and PNG/SVG
plots. Use `--replace` only when re-generating **existing report files**.
Score the `.progress.jsonl` instead if you intentionally want a partial
snapshot; never mislabel partial results as a full 100-question experiment.

Keep the original 50-question dataset/oracle and 150-run journal intact.
Match percentages between different task sets do not by themselves prove
model improvement. The 100-question workflow has been locally checked, but
**a live end-to-end 100-query experiment has not been executed here**.
