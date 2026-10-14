# AstroAKD-Bench

**Reproducible astronomical data-discovery benchmarks, source-anchored answers,
and three-arm AI-agent evaluation.**

AstroAKD-Bench is an **independent Python project** that produces synthetic
astronomical questions, collects archived reference data through an external
[Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp), runs AI
agents and exports reproducible answer comparisons, scores and performance plots.
**AstroAKD** is the *agent being evaluated*; **AstroAKD-Bench** is the *benchmark*;
**astroquery-mcp** is a *separate MCP service*. They are not interchangeable.

**Current version: `0.6.7.4` — documentation and instruction-file separation.**
[Documentation index](docs/index.md) · [Current quick-start](docs/benchmark/quickstart.md)
· [Change history](CHANGELOG.md) · [Instruction layout](instructions/README.md)

## Quick start

Install Python 3.11+ and [uv](https://docs.astral.sh/uv/). Work from the
AstroAKD-Bench repository root:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast --json-format pretty
```

`doctor` connects to an **already running** compatible Astroquery MCP server;
this repository does not launch one. Set an endpoint for your environment:

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
│       └── llm_generation_instructions_v1.md # Synthetic-question authoring
├── docs/                              # Documentation only
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
any shell commands or scripts using those paths. The `docs/` directory now
contains only documentation and preserved technical background.

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
respectively. The ongoing full 150-run experiment is not claimed complete
until the final live host report confirms it.

### Continue the existing three-arm experiment

Ensure `OPENAI_API_KEY` is set and the external MCP endpoint remains the same
as the saved manifest. From a **0.6.7.4 checkout** (or after the current run
finishes and you upgrade), use the **new instruction path**:

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

`--resume` is used only when a partial journal already exists. Remove it for a
new experiment with new output files. Moving an instruction **without changing
its content** keeps the instruction SHA-256 consistent with the original
pilot's resume manifest. **Do not apply a code update to a currently running
process**; finish that process first. **Do not change MCP URLs within the
same journal**; use a different output prefix for a different server.

### Re-score and regenerate CSV reports / plots

Once the 150-run output `.jsonl` exists, run:

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

For a partial run substitute
`datasets/agent/scorable_50_gpt52_runs.jsonl.progress.jsonl` for `--runs`.
Scoring is offline and keeps **all** actual answers including wrong, blank,
abstained and unstructured ones. Results include a 50-question wide answer
comparison, 150-row detailed comparison, 3-row A/B/C performance CSV, a
per-task performance CSV and PNG/SVG barplots of match rate, runtime and tokens.
`--replace` affects the generated reporting outputs, not the oracle or journal.
See [the reporting guide](docs/benchmark/three_arm_detailed_reporting_0_6_7_1.md).

## Synthetic questions, evidence and scientific qualification

Synthetic generation may use deterministic templates, MCP-backed OpenAI
question authoring, or web-only research. Question-generation instructions
are read automatically from
[`instructions/astroakd_bench/llm_generation_instructions_v1.md`](instructions/astroakd_bench/llm_generation_instructions_v1.md)
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
