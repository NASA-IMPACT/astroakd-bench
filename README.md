# AstroAKD-Bench

**AstroAKD-Bench** is a reproducible evaluation framework for AI agents that search astronomical data archives. It generates astronomy questions, collects reference answers through an independent [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp), runs controlled agent comparisons, and produces traceable scoring and performance reports.

**[Documentation](https://danehkar.github.io/astroakd-bench/)** · **[Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp)** · **[Changelog](CHANGELOG.md)**

## What it does

- **Generates reference-aware questions.** Candidate archive queries are checked for bounded, nonempty, manageable results before synthetic questions are finalized.
- **Collects independent archive evidence.** Reference queries run through Astroquery MCP separately from the agents being evaluated. Questions, references, and agent answers are stored independently.
- **Compares three agent configurations.** All three receive the same questions and use the same underlying LLM and baseline execution limits.
- **Scores structured astronomical answers.** Comparisons support coordinates, numerical tolerances, units, identifiers, repeated values, and archive/field associations. Results distinguish correct, partially correct, incorrect, abstained, and failed executions.
- **Preserves reproducibility.** Saved datasets, MCP traces, execution journals, checksums, and CSV/JSON reports support inspection and offline re-scoring.

### A/B/C evaluation design

| Arm | Agent configuration | Available tools |
| --- | --- | --- |
| **A — MCP only** | General-purpose LLM agent | Astroquery MCP |
| **B — AstroAKD** | Same LLM with [AstroAKD domain instructions](instructions/astroakd/AstroAKD_Instruction.md) | Astroquery MCP |
| **C — Web only** | General-purpose LLM agent | Web search; no Astroquery MCP |

The benchmark separates **execution completion**, **archive-reference answer agreement**, and **resource usage**. Automatic agreement with archive responses is not the same as independently verified scientific accuracy.

## Example questions and results

A [published example dataset](examples/README.md) provides **all 100 generated questions**, a convenient [question-and-reference CSV](examples/astroakd_100_v2/astroakd_100_v2_questions_and_references.csv), original single-call and multi-archive reference tables, A/B/C scoring summaries, and selected plots.

In this frozen study, **92 questions have complete archive-derived reference evidence** (80 single-call and 12 multi-archive); 8 literature-driven questions remain excluded. Strict automated reference agreement is **94.57% (A)**, **95.65% (B)**, and **14.13% (C)**. These are **not independently reviewed scientific accuracy rates**, and the one-question A/B difference is not conclusive.

| Strict reference-answer agreement (92 evaluable) | Mean runtime per run (original baseline) |
| --- | --- |
| ![Strict A/B/C agreement](examples/astroakd_100_v2/figures/match_rate.png) | ![A/B/C baseline mean runtime](examples/astroakd_100_v2/figures/mean_runtime.png) |

See [all example files and figures](examples/README.md) for per-question classifications, original input CSVs, and the limitations of automatic scoring.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- An OpenAI API key for synthetic question generation and A/B/C agent runs
- A separately running [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp)
- An ADS API credential configured on the MCP server when using `--require-ads`

### 1. Start the Astroquery MCP server (terminal 1)

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Keep the server running. Its default benchmark endpoint is `http://127.0.0.1:8000/mcp`. If using ADS literature queries, set `API_DEV_KEY` (or the server-supported `ADS_API_KEY`) in this terminal **before starting** the server. Do not commit credentials.

### 2. Install AstroAKD-Bench (terminal 2)

```bash
git clone https://github.com/danehkar/astroakd-bench.git
cd astroakd-bench
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast
```

Set `OPENAI_API_KEY` securely in the benchmark terminal before making model calls. For another MCP endpoint, configure `ASTROAKD_MCP_URL` and optionally `ASTROAKD_MCP_TOKEN` (distinct from the ADS credential).

For ADS-enabled question generation, check access first:

```bash
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

## Run a benchmark

The examples below create a **new** study named `astroakd_example_100` in `datasets/`. Use a different `--name` for each independent dataset; do not overwrite frozen experiments.

### 1. Generate 100 questions and collect available references

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_example_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

For 100 questions, the default design targets **60 archive-driven, 20 coordinate-driven, 12 multi-archive, and 8 literature-driven tasks**. The actual archive distribution can adapt to reference feasibility. `--with-reference-answers` enables bounded archive prechecks and collects eligible **single-call** reference evidence. Multi-step reference collection is a separate operation.

Interrupted generation can be continued with the same options plus `--resume`; keep the files in `datasets/generated/` so completed work is reused. See [question generation](docs/benchmark/create_queries.md) for feasibility limits and recovery details.

### 2. Collect or inspect reference answers

If questions were saved but single-call reference collection did not finish, **reuse the questions** rather than regenerating them:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_example_100 \
  --output-dir datasets \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

Use `--resume` for an interrupted collection; skip this command if the references were already collected. To summarize reference completeness and response times **offline**:

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_example_100 --output-dir datasets
```

For multi-archive reference tasks, collect evidence with a small pilot and resume:

```bash
uv run python -m benchmark collect-multistep-references \
  --name astroakd_example_100 --output-dir datasets \
  --timeout 900 --limit 5

uv run python -m benchmark collect-multistep-references \
  --name astroakd_example_100 --output-dir datasets \
  --timeout 900 --resume
```

Literature-driven tasks require independently supported links between publications and observations; candidate ADS citations or draft query templates alone are **not** complete reference answers. Tasks with incomplete evidence are excluded from scoring with explicit reasons. See [reference collection](docs/benchmark/references_and_review.md).

### 3. Run the A/B/C agents

Start with a five-question pilot before resuming the full experiment:

```bash
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_example_100 --output-dir datasets \
  --timeout 900 --task-timeout 2400 --limit 5

uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_example_100 --output-dir datasets \
  --timeout 900 --task-timeout 2400 --resume
```

A complete 100-question experiment records up to **300 agent runs**. The same questions, model, and baseline limits are used across arms; archive reference answers are not exposed to the evaluated agents.

### 4. Score saved answers and generate figures

These commands use saved evidence and runs; they do **not** call OpenAI or rerun archive queries:

```bash
# Question-aware answer scoring
uv run --with matplotlib python -m benchmark score-reference-answers \
  --name astroakd_example_100 --output-dir datasets

# A/B/C operational reports and figures
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_example_100 --output-dir datasets
```

Results include:

| Output | Purpose |
| --- | --- |
| `reports/<name>/automated/match_rate.png` | Strict archive-reference agreement across A/B/C |
| `reports/<name>/automated/accuracy_by_archive.png` | Agreement by archive |
| `reports/<name>/automated/accuracy_by_question_type.png` | Agreement by question type |
| `reports/<name>/automated/automated_scores_per_question.csv` | Per-question correctness, partial matches, and exclusions |
| `reports/<name>/agents/mean_runtime.png` | Mean runtime by agent configuration |
| `reports/<name>/agents/total_tokens.png` | Recorded token use by configuration |
| `reports/<name>/agents/completed_runs.png` | Execution completion, distinct from answer correctness |

Paths above are relative to `datasets/`; figures also have SVG equivalents. Use `--replace` on a reporting command to regenerate existing **reports**, without rerunning the experiment.

## Reproducibility and outputs

| Directory | Contents |
| --- | --- |
| `datasets/generated/` | Synthetic questions, task plans, and generation metadata |
| `datasets/validated/` | Independently collected MCP reference observations and multi-step evidence |
| `datasets/agent/` | Saved A/B/C responses, statuses, and tool traces |
| `datasets/reports/` | Offline scoring results, summaries, and plots |

Preserve the original question JSONL, reference evidence, and run journals when comparing scoring policies. For finalized runs with errors, `run-benchmark --retry-errors --dry-run` previews selective retries; actual retries are stored as a **separate diagnostic experiment** if execution limits change. See [evaluation and plots](docs/benchmark/evaluation_and_plots.md) for examples.

## Documentation

The [online documentation](https://danehkar.github.io/astroakd-bench/) covers:

- [Getting started](docs/benchmark/quickstart.md) and [installation](INSTALL.md)
- [Question generation](docs/benchmark/create_queries.md) and [ADS/MCP configuration](docs/benchmark/ads_and_mcp.md)
- [Reference evidence](docs/benchmark/references_and_review.md) and [A/B/C evaluation](docs/benchmark/evaluation_and_plots.md)
- [Python API](docs/benchmark/python_api.md)

Build the current HTML documentation locally with `make -C docs/sphinx clean` followed by `make -C docs/sphinx html`. The generated site appears under `docs/_build/html/`.

For the complete command list, run `uv run python -m benchmark --help`. See [CHANGELOG.md](CHANGELOG.md) for release history and [the benchmark-generation instructions](instructions/astroakd_bench/AstroAKD-Bench_Instruction.md) for question-design policy.
