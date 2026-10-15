# AstroAKD-Bench

**Reproducible synthetic astronomy questions and three-arm agent evaluation.**

**Current version: 0.6.7.11.3** — easy named-dataset workflows; optional single-call reference collection; offline plots; historical datasets archived outside the clean working tree.

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

## Five short commands for `astroakd_100`

### 1. Create 100 mixed synthetic questions with available reference evidence

**Recommended command:** generate 100 questions, require ADS for literature question authoring, and collect available single-call archive evidence automatically. **`--seed` is optional** (default: `20261018`). The named dataset and all new files are saved under the user-facing `datasets/` folder:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers
```

`--name` chooses the filename prefix, `--count` sets the number of questions, and `--output-dir` sets the **root** directory (not a full `.jsonl` filename). `--output-dir datasets` is explicit but optional: it is the default. No manual `mkdir` is necessary. The command writes `datasets/generated/astroakd_100.jsonl` and `.csv`, an 80-question single-call subset, a 20-question multi-step subset, and `datasets/validated/astroakd_100_references.jsonl` for collected eligible references.

**What `--with-reference-answers` means:** of the default balanced 100 questions, **60 archive-driven plus 20 coordinate-driven** questions are eligible for automatic single-call MCP collection. **8 literature/ADS and 12 multi-archive questions require multi-step evidence** and stay pending. ADS literature discovery used in writing questions is not a verified answer. All collected values are **unreviewed evidence**, not approved gold. Live model and MCP calls require configured OpenAI and Astroquery MCP access, including working ADS credentials when `--require-ads` is set.

**Safe five-reference pilot:** add `--reference-limit 5` to the command above. Finish reference collection afterwards without regenerating questions:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100 --output-dir datasets --resume
```

**Questions only:** omit `--with-reference-answers`; `collect-references` can then be called separately. To generate 40 questions under a custom study root, use `--name my_study --count 40 --output-dir /scratch/astroakd/study1`. The balanced family counts scale automatically for 1–100 questions. Supply `--seed 42` or another integer when you need to control local random choices; fixed seeds do **not** guarantee identical remote GPT output. For an exact A/B/C comparison reuse the saved JSONL, rather than regenerating it. Existing datasets are protected; `--replace` is destructive and should not be used on a frozen experiment.

The current default mix is 60 archive-driven, 20 coordinate-driven, 8 ADS literature-driven and 12 multi-archive questions. With `--require-ads`, literature authoring must use MCP ADS, not an unlabeled web fallback. The model generates questions rather than independently verified scientific answers.

## Dataset layout and frozen experiment archives (0.6.7.11.3)

The source release ships an intentionally clean `datasets/` working directory containing only [its README](datasets/README.md). The five commands above create needed `generated/`, `validated/`, `agent/`, and `reports/` subdirectories automatically. The old **118-file data snapshot** is not deleted: it is distributed **separately** as `astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz`, plus a smaller frozen 50-question experiment archive. Each historical file has an independently verified SHA-256 in [the archival manifest](archives/historical_datasets_manifest_0_6_7_11_3.json). Nine unchanged inputs needed for offline regressions live in `benchmark/tests/fixtures/legacy/`.

For restoring historical data, use a separate directory or checkout, never overwrite your active working `datasets/`:

```bash
mkdir -p /tmp/astroakd-history
tar -xzf astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz \
  -C /tmp/astroakd-history
```

See [dataset cleanup and reproducibility](docs/benchmark/dataset_layout_historical_archive_0_6_7_11_3.md) for archive checksums, canonical frozen task/oracle SHA-256, legacy fixture paths, and reproduction of historical reports.

### 2. Collect references separately (when not using `--with-reference-answers`)

```bash
uv run python -m benchmark collect-references --name astroakd_100 --limit 5
uv run python -m benchmark collect-references --name astroakd_100 --resume
```

Skip this step if `--with-reference-answers` already collected all 80 single-call references. The collector uses conservative archive-specific timeouts/retry limits. It writes immutable-evidence JSONL and a per-task progress journal under `datasets/validated/`. The **20 literature/multi-archive questions require a separate multi-step evidence/review workflow** and deliberately remain pending in reference reports. Do not pass the full mixed JSONL to the single-call validator.

### 3. Create native reference reports and plots (offline)

```bash
uv run --with matplotlib python -m benchmark reference-report --name astroakd_100
```

Look in `datasets/reports/astroakd_100/references/`. It contains summary JSON, per-question and per-archive CSV, and PNG/SVG plots for archive balance, answer shapes, dispositions, missing/null/truncated values, and reference response times. **No OpenAI or MCP calls** occur. Add `--replace` to regenerate reports, never reference evidence. It also works before collection and labels missing evidence accurately.

### 4. Run a resumable A/B/C experiment

```bash
uv run --with openai python -m benchmark run-benchmark --name astroakd_100 --limit 5
uv run --with openai python -m benchmark run-benchmark --name astroakd_100 --resume
```

Same GPT-5.2 model and prompts across arms: A = MCP only, B = MCP with the AstroAKD specialist instruction, C = Web only. A full run has **300 question–arm executions**. Resume requires the same model, MCP endpoint, instruction hash, and resource settings. Archive references/gold answers are **never given to agents**.

### 5. Create A/B/C reports and plots (offline)

```bash
uv run --with matplotlib python -m benchmark agent-report --name astroakd_100
```

Look in `datasets/reports/astroakd_100/agents/`: a three-arm answer CSV, per-task/arm trace metrics, per-arm operating summaries, MCP frequencies, and PNG/SVG completion, runtime, token, tool-use and web-search plots. Supports partial journals. Completion **is not scientific accuracy**.

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
