# Current workflow — AstroAKD-Bench 0.6.7.4

This is the **current command guide**. Versioned documentation under `docs/benchmark/`
may illustrate earlier behavior. Execute all commands from the **repository root**.

## 1. Install and check configuration

Python 3.11+ and `uv` are supported. The Astroquery MCP server is a **separate
service** (e.g. the NASA IMPACT `astroquery-mcp` project); AstroAKD-Bench does
not start or own it.

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
  `instructions/astroakd_bench/llm_generation_instructions_v1.md`
  (read by default when instructions are enabled).

These are **different projects' instructions**. The two files were moved from
`docs/` in version 0.6.7.4; their content hashes remain unchanged. The
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

Set `OPENAI_API_KEY` in the **runner** environment; start the external MCP
service and check it with `doctor`. The 3 arms are A: MCP only, B: MCP plus
specialist AstroAKD instruction, and C: web search only (never MCP).

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 \
  --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/scorable_50_gpt52_runs.jsonl \
  --report datasets/agent/scorable_50_gpt52_report.json \
  --resume --json-format pretty
```

**Resume** assumes a matching previously initialized manifest/journal; remove
`--resume` for a brand-new output prefix. For a pilot on brand-new paths use
`--limit 5`. Do not combine `--resume` with `--replace`. A resumed experiment
requires the same question hash, instruction content hash, model, MCP URL,
and resource budgets. Changing just the file path to the **identical** moved
instruction does not change its hash. An ongoing process should be allowed to
finish before applying a software update. Switching the MCP server requires
starting a separate experiment with **new output paths**.

## 5. Score all answers and re-create CSV and plots

After completion, the runner publishes the final `.jsonl`. For a partial
experiment use the same prefix with `.jsonl.progress.jsonl` instead.

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_50.jsonl \
  --oracle datasets/gold/scorable_50_reference_oracle.jsonl \
  --runs datasets/agent/scorable_50_gpt52_runs.jsonl \
  --comparison-csv datasets/reports/scorable_50_gpt52_ABC_answers.csv \
  --summary-csv datasets/reports/scorable_50_gpt52_rates.csv \
  --detailed-csv datasets/reports/scorable_50_gpt52_detailed_150.csv \
  --performance-csv datasets/reports/scorable_50_gpt52_performance.csv \
  --task-performance-csv datasets/reports/scorable_50_gpt52_per_task_performance.csv \
  --plots-dir datasets/reports/scorable_50_gpt52_plots \
  --report datasets/reports/scorable_50_gpt52_scores.json \
  --replace --json-format pretty
```

Produces (a) 50-question wide A/B/C table, (b) 150-row long answer report,
(c) three-row per-arm score + timing/token summaries, (d) 150-row per-task
performance, and (e) match-rate, mean-runtime and total-token barplots in PNG
and SVG. **All answers are retained**, correct or incorrect. Scoring is offline:
no OpenAI calls or MCP connectivity required. `--replace` only replaces output
reports, never the source agent journal, tasks or oracle.

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
