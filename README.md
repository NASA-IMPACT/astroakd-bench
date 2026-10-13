# AstroAKD-Bench

**Reproducible synthetic astronomical queries and evidence-based evaluation of AI data-discovery agents.**

AstroAKD-Bench is an **independent Python repository** for developing and evaluating agents that discover astronomical data through the [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp). That server is an **external service**, not this repository or the owner of this benchmark. AstroAKD-Bench generates natural-language astronomy tasks, executes reference archive queries via MCP, collects independent agent traces, and scores observable execution and a bounded set of claims.

**Current version: 0.6.1 — SEMANTIC_REPLAY_ARGUMENT_CANONICALIZATION.** The benchmark works on a local laptop. The server normally runs at `http://127.0.0.1:8000/mcp`; only the agent execution mode `--agent openai` needs the OpenAI API. No OpenAI key is needed to generate, validate, inspect, or score saved runs.

## Status and scope

| Milestone | Capability | Qualification |
| --- | --- | --- |
| 0.1.0 — LOCAL_MCP_CONNECTION | FastMCP HTTP connectivity, discovery and SIMBAD smoke | **ACCEPT** (laptop) |
| 0.2.0 — SYNTHETIC_QUERY_GENERATION | Deterministic 50-task dataset for five archives | **ACCEPT** (laptop) |
| 0.3.0 — REFERENCE_VALIDATION | Query real archives; preserve references, error evidence and journals | **ACCEPT** (laptop) |
| 0.4.0 — AGENT_EXECUTION_AND_TRACING | Optional OpenAI/external-agent execution and MCP traces | Implemented; live pilot identified routing issues |
| 0.4.1 — AGENT_TOOL_SELECTION_AND_RECOVERY_CLOSURE | Question-derived archive routing, recovery and query-evidence checks | **ACCEPT** (five-task laptop pilot) |
| **0.5.0 — AUTOMATED_EVALUATION_AND_SCORING** | Deterministic technical scoring, claim checks, readable JSON reports, root datasets | **Offline tests PASS; laptop requalification pending** |
| **0.5.1 — PRETTY_SCORE_EXPORT_CLOSURE** | Optional saved, indented JSON array of every per-task score (`--pretty-output`) | **Offline tests PASS; user's saved 0.5.1 scores verified** |
| **0.6.0 — REPLAY_AND_BENCHMARK_RELEASE** | Frozen offline MCP fixtures, live recording and reproducible replay | **5-task laptop live-record/replay ACCEPT; generic reference replay found an ICRS mismatch** |
| **0.6.1 — SEMANTIC_REPLAY_ARGUMENT_CANONICALIZATION** | ICRS default-aware fixture lookup and public Python workflow API | **Offline qualification PASS; laptop replay pending** |

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
│   ├── formatting.py
│   ├── replay.py                         # Semantic ICRS-aware offline lookup
│   ├── api.py                            # Reusable Python workflow facade
│   └── tests/
├── datasets/                            # Root-level output/input directory
│   ├── generated/
│   ├── validated/
│   ├── agent/
│   ├── evaluation/
│   └── replay/                           # Recorded or reference MCP fixtures
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

### Evaluate recorded agent evidence — 0.5.1

**Scoring does not call an LLM or MCP server.** This example scores the frozen five-task 0.4.1 OpenAI pilot included in the package:

```bash
uv run python -m benchmark evaluate \
  --strict-accepted-020 \
  --runs datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --output datasets/evaluation/openai_041_scores_recheck.jsonl \
  --report datasets/evaluation/openai_041_report_recheck.json \
  --csv datasets/evaluation/openai_041_scores_recheck.csv \
  --pretty-output datasets/evaluation/openai_041_scores_recheck_pretty.json \
  --json-format pretty
```

To score a new 0.5.1 run, set `--runs datasets/agent/openai_050_runs.jsonl` after a completed run, or use its `.progress.jsonl` journal for a partial pilot. For repeated scoring of the same destination, add `--replace` only when intended.

Scores are divided into archive selection (20), function selection (15), parameter correctness (25), successful MCP execution (15), reference row-count agreement (15) and limited answer-claim checks (10). Exact scientific correctness remains marked `INDEPENDENT_REVIEW_REQUIRED`. See [scoring details](docs/benchmark/evaluation_and_scoring.md).

## Offline archive replay — 0.6.1

**No local MCP server or astronomical archive connection is needed to replay** a
previously captured tool response. The OpenAI agent still requires its own API
connection; use `--agent external` with a locally running model to avoid that.
The `echo` agent is only a harness check and performs no astronomical calls.

Create a fixed 50-call fixture from the accepted reference results **without
network traffic** (this file is also supplied in the release):

```bash
uv run python -m benchmark build-fixtures \
  --strict-accepted-020 \
  --output datasets/replay/reference_fixtures.json \
  --json-format pretty
```

Use it to replay an AI agent's matching MCP calls, again without contacting the
MCP server. Record and run files are separate; use unique output names:

```bash
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --mcp-mode replay \
  --fixtures datasets/replay/reference_fixtures.json \
  --strict-accepted-020 --limit 5 \
  --output datasets/agent/openai_061_replay_runs.jsonl \
  --report datasets/agent/openai_061_replay_report.json \
  --json-format pretty
```

**Replay identity rule (0.6.1):** exact tool and argument matching is tried
first. For allowlisted sky-coordinate query functions only, replay also treats
an explicitly written `"frame": "icrs"` as equivalent to an omitted ICRS
frame. Sky coordinates, search radius, catalog, function name, and all other
arguments must remain identical; changed calls receive `OFFLINE_REPLAY_MISS`.
This uses a lookup-only semantic index: it **does not rewrite original fixture
keys, payloads or integrity hashes** and never queries live archives. This is essential to distinguish tool-selection failures from
missing fixture coverage. The reference-derived bootstrap catalog describes
safe tool schemas; it is not a captured, version-exact MCP server catalog.
If an agent relies on method introspection or makes different calls, record a
live session to capture them:

```bash
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --mcp-mode record \
  --fixtures datasets/replay/live_recording.json \
  --strict-accepted-020 --limit 5 \
  --output datasets/agent/openai_060_record_runs.jsonl \
  --report datasets/agent/openai_060_record_report.json
```

The `record` mode requires your live MCP service. It captures the actual tool
catalog and permitted query responses in a persistent, integrity-checked JSON
file after each completed call. Replay uses the same `--fixtures` path and the
recorded call signatures, but a **different** agent output/report path. Do not
share fixtures without reviewing them: they may contain astronomical query
parameters, archive metadata or other source-derived content. See
[record/replay documentation](docs/benchmark/replay_and_release.md).

Benchmark runs in `live`, `record` and `replay` modes remain distinct in their
manifests. Resume is allowed only with the original inputs, agent, routing
policy, mode and fixture identity. A replay fixture cannot be modified without
breaking its integrity check. Neither fixture replay nor deterministic scoring
makes LLM generation deterministic; fix the model/temperature/seed separately
when supported by your agent provider.

## Reusable Python API — 0.6.1

AstroAKD-Bench has a supported programmatic entrypoint:

```python
import asyncio
from benchmark.api import AstroAKDBench

bench = AstroAKDBench(root=".", mcp_url="http://127.0.0.1:8000/mcp")

async def main():
    # Requires the separate NASA IMPACT Astroquery MCP server for discovery.
    # Does NOT execute astronomical queries or require an LLM.
    report = await bench.generate_queries(
        count=20, seed=123, modules=("simbad", "mast"),
        output="datasets/generated/my_questions.jsonl",
        report="datasets/generated/my_generation_report.json",
    )
    print(report["dataset_sha256"])

asyncio.run(main())

# Fully offline: verify a saved fixture (no MCP server or LLM required).
store = bench.load_fixtures("datasets/replay/reference_fixtures.json")
print(len(store.entries), store.fingerprint)
```

The `AstroAKDBench` facade also provides `validate_queries(...)`,
`run_agent(...)`, `evaluate_agent(...)`, `build_fixtures(...)`, and
`load_records(...)`. It delegates to the same checked code paths as the CLI,
with explicit output paths, non-overwriting defaults, independent agent
traces and reference isolation. For notebook examples, custom seeds/templates,
programmatic scoring, agent adapters, error handling and offline replay, see
**[Python API and extension guide](docs/benchmark/python_api.md)**.

**Custom synthetic questions:** the current generator uses curated seeds and
read-only archive-specific templates; it is not an arbitrary text-to-Astroquery
engine. To add a new template, update the seed/template definitions and
corresponding safe signatures, add reproducibility tests, and then validate
new candidates on live archives. Never modify the frozen 50-task accepted
baseline just to create a new experiment.

## Readable JSON on a laptop

Choose `--json-format compact` (default) or `--json-format pretty`. This changes the **console output and summary `.json` reports**. It does not change `.jsonl` files: they must contain exactly one compact JSON object per line to remain stream-friendly and to preserve accepted dataset hashes.

**New in 0.5.1:** `benchmark evaluate --pretty-output datasets/evaluation/scores_pretty.json` writes an **additional, complete, indented JSON array** of the same per-task score objects, saved on disk. This works with either `--json-format compact` or `--json-format pretty` and does not call a server or an LLM. The pretty output path must end in `.json`, be distinct from all other input/output paths, and will not be overwritten unless you explicitly provide `--replace`. The resulting `.json` is separate from the normal summary `.json` report and the canonical `.jsonl` score stream.

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

The accepted 0.4.1 five-task OpenAI pilot observed **five successful MCP executions and zero rejected calls**. Version 0.5.0/0.5.1 scoring of that recorded pilot gives **94/100 mean technical evidence**, with 3 technical PASS and 2 REVIEW (including truncated Gaia output). **This is not astrophysical answer accuracy**. The uploaded 0.5.1 scores and pretty export were checked on the laptop. Version 0.6.0 live-record/replay with a live-captured fixture was also verified (5/5 successful with identical recorded and replayed responses). Version 0.6.1 addresses the separate reference-derived fixture mismatch; its live-laptop acceptance is pending.

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
- LLM-generated natural-language variations and comprehensive scientific statement verification are **not yet implemented**. Offline MCP replay is implemented, but unsupported calls fail closed and the LLM itself is not necessarily offline.
- AstroAKD-Bench does **not** claim authorship of the NASA IMPACT Astroquery MCP server or attribute its contributors to the benchmark.

See [CHANGELOG.md](CHANGELOG.md) for cumulative release history and [docs/benchmark](docs/benchmark/) for implementation details. **Every new release updates the root README, root CHANGELOG, package metadata, CLI examples, and relevant docs together.**
