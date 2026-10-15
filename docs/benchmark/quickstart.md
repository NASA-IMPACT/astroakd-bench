> **0.6.7.11:** For the simplest supported workflow with ADS literature and multi-archive questions, use [the named `synthetic_100` guide](easy_mixed_100_workflow_0_6_7_11.md). This page also documents older or advanced flows.

# Current workflow — AstroAKD-Bench 0.6.7.10

This is the **current command guide**. Versioned documentation under `docs/benchmark/`
may illustrate earlier behavior. Execute all commands from the **repository root**.

## 1. Install and check configuration

Python 3.11+ and `uv` are supported. The Astroquery MCP server is a **separate
service** (e.g. the NASA IMPACT `astroquery-mcp` project); AstroAKD-Bench does
not start or own it. For tested command syntax to clone and start a local
`astroquery-mcp` server and generate a new 100-query study, see the
[100-query workflow](new_100_query_workflow.md).

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast --json-format pretty
```

Endpoint precedence: `--mcp-url`/`--mcp-server`, then `ASTROAKD_MCP_URL`, then
`http://127.0.0.1:8000/mcp`. Token precedence: `--mcp-token`/`--mcp-server-token`,
then `ASTROAKD_MCP_TOKEN`, otherwise unauthenticated. Set these in your shell:

```bash
# Local server
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN

# Alternative: remote HTTPS server with bearer access
export ASTROAKD_MCP_URL='https://coming-gray-slug.fastmcp.app/mcp'
export ASTROAKD_MCP_TOKEN='REPLACE_WITH_YOUR_TOKEN'
```

Generic `MCP_URL` and `MCP_TOKEN` **are not read**. Do not store or commit tokens
in code, output files, scripts or documentation. `doctor` names the URL on
connection failure without revealing the token. Refer to
[MCP authentication](mcp_endpoint_auth_0_6_7_3.md).

## 2. Instruction files (outside docs)

- Agent instruction for **arm B only**:
  `instructions/astroakd/AstroAKD_Instruction.md`.
- Synthetic authoring instruction for the `generate` workflow:
  `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md`
  (read by default when instructions are enabled).

These are **different projects' instructions**. The two files were moved from
`docs/` in version 0.6.7.5; their content hashes remain unchanged. The
benchmark oracle must never be passed to any agent.

## 3. Generate or examine the scorable questions

The release contains `datasets/generated/scorable_50.jsonl` (50 candidate tasks),
`datasets/gold/scorable_50_reference_oracle.jsonl` (frozen source-derived answers),
and `datasets/gold/scorable_50_question_answers.csv` (reviewer view).
They are based on the 42 completed structural reference responses, not
independently approved scientific truth. To build a **new** dataset from the
existing source reference records, choose new output paths:

```bash
uv run python -m benchmark build-scorable \
  --source-tasks datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --references datasets/validated/gold_mixed_065_ref_42.jsonl \
  --count 50 \
  --tasks-output datasets/generated/scorable_50_new.jsonl \
  --oracle-output datasets/gold/scorable_50_new_reference_oracle.jsonl \
  --answers-csv datasets/gold/scorable_50_new_question_answers.csv \
  --report datasets/gold/scorable_50_new_report.json
```

Do **not** regenerate the frozen `scorable_50.jsonl` used in a running experiment.
To author *unverified candidate* questions from the LLM prompt instead, see
[LLM generation](llm_generation_0_6_4.md).

## 4. Run the three GPT-5.2 arms

Set `OPENAI_API_KEY` and check MCP connectivity with `doctor` first. The three
arms are A: MCP only, B: MCP with AstroAKD instruction, C: web only.
The archive's original experiment journal must be kept separate from new runs.

### New 50-question experiment (without `--resume`)

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_fresh_runs.jsonl \
  --report datasets/agent/gpt52_fresh_report.json
```

### Pilot: five questions per arm (`--limit 5`)

Use a different output prefix from the full run:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --limit 5 --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_new_pilot_runs.jsonl \
  --report datasets/agent/gpt52_new_pilot_report.json
```

### Resume that pilot (`--resume`, no `--limit`)

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_new_pilot_runs.jsonl \
  --report datasets/agent/gpt52_new_pilot_report.json \
  --resume
```

The runner records task/arm pairs and checks the manifest before resuming;
do not change the MCP address, model or budgets mid-experiment. The agent
instruction was only renamed/moved, not rewritten, so its SHA-256 is unchanged.
Use new paths to start different experiments.

## 5. Score and generate CSV reports / plots

After a completed full new experiment, score its final `.jsonl`. For a pilot,
use the same prefix with `.jsonl.progress.jsonl` as input and choose a
**different report prefix**. First-time reports do not require `--replace`.

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_50.jsonl \
  --oracle datasets/gold/scorable_50_reference_oracle.jsonl \
  --runs datasets/agent/gpt52_fresh_runs.jsonl \
  --comparison-csv datasets/reports/gpt52_fresh_ABC_answers.csv \
  --summary-csv datasets/reports/gpt52_fresh_rates.csv \
  --detailed-csv datasets/reports/gpt52_fresh_detailed_150.csv \
  --performance-csv datasets/reports/gpt52_fresh_performance.csv \
  --task-performance-csv datasets/reports/gpt52_fresh_per_task_performance.csv \
  --plots-dir datasets/reports/gpt52_fresh_plots \
  --report datasets/reports/gpt52_fresh_scores.json \
  --json-format pretty
```

Outputs: (a) 50-question wide A/B/C table, (b) 150-row long answer report,
(c) three-row per-arm score and timing/token summaries, (d) 150-row per-task
performance file, (e) match-rate, mean-runtime and total-token barplots in
PNG/SVG. Incorrect, abstained and incomplete responses stay in the CSVs.
The score is archive-snapshot agreement, **not independently verified
scientific accuracy**. The scorer never makes OpenAI or MCP calls.

For an already existing report, add `--replace` intentionally; this overwrites
**reports only**, not the input journal, tasks or oracle.

## 6. Interpret results and check qualification

`reference_match_pct_attempted = reference_matches / attempted × 100`.
This measures agreement with a stored archive snapshot, **not independent
scientific accuracy**. `completion` means the agent execution returned, not
that the answer was correct. The first five-task GPT-5.2 pilot matched
A 5/5, B 5/5, C 1/5; the complete 50-task comparison is a separate milestone.

```bash
uv run python -m unittest discover -s benchmark/tests -q
```

See [experimental interpretation](experimental_methods.md),
[detailed reporting](three_arm_detailed_reporting_0_6_7_1.md), and
[the instructions directory](../../instructions/README.md).

## Build the HTML documentation

```bash
make -C docs/sphinx html
# Output: docs/_build/html/index.html
make -C docs/sphinx clean
```

See the [Sphinx build guide](documentation_build.md).

## 6. MCP tool-call CSVs and A/B diagnostic plots

The `run-three-arm` JSONL `trace` already preserves every MCP tool attempt.
Use the **same offline `score-scorable` command** as in the README, adding
`--mcp-calls-csv`, `--mcp-tool-frequency-csv`, and `--plots-dir` to obtain
one event row per actual call, per-function A/B totals, and five PNG/SVG plots
(including two MCP-specific A/B charts). See
[MCP tool-call reporting](mcp_tool_call_reporting_0_6_7_7.md). No GPT-5.2
re-execution is needed.

## 7. Paired 50-question analysis and CSVs (0.6.7.8)

For the completed 150-run journal, use the same `score-scorable` command with
`--overall-csv`, `--mcp-ab-summary-csv`, `--paired-questions-csv`,
`--paired-summary-csv`, `--mismatch-audit-csv` and `--paired-plots-dir`.
See [paired analysis and reproducible commands](paired_analysis_0_6_7_8.md).
These exports are offline, additive, and preserve the frozen dataset.


### Live reference collection at generation time (0.6.7.9)

Use `generate --with-reference-answers` for new single-call MCP candidates to execute the real archive query immediately after question writing. The companion validation JSONL stores full returned tables and provenance; its CSV includes observed expected-column values marked unreviewed. For existing generated questions, use `validate` directly. Keep reference collection separate from scientific gold review. See [the 100-query workflow](new_100_query_workflow.md).

### Archive-specific reference policy and offline review (0.6.7.10)

`validate` and `generate --with-reference-answers` accept `--archive-timeouts`,
`--archive-attempts` and `--reference-deadline`. A consolidated one-row-per-question
review CSV accompanies any reference CSV. The entirely offline
`reference-review-draft` command constructs a human-editable gold review JSONL
with row-cardinality and truncation warnings; no observed values are approved
by default. See [scientific-review guide](archive_policy_scientific_review_0_6_7_10.md).
