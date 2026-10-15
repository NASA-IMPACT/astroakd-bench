# AstroAKD-Bench

**Reproducible synthetic astronomy questions and three-arm agent evaluation.**

**Current version: 0.6.7.11.2** — easy named-dataset workflows; ADS/literature and multi-archive questions; native offline archive-reference and A/B/C reports with PNG/SVG plots.

AstroAKD-Bench is the **benchmark**. AstroAKD is the **evaluated agent**. The independent [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp) is the **archive backend**. Benchmark questions, archive observations, independently reviewed scientific answers, and agent predictions remain separate objects.

[Simple 100-question guide](docs/benchmark/easy_mixed_100_workflow_0_6_7_11.md) · [Python API](docs/benchmark/python_api.md) · [Documentation](docs/index.md) · [CHANGELOG](CHANGELOG.md)

## Setup

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), an `OPENAI_API_KEY` for question generation/agent runs, and a running external Astroquery MCP service for MCP-powered tasks. In a separate terminal, start that server:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

From **this** repository root, verify the connection:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast
export OPENAI_API_KEY='YOUR_API_KEY'  # set securely; do not commit credentials
```

The default server is `http://127.0.0.1:8000/mcp`; `ASTROAKD_MCP_URL` and `ASTROAKD_MCP_TOKEN` select a remote server if needed. MCP ADS literature search may require credentials *in the server configuration*. Do not put an ADS token in benchmark output or in a question.

## Five short commands for `synthetic_100`

### 1. Create synthetic questions, optionally collecting reference evidence

```bash
uv run --with openai python -m benchmark create-queries \
  --name synthetic_100 --model gpt-5.2 --seed 20261018
```

You can select **any count from 1 through 100** using `--count`; the mixed proportions are adjusted automatically without writing a manual `--mix`. Set `--output-dir` to put **all artifacts** into a chosen folder. If you omit `--name`, it becomes `synthetic_N` (for example `synthetic_40`), while the default remains `synthetic_100`.

```bash
# Question generation only (no reference queries)
uv run --with openai python -m benchmark create-queries \
  --count 40 --seed 20261018 \
  --output-dir /scratch/astroakd/study1 --require-ads
```

**Generate questions and collect real reference observations in one command**
(`--with-reference-answers` is supported by `create-queries` in 0.6.7.11.2):

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_test40 \
  --count 100 \
  --output-dir /scratch/astroakd/study1 \
  --seed 20261018 \
  --require-ads \
  --with-reference-answers
```

Here `--name` and `--count` are **independent**: the command creates 100
questions named `astroakd_test40`. To create 40, set `--count 40`. With the
100-question balanced mix, the command collects references for **80 eligible
single-call archive/coordinate questions** after generation. The 8 ADS literature
and 12 multi-archive questions are retained and reported as **multi-step evidence
pending**, not falsely assigned reference answers. ADS research during question
authoring is *not* an independently verified answer. All observed reference values
remain unreviewed; **zero are automatically declared gold**.

For a faster initial reference check add `--reference-limit 5`. The generator
saves its output before archive queries; after the pilot (or an interrupted
collection), finish without regenerating or paying for another model run:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_test40 --output-dir /scratch/astroakd/study1 --resume
```

This two-step alternative is also available when you omit
`--with-reference-answers` entirely. Never rerun `create-queries` merely to
resume reference collection. Use a new name for a genuinely new dataset;
`--replace` intentionally replaces existing generation output.

This saves `/scratch/astroakd/study1/generated/synthetic_40.jsonl`, its CSV and split subsets, and its generation report. Follow-up commands use the **same `--output-dir` and `--name`**:

```bash
uv run python -m benchmark collect-references --name synthetic_40 \
  --output-dir /scratch/astroakd/study1 --limit 5
uv run --with matplotlib python -m benchmark reference-report \
  --name synthetic_40 --output-dir /scratch/astroakd/study1
```

Other output subdirectories are `validated/`, `agent/`, and `reports/` beneath the chosen directory. Without `--output-dir`, the historical paths under `datasets/` are unchanged. The current curated target catalog limits the automatic mixed generator to **100 questions maximum**; larger counts require more unique science targets.

The default **balanced100** mix is:

| Question family | Count | Evidence plan |
| --- | ---: | --- |
| Archive-driven | 60 | Single MCP archive call |
| Coordinate-driven | 20 | Single MCP archive call with a defined ICRS region |
| Literature-driven | 8 | Publication discovery via authenticated MCP ADS when available, plus archive follow-up |
| Multi-archive | 12 | At least two different Astroquery archive calls on the same target |
| **Total** | **100** | **80 single-call + 20 multi-step** |

For ADS-backed literature **without any web fallback**, add `--require-ads`. This fails rather than mislabeling web evidence as ADS. Without it, literature research can explicitly fall back to OpenAI web search when ADS is unavailable; the provenance records the provider. The model writes **questions, never gold answers**. The 20 multi-step tasks are not validated by pretending their two or more calls are a single MCP call.

The generator saves `datasets/generated/synthetic_100.jsonl` and `synthetic_100.csv`, alongside `synthetic_100_single_call.jsonl`, `synthetic_100_multistep.jsonl`, and `synthetic_100_generation_report.json`. Choose a new `--name` for an independent dataset; `--replace` intentionally replaces outputs and should **not** be used for a frozen experiment. A seed does not guarantee byte-identical OpenAI API output.

### 2. Collect references separately (when not using `--with-reference-answers`)

```bash
uv run python -m benchmark collect-references --name synthetic_100 --limit 5
uv run python -m benchmark collect-references --name synthetic_100 --resume
```

Skip this step if `--with-reference-answers` already collected all 80 single-call references. The collector uses conservative archive-specific timeouts/retry limits. It writes immutable-evidence JSONL and a per-task progress journal under `datasets/validated/`. The **20 literature/multi-archive questions require a separate multi-step evidence/review workflow** and deliberately remain pending in reference reports. Do not pass the full mixed JSONL to the single-call validator.

### 3. Create native reference reports and plots (offline)

```bash
uv run --with matplotlib python -m benchmark reference-report --name synthetic_100
```

Look in `datasets/reports/synthetic_100/references/`. It contains summary JSON, per-question and per-archive CSV, and PNG/SVG plots for archive balance, answer shapes, dispositions, missing/null/truncated values, and reference response times. **No OpenAI or MCP calls** occur. Add `--replace` to regenerate reports, never reference evidence. It also works before collection and labels missing evidence accurately.

### 4. Run a resumable A/B/C experiment

```bash
uv run --with openai python -m benchmark run-benchmark --name synthetic_100 --limit 5
uv run --with openai python -m benchmark run-benchmark --name synthetic_100 --resume
```

Same GPT-5.2 model and prompts across arms: A = MCP only, B = MCP with the AstroAKD specialist instruction, C = Web only. A full run has **300 question–arm executions**. Resume requires the same model, MCP endpoint, instruction hash, and resource settings. Archive references/gold answers are **never given to agents**.

### 5. Create A/B/C reports and plots (offline)

```bash
uv run --with matplotlib python -m benchmark agent-report --name synthetic_100
```

Look in `datasets/reports/synthetic_100/agents/`: a three-arm answer CSV, per-task/arm trace metrics, per-arm operating summaries, MCP frequencies, and PNG/SVG completion, runtime, token, tool-use and web-search plots. Supports partial journals. Completion **is not scientific accuracy**.

## Review and scientific validity

A successful archive response is **unreviewed observational evidence**, not an independently reviewed gold answer. Row association, units, multiple matches, truncated catalogs, null measurements, ambiguous targets, literature citations and multi-archive cross-matches require manual review. Gold finalization must use evidence-backed reviewer approvals. Existing `reference-review-draft` and `gold-finalize` commands remain available for ordinary single-call datasets and qualified reviewed sources; **do not use the generated question CSV as a gold oracle**.

The historical 50-question / 150-run GPT-5.2 experiment and its hashes, journals, oracles, and instruction files are retained untouched. The 0.6.7.11 code **does not itself regenerate live 100 questions in a source package**; run command 1 with your own connected MCP and OpenAI credentials to produce the new independent dataset.

## Python API

```python
import asyncio
from benchmark.api import AstroAKDBench

bench = AstroAKDBench('.')
asyncio.run(bench.create_synthetic_queries(name='synthetic_100', count=100, seed=20261018))
# Alternative: asyncio.run(bench.create_synthetic_queries(count=40, output_dir='/scratch/astroakd/study1'))
# After archive collection (CLI or bench.collect_named_references):
reference_summary = bench.create_reference_report(name='synthetic_100')
# After A/B/C runs:
agent_summary = bench.create_agent_report(name='synthetic_100')
```

The older detailed `generate`, `validate`, `run-three-arm`, `export-answer-csv`, `gold-finalize`, `score-three-arm`, and `score-scorable` interfaces continue to work. For custom quotas, `--mix archive_driven=60,coordinate_driven=20,literature_driven=8,multi_archive=12` is equivalent to `balanced100`. [Advanced CLI, science qualifications, and Python examples](docs/benchmark/easy_mixed_100_workflow_0_6_7_11.md).

## Documentation build

```bash
uv run --extra docs make -C docs/sphinx html
```

The site is written to `docs/_build/html/index.html`; this build is independent of the live agent or archive.

## Historical 50-question experiment (preserved, not the new default)

The earlier 50-task GPT-5.2 workflow is still supported and documented in the [historical quick-start](docs/benchmark/quickstart.md). Its four documented stages are **Run all 50 questions (new experiment; no `--resume`)**, **Pilot run (`--limit 5`)**, **Resume a partial pilot (`--resume`)**, and **Score and generate CSV reports / plots**. These instructions apply to the historical single-field reference oracle, **not** to the new literature/multi-archive `synthetic_100` mix.

The original, scientifically frozen prompts are `instructions/astroakd/AstroAKD_Instruction.md` (the evaluated agent's specialist instruction) and `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` (question generation). Their bytes are unchanged.

Documentation commands from the repository root:

```bash
make -C docs/sphinx html
make -C docs/sphinx clean
```
