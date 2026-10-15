# AstroAKD-Bench

**Reproducible astronomical data-discovery benchmarks, source-anchored answers,
and three-arm AI-agent evaluation.**

AstroAKD-Bench is an **independent Python project** that produces synthetic
astronomical questions, collects archived reference data through an external
[Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp), runs AI
agents and exports reproducible answer comparisons, scores and performance plots.
**AstroAKD** is the *agent being evaluated*; **AstroAKD-Bench** is the *benchmark*;
**astroquery-mcp** is a *separate MCP service*. They are not interchangeable.

**Current version: `0.6.7.10` — archive-specific reference budgets, consolidated answer-review CSVs, and offline scientific review / gold finalization.**
[Documentation index](docs/index.md) · [Current quick-start](docs/benchmark/quickstart.md)
· [Change history](CHANGELOG.md) · [Instruction layout](instructions/README.md)

## Quick start

Install Python 3.11+ and [uv](https://docs.astral.sh/uv/). Work from the
AstroAKD-Bench repository root:

```bash
uv sync
uv run python -m benchmark --version
```

### Run the external Astroquery MCP server locally

The benchmark is a client of NASA IMPACT's
[`astroquery-mcp`](https://github.com/NASA-IMPACT/astroquery-mcp), not the
server itself. In **terminal 1**, clone that separate repository and launch it:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Leave this terminal running. The local endpoint is
`http://127.0.0.1:8000/mcp`. Bind to loopback rather than exposing the
server's dynamic archive executor to the public Internet. In **terminal 2**,
from your AstroAKD-Bench repository root, check connectivity:

```bash
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN
uv run python -m benchmark doctor --fast --json-format pretty
```

`doctor` connects to an **already running** compatible MCP service. To use a
remote authenticated endpoint instead, configure:

```bash
# Default localhost (no authentication)
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN

# OR remote HTTPS endpoint
export ASTROAKD_MCP_URL='https://coming-gray-slug.fastmcp.app/mcp'
export ASTROAKD_MCP_TOKEN='REPLACE_WITH_YOUR_TOKEN'
```

Endpoint priority: explicit `--mcp-url` / `--mcp-server`, then
`ASTROAKD_MCP_URL`, then `http://127.0.0.1:8000/mcp`.
Authentication: explicit `--mcp-token` / `--mcp-server-token`, then
`ASTROAKD_MCP_TOKEN`, then no token. Generic `MCP_URL` and `MCP_TOKEN` are **ignored**.
An unreachable server returns a diagnostic naming the selected URL, never the
secret. Prefer environment variables over command-line tokens. See
[MCP configuration and security](docs/benchmark/mcp_endpoint_auth_0_6_7_3.md).

## Repository layout: documentation vs. instructions

```text
AstroAKD-Bench/
├── benchmark/                         # Source code, command-line interface, tests
├── datasets/                          # Frozen input sets, reference oracles, runs, reports
├── instructions/                      # Prompts and agent instructions, NOT user docs
│   ├── astroakd/
│   │   └── AstroAKD_Instruction.md    # Specialist instruction: arm B only
│   └── astroakd_bench/
│       └── AstroAKD-Bench_Instruction.md       # Synthetic-question authoring
├── docs/                              # Sphinx/MyST documentation sources
│   ├── sphinx/Makefile                 # Build documentation from any directory
│   ├── conf.py                        # Sphinx configuration
│   ├── index.md                       # Documentation home
│   ├── benchmark/                     # Current and versioned technical guides
│   └── history/                       # Archived historical README
├── scripts/                           # Supporting utilities
├── README.md                           # Concise current landing page
├── CHANGELOG.md                        # Benchmark release history
└── pyproject.toml
```

The **AstroAKD** specialist instruction belongs to *the evaluated agent*, not
to synthetic query generation. The **AstroAKD-Bench** instruction controls how
candidate questions are authored, not how the tested agent answers them. They
are separate files under `instructions/` and are **byte-identical** to their
0.6.7.3 predecessors. See [instruction migration](instructions/README.md).

The old `docs/agent/AstroAKD_Instruction.md` and
`docs/benchmark/llm_generation_instructions_v1.md` paths have moved; update
any shell commands or scripts using those paths. Version 0.6.7.5 additionally
renamed the generator prompt to `AstroAKD-Bench_Instruction.md`. The `docs/` directory now
contains only documentation and preserved technical background.

## Generate synthetic questions **with real reference answers**

AstroAKD-Bench 0.6.7.10 retains the integrated, explicit
`generate --with-reference-answers` workflow. The question-writing model
**never supplies reference answers**. Instead the benchmark executes each
candidate's allowed read-only Astroquery MCP call, keeps actual serialized
archive tables and provenance, and exports field observations in CSV.
These are **unreviewed reference snapshots**, not independently verified
scientific ground truth. Collection can take considerably longer than question
writing and may encounter empty or unavailable archive responses.

Start the [local MCP server](#start-an-independent-local-astroquery-mcp-server)
first, and configure `OPENAI_API_KEY`. Use fresh filenames:

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --instructions --mcp \
  --model gpt-5.2 --count 100 --batch-size 5 --seed 20261016 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --with-reference-answers \
  --output datasets/generated/synthetic_100_with_refs.jsonl \
  --csv-output datasets/generated/synthetic_100_with_refs.csv \
  --report datasets/generated/synthetic_100_with_refs_report.json \
  --json-format pretty
```

Reference outputs are automatically written under `datasets/validated/`:
`synthetic_100_with_refs_references.jsonl` (complete only when all 100 have
been attempted), `synthetic_100_with_refs_references.jsonl.progress.jsonl`
(fsynced per-task journal), `synthetic_100_with_refs_references.csv` (questions,
status, matching field observations), and the corresponding references report.
Use `--reference-limit 5` to collect a five-task pilot, then finish with a
**separate** `validate --resume` command using the same inputs and limits.
Do not rerun `generate` for resumption.

**For your already-generated 100 questions**, do **not** call `generate`
again. Collect their actual archive responses directly:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_100_gpt52.jsonl \
  --output datasets/validated/synthetic_100_gpt52_references.jsonl \
  --csv-output datasets/validated/synthetic_100_gpt52_references.csv \
  --report datasets/validated/synthetic_100_gpt52_references_report.json \
  --attempts 2 --delay 2 --timeout 180 \
  --json-format pretty
```

The CSV contains `reference_answer_values_json` and
`reference_answer_status`. Values are extracted only when an expected column
is genuinely present; no model-written answer is substituted for missing
archive evidence. Empty, truncated and rejected responses remain visible for
review. A strict 100-question scorable oracle additionally requires sufficient
nonempty unambiguous evidence; do not interpret a `generate`/`validate` `PASS`
as 100 scientifically verified answers. See the
[100-query workflow](docs/benchmark/new_100_query_workflow.md).

## Scientific review of the completed 100-question reference collection (0.6.7.10)

The generated question CSV **does not** contain reference values. The validated
reference CSV has `reference_answer_values_json` and
`reference_answer_status`, and now has an automatically generated companion
`*_references_review.csv`: **one row per question** with its text, archive,
target, observed answer preview, cardinality, ambiguity and review flags.

For the existing 100 finished references, run this **offline**; no new OpenAI
or MCP calls are needed:

```bash
uv run python -m benchmark reference-review-draft \
  --tasks datasets/generated/synthetic_100_with_refs.jsonl \
  --references datasets/validated/synthetic_100_with_refs_references.jsonl \
  --output datasets/gold/synthetic_100_review_draft.jsonl \
  --csv-output datasets/gold/synthetic_100_science_review.csv \
  --report datasets/gold/synthetic_100_review_report.json \
  --json-format pretty
```

The editable JSONL is compatible with `gold-finalize`, **after independent
human review**, author attribution and two independent source citations.
Multi-row responses and truncated archive subsets are not automatically
scorable. Archive-specific `--archive-timeouts mast=60,...`,
`--archive-attempts mast=1,...`, and `--reference-deadline 70` can be supplied
to *new* `validate`/reference-enabled `generate` runs without changing the
prior default policy. Refer to the
[0.6.7.10 scientific-review guide](docs/benchmark/archive_policy_scientific_review_0_6_7_10.md).

## Current 50-question GPT-5.2 experiment

The scorable test set contains **50 narrowly answerable questions**, derived
from **42 accepted single-call archive reference responses** across SIMBAD,
MAST, HEASARC, Gaia and VizieR. Each question has a frozen expected field value,
units/tolerance where applicable, and provenance. It measures **agreement with
an archive snapshot**, not independently verified scientific truth.

| Arm | Tools | Specialist AstroAKD instruction |
| --- | --- | --- |
| **A — MCP only** | Astroquery MCP | No |
| **B — MCP + Instruction** | Same Astroquery MCP | Yes |
| **C — Web only** | OpenAI web search | No |

All three arms run `gpt-5.2`. Gold/reference answers are **never provided to the
agent runner**. The original 50-question mixed dataset (32 archive, 10
coordinate, 8 literature) is retained separately, and its literature-derived
scientific truth is not implied by the scorable dataset.

The initial five-question pilot yielded **snapshot matches** of A **5/5**, B
**5/5**, C **1/5**; these are **not** independently verified science accuracy,
and were only 5/50 questions. Its mean runtimes were **21.46, 7.58 and 16.95
seconds** and recorded token totals **276,739, 308,724 and 101,552**,
respectively. The full 150-run GPT-5.2 experiment subsequently completed on the host:
A **48/50**, B **49/50**, and C **12/50** source-snapshot matches (run-journal
SHA-256 `58824a2b71e7063b550c3fa16592f70307f11f6ace7293bf7fe81a47c334daaf`).
These are **not** independently reviewed scientific accuracy values.

### Run all 50 questions (new experiment; no `--resume`)

With `OPENAI_API_KEY` configured and the external MCP endpoint running,
use **fresh output paths** for a new experiment. The three arms use GPT-5.2
and the same tasks and budgets:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 \
  --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_fresh_runs.jsonl \
  --report datasets/agent/gpt52_fresh_report.json \
  --json-format pretty
```

The command runs 50 questions × 3 arms = **150 executions**. The example
uses fresh names because the release already contains an earlier GPT-5.2 pilot
journal. If the output exists, the runner refuses to overwrite it.

### Pilot run (`--limit 5`)

To examine five questions per arm before executing all 50, use a **different
fresh output prefix**:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --limit 5 \
  --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_new_pilot_runs.jsonl \
  --report datasets/agent/gpt52_new_pilot_report.json \
  --json-format pretty
```

The pilot writes `gpt52_new_pilot_runs.jsonl.progress.jsonl` containing 15
entries. Partial progress is deliberately marked `PARTIAL`; it does not
represent success on the full dataset.

### Resume a partial pilot (`--resume`)

Use the **same** task file, model, instruction *content*, MCP URL, budgets,
output path and report path as the original limited run; **remove `--limit`**:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 \
  --max-turns 8 --max-calls 12 \
  --max-tool-bytes 262144 --timeout 180 --task-timeout 900 \
  --output datasets/agent/gpt52_new_pilot_runs.jsonl \
  --report datasets/agent/gpt52_new_pilot_report.json \
  --resume --json-format pretty
```

Resume skips already recorded task/arm pairs. A completed run publishes the
final `.jsonl`, and an interrupted run remains in the `.progress.jsonl` journal.
To resume the existing historical GPT-5.2 pilot instead, use the original
`scorable_50_gpt52_runs.jsonl` output prefix and match its saved manifest.
**Do not** use `--replace` to resume or change the endpoint during one run.

### Score and generate CSV reports / plots

**After the run** (no previous scoring required), use `score-scorable` to
compare actual replies against the frozen reference-answer snapshot:

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
  --mcp-calls-csv datasets/reports/gpt52_fresh_mcp_calls.csv \
  --mcp-tool-frequency-csv datasets/reports/gpt52_fresh_mcp_tool_frequency.csv \
  --overall-csv datasets/reports/gpt52_fresh_overall_results.csv \
  --mcp-ab-summary-csv datasets/reports/gpt52_fresh_mcp_ab_summary.csv \
  --paired-questions-csv datasets/reports/gpt52_fresh_paired_questions.csv \
  --paired-summary-csv datasets/reports/gpt52_fresh_paired_summary.csv \
  --mismatch-audit-csv datasets/reports/gpt52_fresh_mismatch_audit.csv \
  --paired-plots-dir datasets/reports/gpt52_fresh_paired_plots \
  --plots-dir datasets/reports/gpt52_fresh_plots \
  --report datasets/reports/gpt52_fresh_scores.json \
  --json-format pretty
```

This command reads the **fresh full-run** example above. For the five-question
pilot, point `--runs` to
`datasets/agent/gpt52_new_pilot_runs.jsonl.progress.jsonl` and use different
report destinations. When refreshing **existing** reports, add `--replace`;
it is not required on the first score. The offline scorer preserves wrong,
blank, unstructured and abstained answers and produces A/B/C match-rate,
mean-runtime and total-token bar plots, plus **average MCP tool calls** and **per-function MCP call frequencies** for arms A/B, in PNG and SVG. Reference matches are
**not independently verified scientific accuracy**. See the
[reporting guide](docs/benchmark/three_arm_detailed_reporting_0_6_7_1.md) and
[per-query MCP tool-call reporting](docs/benchmark/mcp_tool_call_reporting_0_6_7_7.md). The 0.6.7.8 extension also exports a **combined A/B/C overall-results CSV**,
**A/B MCP summary CSV**, 50-row question-paired answer/efficiency table,
three-row paired comparison summary with exact McNemar testing and
fixed-seed paired bootstrap intervals, and an independently reviewable
mismatch audit. Four supplementary paired PNG/SVG figures are saved separately;
see the [paired-analysis guide](docs/benchmark/paired_analysis_0_6_7_8.md).
For a full completed journal stored in an older release directory, supply
its **absolute path** to `--runs`; do not accidentally score the bundled
15-record pilot. Model/MCP replay is not required.

## HTML documentation (Sphinx + MyST)

From the repository root, build all current and historical Markdown guides:

```bash
make -C docs/sphinx html
```

This installs the optional documentation dependencies through `uv` and writes
`docs/_build/html/index.html`. Run `make -C docs/sphinx clean` to delete build outputs. If
Sphinx is already installed, use `make -C docs/sphinx html SPHINXBUILD=sphinx-build`.
The build Makefile lives at `docs/sphinx/Makefile`; the Sphinx configuration lives in `docs/conf.py`; see the
[documentation build guide](docs/benchmark/documentation_build.md).

[0.6.7.10 offline qualification](QUALIFICATION_0_6_7_10.md) and [0.6.7.10 conversation handoff](CONVERSATION_HANDOFF_THROUGH_0_6_7_10.md) document the new review safeguards and remaining live-host checks.

## Synthetic questions, evidence and scientific qualification

Synthetic generation may use deterministic templates, MCP-backed OpenAI
question authoring, or web-only research. Question-generation instructions
are read automatically from
[`instructions/astroakd_bench/AstroAKD-Bench_Instruction.md`](instructions/astroakd_bench/AstroAKD-Bench_Instruction.md)
when enabled, and can be replaced with `--instructions-file`. Candidate
questions are not verified scientific answers until separately checked.

`validate` collected **42/42 structurally accepted, nonempty archive responses**
for the old single-call task subset. Scientific gold approval is a separate
manual and archival-verification workflow (`gold-draft`, `gold-finalize`).
Reference-snapshot agreement (`score-scorable`), operational completion and
scientific accuracy must not be conflated.

Read [experimental methods and limitations](docs/benchmark/experimental_methods.md),
[the generator guide](docs/benchmark/llm_generation_0_6_4.md),
[the scientific-gold workflow](docs/benchmark/gold_reference_and_three_arm_0_6_6.md),
and [the Python API](docs/benchmark/python_api.md).

## Testing and release history

```bash
uv run python -m unittest discover -s benchmark/tests -q
```

Offline tests cover data/agent separation, resume integrity, MCP configuration,
answer scoring and report outputs. Online/OpenAI/remote MCP acceptance requires
running the corresponding workflows on your own host; unit tests alone do not
qualify a remote service or scientifically validate the oracle.

- [Documentation index](docs/index.md)
- [0.6.7.4 installation and migration notes](INSTALL_ASTROAKD_BENCH_0_6_7_4.md)
- [0.6.7.4 qualification record](QUALIFICATION_0_6_7_4.md)
- [Changelog](CHANGELOG.md) and [historical README (0.6.7.3)](docs/history/README_0_6_7_3.md)
