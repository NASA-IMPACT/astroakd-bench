> **Historical project overview.** For current version `0.6.7.4`, default model, prompt locations, authentication and GPT-5.2 commands, use the [documentation index](../index.md) or [current quick-start](quickstart.md). Versioned descriptions below may refer to older milestones.

# AstroAKD-Bench

**Reproducible synthetic astronomical queries and evidence-based evaluation of AI data-discovery agents.**

AstroAKD-Bench is an **independent Python repository** for developing and evaluating agents that discover astronomical data through the [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp). That server is an **external service**, not this repository or the owner of this benchmark. AstroAKD-Bench generates natural-language astronomy tasks, executes reference archive queries via MCP, collects independent agent traces, and scores observable execution and a bounded set of claims.

**Current version: 0.6.4 — LLM_ASSISTED_SYNTHETIC_QUERY_GENERATION.** The `generate` default now uses OpenAI with workbook-derived instructions and MCP discovery. For API-free deterministic generation, use `--backend template`. The no-MCP alternative uses OpenAI Responses hosted `web_search`. The external MCP server is independent.

## Status and scope

| Milestone | Capability | Qualification |
| --- | --- | --- |
| 0.1.0 — LOCAL_MCP_CONNECTION | FastMCP HTTP connectivity, discovery and SIMBAD smoke | **ACCEPT** (laptop) |
| 0.2.0 — SYNTHETIC_QUERY_GENERATION | Deterministic 50-task dataset for five archives | **ACCEPT** (laptop) |
| 0.3.0 — REFERENCE_VALIDATION | Query real archives; preserve references, error evidence and journals | **ACCEPT** (laptop) |
| 0.4.0 — AGENT_EXECUTION_AND_TRACING | Optional OpenAI/external-agent execution and MCP traces | Implemented; live pilot identified routing issues |
| 0.4.1 — AGENT_TOOL_SELECTION_AND_RECOVERY_CLOSURE | Question-derived archive routing, recovery and query-evidence checks | **ACCEPT** (five-task laptop pilot) |
| **0.5.0 — AUTOMATED_EVALUATION_AND_SCORING** | Deterministic technical scoring, claim checks, readable JSON reports, root datasets | **Offline tests PASS; laptop requalification pending** |
| **0.6.0 — REPLAY_AND_BENCHMARK_RELEASE** | Offline fixture recording and replay | 5-task live-record/replay ACCEPT; ICRS mismatch found for reference fixture |
| **0.6.1 — SEMANTIC_REPLAY_ARGUMENT_CANONICALIZATION** | Default ICRS-frame replay matching and reusable Python API | Offline qualification PASS; laptop pending |

**What the scores mean.** The weighted 0–100 **technical evidence score** assesses archive/function selection, argument alignment, successful execution, reference-result consistency, and *limited* automated answer-claim checks. It is **not a general scientific answer-accuracy score**. Truncated responses, changing public archives, and unverified scientific assertions are explicitly flagged for independent review. Reference acceptance establishes structurally valid MCP data, not independently proven astrophysical ground truth.

## Separate local repositories

```text
AstroAKD-Bench/                         # THIS repository
├── README.md                           # Benchmark project overview
├── CHANGELOG.md                        # Benchmark versions only
├── pyproject.toml
├── benchmark/                          # Benchmark Python package
│   ├── cli.py
│   ├── generator.py
│   ├── validator.py
│   ├── agent_runner.py
│   ├── evaluator.py                      # NEW in 0.5.0
│   ├── formatting.py                     # NEW in 0.5.0
│   └── tests/
├── datasets/                            # Root-level output/input directory
│   ├── generated/
│   ├── validated/
│   ├── agent/
│   └── evaluation/
├── scripts/
│   └── migrate_datasets_0_5_0.py
└── docs/benchmark/

astroquery-mcp/                         # SEPARATE NASA IMPACT MCP service
└── server.py
```

The release includes the accepted generated and validated datasets at **root-level `datasets/`**. No `benchmark/datasets/` path is used for new runs. The Python `benchmark/` directory contains implementation code only. The original accepted dataset bytes and SHA-256 hashes are unchanged by this move.

## Install and start

Use Python 3.11+ and [uv](https://docs.astral.sh/uv/). In the **AstroAKD-Bench checkout**:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m unittest discover -s benchmark/tests -v
```

In a **different terminal, from the separate `astroquery-mcp` repository**, start its own server with its own environment:

```bash
cd /path/to/astroquery-mcp
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Return to the **AstroAKD-Bench** directory for all following commands. Override `http://127.0.0.1:8000/mcp` with `--mcp-url` or `ASTROAKD_MCP_URL` if needed.

### Connection check — 0.1.0

```bash
uv run python -m benchmark doctor --fast --json-format pretty
uv run python -m benchmark doctor --smoke --timeout 180 --json-format pretty
```

### Generate queries — 0.2.0

```bash
uv run python -m benchmark generate \
  --backend template \
  --count 50 --seed 42 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --output datasets/generated/synthetic_queries.jsonl \
  --report datasets/generated/generation_report.json \
  --json-format pretty
```

Only run this if intentionally regenerating a dataset. The distributed 50-task seed=42 dataset is already accepted; `--replace` would intentionally replace an existing file. Generation makes **no astronomy archive queries** and **no LLM calls**.

### Validate reference results — 0.3.0

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_queries.jsonl \
  --strict-accepted-020 \
  --limit 5 --attempts 2 --delay 2 --timeout 180 \
  --output datasets/validated/reference_answers.jsonl \
  --report datasets/validated/validation_report.json \
  --json-format pretty
```

Resume an interrupted validation with `--resume` and without `--limit`. Existing accepted reference data is already included in the package, so **do not revalidate solely to run scoring**. Live validation requires network access to the archives.

### Execute the agent — 0.4.1 / 0.5.0

An OpenAI agent is optional. Supply `OPENAI_API_KEY` privately through your shell environment and enable the optional SDK:

```bash
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --limit 5 \
  --max-turns 8 --max-calls 12 \
  --output datasets/agent/openai_050_runs.jsonl \
  --report datasets/agent/openai_050_report.json \
  --json-format pretty
```

Run a separate external AstroAKD implementation with `--agent external --adapter package.module:run`, provided the adapter routes calls through the tracing gateway. `--agent echo` tests only the harness, **not agent performance**. Existing runs are protected from overwrite: use `--resume` for a compatible incomplete run or `--replace` to discard it intentionally.

### Evaluate recorded agent evidence — 0.5.0

**Scoring does not call an LLM or MCP server.** This example scores the frozen five-task 0.4.1 OpenAI pilot included in the package:

```bash
uv run python -m benchmark evaluate \
  --strict-accepted-020 \
  --runs datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --output datasets/evaluation/openai_041_scores_recheck.jsonl \
  --report datasets/evaluation/openai_041_report_recheck.json \
  --csv datasets/evaluation/openai_041_scores_recheck.csv \
  --json-format pretty
```

To score a new 0.5.0 run, set `--runs datasets/agent/openai_050_runs.jsonl` after a completed run, or use its `.progress.jsonl` journal for a partial pilot. For repeated scoring of the same destination, add `--replace` only when intended.

Scores are divided into archive selection (20), function selection (15), parameter correctness (25), successful MCP execution (15), reference row-count agreement (15) and limited answer-claim checks (10). Exact scientific correctness remains marked `INDEPENDENT_REVIEW_REQUIRED`. See [scoring details](evaluation_and_scoring.md).

## Readable JSON on a laptop

Choose `--json-format compact` (default) or `--json-format pretty` on the commands above. This changes the **console output and summary `.json` reports**. Machine-readable `.jsonl` datasets, trace journals, and score records remain **one compact JSON object per line**, preserving JSONL compatibility and the accepted input hashes.

For an easy-to-read view of existing JSONL without modifying the original:

```bash
uv run python -m benchmark inspect \
  --input datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --limit 1 --json-format pretty \
  --output datasets/evaluation/pilot_inspection.json
```

`inspect` converts a bounded preview into readable JSON with a `records` array; it does **not** reformat or overwrite source files. `--limit` is between 1 and 100. For large archive tables, use a small limit.

## Dataset evidence and accepted baselines

On 2026-10-13, 50 candidate queries were generated and 50 structurally accepted MCP references were obtained: SIMBAD 10, MAST 10, Gaia 10, VizieR 10, HEASARC 8 nonempty plus 2 valid empty. The validated references consist of **48 nonempty and 2 empty results**. These outputs were checked on the user's laptop.

- Accepted candidate SHA-256: `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`
- Accepted reference SHA-256: `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`

The accepted 0.4.1 five-task OpenAI pilot observed **five successful MCP executions and zero rejected calls**. Version 0.5.0's offline scoring of that recorded pilot gives **94/100 mean technical evidence**, with 3 technical PASS and 2 REVIEW (including truncated Gaia output). **This is not astrophysical answer accuracy**, and 0.5.0 has not yet been host-qualified on the user's laptop.

### Migrating an older checkout

If your older AstroAKD-Bench checkout has `benchmark/datasets/` and no root-level `datasets/`, execute:

```bash
uv run python scripts/migrate_datasets_0_5_0.py
```

The script **refuses to merge** when both directories exist. Move or reconcile those directories manually in that case; never overwrite the accepted input files accidentally. The migration checks known frozen SHA-256 values before moving accepted files.

## Safety, reproducibility and limitations

- Use the MCP server on `127.0.0.1` rather than exposing dynamic archive operations publicly.
- Queries use an explicit read-only allowlist and conservative limits. Public archives can change or become unavailable.
- Agent context excludes reference calls and reference answers; scores operate on previously saved artifacts.
- A model answer plus successful MCP transport is not proof of astronomical correctness. Result truncation and possible archive drift are review conditions.
- LLM-generated natural-language variations, comprehensive scientific statement verification, and offline MCP record/replay are **not yet implemented**.
- AstroAKD-Bench does **not** claim authorship of the NASA IMPACT Astroquery MCP server or attribute its contributors to the benchmark.

See [CHANGELOG.md](../../CHANGELOG.md) for cumulative release history and [docs/benchmark](./) for implementation details. **Every new release updates the root README, root CHANGELOG, package metadata, CLI examples, and relevant docs together.**

## Semantic replay and reusable Python API (0.6.1)

See [0.6.1 MCP record/replay](replay_and_release.md) and the [reusable Python API guide](python_api.md) for custom astronomical seed lists, programmatic query generation, reference validation, independent agent runs, scoring and offline replay. The benchmark remains independent of the NASA IMPACT Astroquery MCP server repository.


## 0.6.2: Human-readable CSV and pretty JSON exports

Canonical `.jsonl` stays **one compact JSON object per line**. Pass
`--csv-output PATH.csv` to create an inspection table and `--pretty-output
PATH.json` to save a complete indented JSON array. `--json-format pretty`
alone affects only terminal output and `.json` summary reports; it does **not**
change canonical JSONL encoding. Saved CSV/pretty views do not replace JSONL
in API calls, validation inputs or frozen-hash checks.

For generated queries:

```bash
uv run python -m benchmark generate \
  --backend template \
  --count 50 --seed 123 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --output datasets/generated/my_50_queries.jsonl \
  --csv-output datasets/generated/my_50_queries.csv \
  --pretty-output datasets/generated/my_50_queries_pretty.json \
  --report datasets/generated/my_50_report.json \
  --json-format pretty
```

For live validation of this **new seed=123 dataset**, start conservatively:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/my_50_queries.jsonl \
  --limit 1 --attempts 1 --timeout 30 --delay 0 \
  --output datasets/validated/my_50_references.jsonl \
  --csv-output datasets/validated/my_50_references.csv \
  --pretty-output datasets/validated/my_50_references_pretty.json \
  --report datasets/validated/my_50_validation_report.json \
  --json-format pretty
```

The validator reports progress on **stderr** at preflight, START, WAITING
(every 15 seconds), and DONE, so a slow remote archive cannot silently
appear idle. It saves completed-task results into an fsynced `.progress.jsonl`
journal. If interrupted, use `--resume` with the same input and output names,
and remove `--limit`. Do not use `--strict-accepted-020` for new seeds.
CSV and pretty JSON views are updated after each successful command invocation,
including pilot runs, and contain only processed records. The final canonical
reference `.jsonl` is published when all input tasks have dispositions.
