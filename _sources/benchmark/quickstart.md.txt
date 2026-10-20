# Getting started

AstroAKD-Bench evaluates astronomical archive-search agents. The benchmark **creates questions** and compares three agent configurations using a separately running [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp).

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- An `OPENAI_API_KEY` in the environment when generating or running the agents
- An Astroquery MCP server serving `http://127.0.0.1:8000/mcp` (or set `ASTROAKD_MCP_URL`)
- Working ADS credentials **on the MCP server** if using `--require-ads`

## Install the external Astroquery MCP server (Terminal 1)

In a **separate terminal**, from the directory where you want the independent server checkout:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Keep the MCP server running while using the benchmark. The command starts the local endpoint at `http://127.0.0.1:8000/mcp`. For ADS-backed literature questions, set an ADS token (`API_DEV_KEY` or server-supported `ADS_API_KEY`) **in the server process environment before starting it**, then restart the server if its environment changes. Do not add the token to source files, questions or logs.

## Install and check AstroAKD-Bench (Terminal 2)

In a **second terminal**, switch to your AstroAKD-Bench checkout, not the `astroquery-mcp` directory:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast
```

Configure `OPENAI_API_KEY` securely in the benchmark terminal before generating questions or evaluating agents. To check literature search, run:

```bash
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

The benchmark defaults to `http://127.0.0.1:8000/mcp`. Use `ASTROAKD_MCP_URL` (and optionally `ASTROAKD_MCP_TOKEN` for a protected MCP endpoint) only when connecting elsewhere. The MCP client token is distinct from the server-side ADS token. For details, see [ADS and MCP connectivity](ads_and_mcp.md).

## Recommended 100-question workflow

In the AstroAKD-Bench repository root:

```bash
# Check ADS authentication and a real small ADS query before spending OpenAI credits
uv run python -m benchmark literature-auth --probe

# Create a mixed 100-question experiment and collect eligible reference evidence
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers

# Offline reference quality report
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 --output-dir datasets

# Test five questions before running all three agents on 100 questions
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --resume

# Offline A/B/C plots and CSVs
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets
```

The five named commands create their needed output subdirectories automatically.

### Recover references without regenerating questions

If the question JSONL was saved but reference collection stopped, finish the
80 single-call MCP queries directly (no OpenAI calls):

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100_v2 \
  --output-dir datasets \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

Append `--resume` only for an interrupted collector with a saved progress
journal. If the 80/80 references were already collected successfully, skip
this step and run only the offline `reference-report` command shown above.
The 20 literature/multi-archive questions require separate multi-step
evidence. See [reference collection and reports](references_and_review.md).

`--seed` is optional, defaulting to `20261018`, and does not guarantee identical responses from GPT-5.2. Preserve the generated JSONL for reproducibility.

## Current v2 reference coverage and literature drafts (2026-10-19)

The current saved `astroakd_100_v2` dataset contains 80 complete single-call references and 12 complete two-archive references. The recovered VizieR steps need no further retries; eight literature questions still lack verified paper-linked observation evidence. The offline scorer evaluates **92/100** questions. The literature draft command

```bash
uv run python -m benchmark draft-literature-plans \
  --name astroakd_100_v2 --output-dir datasets
```

has already produced `datasets/validated/astroakd_100_v2_literature_plan_drafts.jsonl` with `DRAFT_ONLY_NOT_REFERENCE`: six unverified candidate templates and two requiring target/archive resolution. **These drafts are not runnable `--literature-plans` input and are not reference answers.** Read [Reference collection and scientific review](references_and_review.md) before preparing independently verifiable literature-observation plans. No question regeneration or A/B/C reruns are necessary.

## What is measured?

A is MCP only, B is MCP with the AstroAKD specialist instruction, and C is Web only. One hundred questions create up to 300 agent runs. **Completion, time and tool metrics are not scientific correctness.** Scientific accuracy requires independently verified gold answers.

**Figure commands are separate from execution.** `run-benchmark` saves agent runs; the subsequent `agent-report` command saves `mean_runtime.png`, `total_tokens.png`, `completed_runs.png`, `mean_mcp_events.png`, and `web_search_calls.png` to `datasets/reports/astroakd_100_v2/agents/`. To refresh plots, rerun `agent-report --name astroakd_100_v2 --output-dir datasets --replace`. For archive observations, `reference-report --name astroakd_100_v2 --output-dir datasets --replace` creates `response_times.png` and the other reference completeness figures under `datasets/reports/astroakd_100_v2/references/`. The current `agent-report` also generates question-aware automated archive-reference `match_rate.png` when there are automatically scorable complete reference records. It reports the scorable denominator and exclusions; it is not independently reviewed scientific accuracy.

Continue with [question generation](create_queries.md), [references](references_and_review.md), and [evaluation](evaluation_and_plots.md).

Frozen prompts: `instructions/astroakd/AstroAKD_Instruction.md` (arm B) and `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` (generation only).

To build the HTML documentation from the repository root: `make -C docs/sphinx html`.

## Match-rate figure and selective MCP-only retry

For a saved `astroakd_100_v2` dataset with single-call reference evidence, run `uv run --with matplotlib python -m benchmark agent-report --name astroakd_100_v2 --output-dir datasets --replace`. Alongside runtime and token plots this now creates `datasets/reports/astroakd_100_v2/agents/match_rate.png`, explicitly labeled **automated archive-reference agreement** on the currently evaluable denominator; read `automated_scoring_summary.json` for scorable/excluded counts. It is not verified scientific accuracy.

After a complete A/B/C run, `uv run python -m benchmark run-benchmark --name astroakd_100_v2 --output-dir datasets --retry-errors --dry-run` previews failed MCP-only tasks. Remove `--dry-run` and add `--with openai` to `uv run`, `--max-turns 16 --max-calls 20 --timeout 900 --task-timeout 2400` to execute **only those failed MCP-only tasks**. A separate diagnostic journal is created; the original 300 runs are preserved. See [A/B/C evaluation and plots](evaluation_and_plots.md).

## New generation policy

Version 0.6.7.11.10 performs agent-independent, reference-aware MCP prechecks **before** GPT question writing when `--with-reference-answers` is selected. It tries bounded Gaia/MAST/HEASARC/VizieR queries, rejects incomplete/oversized/null results and selects alternate target/radius combinations. Accepted slots are frozen in a checksum-protected feasibility plan so `--resume` keeps the same questions and MCP calls. A precheck is not an independently validated reference answer. If no feasible 100-question candidate mix is available, the command fails *before* GPT rather than silently creating unscorable questions. For your fresh study use `--name astroakd_100_v2` throughout; see [Question creation](create_queries.md).

If reference-aware probing stops before GPT writing, check
`datasets/generated/<name>_feasibility_progress.json` and run the same
`create-queries` command with `--resume`. This reuses saved MCP probes and
accepted slots. When an archive has no complete, bounded candidate, the
selector tries another archive and records the new distribution.
