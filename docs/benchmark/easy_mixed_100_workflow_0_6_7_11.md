# AstroAKD-Bench 0.6.7.11.1: flexible mixed-question workflow

This is the current supported quick-start. Earlier `*_with_refs` guides describe **single-call** experiments, not the new mixed one. Every command below runs from the repository root. `OPENAI_API_KEY` and the external Astroquery MCP service must be configured for live model/archive commands; reports only read saved files.

## 1. Create `synthetic_100` or choose a different count and destination

```bash
uv run --with openai python -m benchmark create-queries --name synthetic_100 --seed 20261018
```

**Count and custom output directory:**

```bash
uv run --with openai python -m benchmark create-queries \
  --count 40 --seed 20261018 \
  --output-dir /scratch/astroakd/experiment_A --require-ads
```

The automatic name is `synthetic_40`, and outputs are under `/scratch/astroakd/experiment_A/generated/` (main file `synthetic_40.jsonl`, CSV, subset JSONLs and generation report). The folder also contains `validated/`, `agent/`, and `reports/` after subsequent steps. Keep `--output-dir /scratch/astroakd/experiment_A --name synthetic_40` on all later short commands. If you prefer another name, specify `--name my_study` on generation and all later commands. Relative output directories are relative to the selected project root (the command's working directory in CLI mode).

The default `balanced100` mix scales automatically when `--count` is from **1 to 100**; a small pilot does not force a multi-archive pair when there are too few repeated targets. For more than 100, extend the curated target pool before running generation; it is not supported by this shortcut. The advanced `--mix` accepts exact manually specified family counts, which must sum to `--count`.

**Continue a custom-directory experiment:**

```bash
uv run python -m benchmark collect-references \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A --limit 5
uv run python -m benchmark collect-references \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A --resume
uv run --with matplotlib python -m benchmark reference-report \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A
uv run --with openai python -m benchmark run-benchmark \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A --resume
uv run --with matplotlib python -m benchmark agent-report \
  --name synthetic_40 --output-dir /scratch/astroakd/experiment_A
```

Uses GPT-5.2 plus AstroAKD-Bench question-authoring instructions and discovered MCP signatures. Mix: **60 archive**, **20 coordinate**, **8 literature**, **12 multi-archive**. This produces:

| File | Purpose |
|---|---|
| `datasets/generated/synthetic_100.jsonl` | All 100 questions, tasks and provenance |
| `datasets/generated/synthetic_100.csv` | Readable question inventory |
| `datasets/generated/synthetic_100_single_call.jsonl` | 80 executable single-call reference candidates |
| `datasets/generated/synthetic_100_multistep.jsonl` | 20 literature/multi-archive candidates requiring multi-step evidence |
| `datasets/generated/synthetic_100_generation_report.json` | Counts, provider provenance and dataset fingerprints |

Literature research **tries authenticated MCP ADS**, recording ADS bibcodes and source provenance where returned. If ADS is unavailable the existing literature client may use OpenAI web search; this is recorded as web, not ADS. Require exclusively ADS evidence using `--require-ads` (generation refuses unqualified provider). Multi-archive tasks contain two different prebound archive-call plans for the same target; they ask for cross-archive interpretation without asserting that every returned source matches. Neither family has a fabricated single-call reference or an automatically approved answer.

Customize the counts, while keeping them summing to `--count`:

```bash
uv run --with openai python -m benchmark create-queries \
  --name synthetic_100 --count 100 --seed 20261018 \
  --mix archive_driven=60,coordinate_driven=20,literature_driven=8,multi_archive=12
```

The original `generate --task-mix ...` advanced API is still supported; pass `--single-call-output` and `--multistep-output` for explicit split files. Use a new `--name` to make a *different* dataset. Changing a seed does not guarantee deterministic responses from a remote LLM.

## 2. Collect single-call references, with safe resume

```bash
uv run python -m benchmark collect-references --name synthetic_100 --limit 5
uv run python -m benchmark collect-references --name synthetic_100 --resume
```

80 ordinary archive/coordinate questions are eligible; the additional 20 literature and multi-archive questions are **not** silently treated as missing single-call references. `collect-references` uses per-module timeouts and one attempt by default; increase per-module budgets only if archive behavior warrants it. The frozen subset hash and original MCP schema are checked on resume.

If a live server is down, investigate `doctor --fast` and inspect the journal before resuming; a recorded failure is not automatically retried with `--resume`. An archive `accepted_nonempty` result is not gold.

## 3. Create report and six plots without new calls

```bash
uv run --with matplotlib python -m benchmark reference-report --name synthetic_100
```

Outputs under `datasets/reports/synthetic_100/references/`:

- `reference_questions.csv` — one row per question, including *uncollected multi-step* status, answer shape, completeness flags, and attempt duration.
- `reference_archives.csv` — totals and accepted/empty/failed/pending, truncation, null values and median response times by archive.
- `reference_summary.json` — dataset/subset hashes and all aggregate counts.
- PNG/SVG: `questions_by_archive`, `answer_shapes`, `reference_dispositions`, `review_flags`, `truncation_null_by_archive`, `response_times`, and `response_time_distribution`.

The tool runs offline, can read a partial reference journal, and rejects mismatched dataset hashes, changed source calls, duplicate IDs and stale references. Without matplotlib, use `reference-report --no-plots` to create CSV and JSON alone. Only `--replace` overwrites previous **report files**, never reference evidence.

## 4. A/B/C benchmark and reports

```bash
uv run --with openai python -m benchmark run-benchmark --name synthetic_100 --limit 5
uv run --with openai python -m benchmark run-benchmark --name synthetic_100 --resume
uv run --with matplotlib python -m benchmark agent-report --name synthetic_100
```

The pilot executes 5 questions in each arm; resume completes the same experimental context for up to 300 total executions. Agent output is saved under `datasets/agent/synthetic_100_ABC_runs.jsonl` (and a crash-safe progress journal). Reports under `datasets/reports/synthetic_100/agents/` include `abc_answers.csv`, `per_task_operational.csv`, `arm_operational_summary.csv`, `mcp_tool_frequency.csv`, `operational_report.json`, plus 5 PNG/SVG figures: `completed_runs`, `mean_runtime`, `total_tokens`, `mean_mcp_events`, `web_search_calls`. These compare **operating behavior only**, not scientific truth. An incomplete journal gives `PARTIAL`, never a 300-run completion claim.

### A/B/C design

| Arm | Tools | Prompt |
| --- | --- | --- |
| A `mcp_only` | Astroquery MCP | Minimal astronomy instructions |
| B `mcp_instruction` | Identical Astroquery MCP | Minimal + preserved AstroAKD specialist prompt |
| C `web_only` | OpenAI web search | No Astroquery MCP |

No agent sees benchmark gold or archived answer keys. Never compare correctness until independent gold review. Multi-archive tasks and ADS tasks are deliberately more difficult than the historical single-call 50-question experiment; compare by task family rather than treating the datasets as directly interchangeable.

## 5. Python API

```python
import asyncio
from benchmark.api import AstroAKDBench

bench = AstroAKDBench(root='.', mcp_url='http://127.0.0.1:8000/mcp')
created = asyncio.run(bench.create_synthetic_queries(name='synthetic_100', count=100, seed=20261018))
# Alternative: created = asyncio.run(bench.create_synthetic_queries(count=40, output_dir='/scratch/astroakd/experiment_A'))
pilot = asyncio.run(bench.collect_named_references(name='synthetic_100', limit=5))
finished = asyncio.run(bench.collect_named_references(name='synthetic_100', resume=True))
references = bench.create_reference_report(name='synthetic_100', plots=True)
# After separately executing the A/B/C run:
agents = bench.create_agent_report(name='synthetic_100', plots=True)
```

This Python facade delegates to the **same implementation** as the CLI and does not maintain a separate evaluator or model prompt. Archive references, reviewer decisions, agent answers and scientific scores remain separate.

## Scientific-review boundary

The single-call reference collector cannot establish a literature citation/observation association or interpret multi-archive cross-matches. Their answer keys require retained multi-step provenance and human review. The existing `reference-review-draft` and `gold-finalize` commands remain available for compatible ordinary-task datasets, not as an automatic approval of these 100 candidates. `score-scorable` is specific to an older constructed single-field oracle and must not be applied directly to the mixed tasks.

The original accepted 50-task/150-run GPT-5.2 experiment, source datasets, science freeze, and instructions are unchanged. The new name is `synthetic_100` by default; older datasets are not overwritten.
