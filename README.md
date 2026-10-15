# AstroAKD-Bench

**Current version: 0.6.7.11.4** · Benchmark for astronomy archive-search agents using an independent [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp). Benchmark questions, archive observations, independently reviewed gold answers, and agent responses remain distinct.

## Quick start: 100 new questions with references

Requirements: Python 3.11+, `uv`, an `OPENAI_API_KEY`, and the external Astroquery MCP server listening at `http://127.0.0.1:8000/mcp`. To require ADS literature research, configure an ADS token **on the MCP server** before starting it.

**Check ADS before spending OpenAI credits:**

```bash
uv run python -m benchmark literature-auth --probe
```

Only proceed with `--require-ads` if the probe succeeds. The benchmark checks automatically as well and **fails before generating any questions** when ADS cannot execute a real query.

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers
```

`--name` sets the file prefix; `--count` selects 1–100 questions; `--output-dir` is the study root. The `--seed` option is optional (default `20261018`); fixed seeds do **not** guarantee byte-identical results from remote GPT models. To reproduce an evaluation, **reuse the saved JSONL**. New outputs create their own subdirectories; there is no need for manual `mkdir`.

For 100 questions, the default mix contains **60 archive-driven, 20 coordinate-driven, 8 ADS-literature, and 12 multi-archive** questions. `--with-reference-answers` collects live, **unreviewed** archive evidence for up to 80 eligible single-call questions; the 20 multi-step questions remain pending separately. Collected observations are **not** independently verified scientific answers. For question generation only, omit `--with-reference-answers`.

### Finish reference collection / make plots

```bash
# Optional initial pilot: add --reference-limit 5 to create-queries above;
# then resume the saved questions without another GPT generation run
uv run python -m benchmark collect-references \
  --name astroakd_100 --output-dir datasets --resume

# Archive coverage, answer shape, nulls, truncation, response-time plots
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100 --output-dir datasets
```

If you originally generated questions *without* reference collection, run `collect-references` without `--resume` on the first attempt. Existing output files are protected unless you explicitly request replacement.

### Execute A/B/C and generate reports

```bash
# Five-question pilot followed by a resumable 100-question three-arm experiment
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --resume

# Offline A/B/C CSV and PNG/SVG figures
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100 --output-dir datasets
```

The three arms are **A** (MCP only), **B** (MCP with the [AstroAKD instruction](instructions/astroakd/AstroAKD_Instruction.md)), and **C** (web only). A full 100-question experiment can generate 300 runs. Runtime, completion, tool-use, and token-consumption plots are **operational measures**, not scientific correctness without reviewed gold references.

## Troubleshoot ADS literature generation

If you see `ADS route unavailable (ads_search_unavailable)`, the MCP ADS query failed; it does **not** uniquely identify a missing token. From the benchmark directory run:

```bash
uv run python -m benchmark literature-auth --probe
```

The [current Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp) expects the ADS credential in its own process environment (typically `API_DEV_KEY`, or `ADS_API_KEY` fallback). After configuring/restarting that server, verify the probe again. The benchmark does not log credentials. `--require-ads` now checks actual ADS query availability *before* authoring questions; if you do not require ADS literature, omit that flag to allow explicitly labeled web-search fallback evidence.

See [ADS and MCP troubleshooting](docs/benchmark/ads_and_mcp.md) for detailed diagnostic reasons and safe setup. Never share tokens in logs or issue reports.

## Files and scientific integrity

`datasets/` is an initially clean working directory, not a bundled record of past experiments:

| Directory | New outputs |
| --- | --- |
| `datasets/generated/` | Questions, CSV and generation metadata |
| `datasets/validated/` | Collected reference observations and journal |
| `datasets/agent/` | Three-arm execution journals |
| `datasets/reports/` | Offline CSV summaries and plots |

Historical data and past version-specific installation/qualification documents are preserved in **separate checksum-indexed archival packages**, not the current user guide or main source root. The frozen 50-question experiment's essential test inputs remain unchanged under `benchmark/tests/fixtures/legacy/`. These are for regression purposes, not preverified 100-question gold. The original data archive metadata lives under [`archives/`](archives/).

## Python API

```python
import asyncio
from benchmark.api import AstroAKDBench

bench = AstroAKDBench('.')
asyncio.run(bench.create_synthetic_queries(
    name='astroakd_100', count=100, output_dir='datasets',
    require_ads=True, with_reference_answers=True,
))
report = bench.create_reference_report(name='astroakd_100', output_dir='datasets')
```

## Documentation and development

Read the [current documentation](docs/index.md) for [getting started](docs/benchmark/quickstart.md), [synthetic question generation](docs/benchmark/create_queries.md), [ADS configuration](docs/benchmark/ads_and_mcp.md), [reference review](docs/benchmark/references_and_review.md), [A/B/C evaluation and plots](docs/benchmark/evaluation_and_plots.md), and [Python API](docs/benchmark/python_api.md). All documentation describes **the supported current release**, not previous-version commands.

Build HTML:

```bash
make -C docs/sphinx clean
make -C docs/sphinx html
```

Source history: [CHANGELOG](CHANGELOG.md); [installation](INSTALL.md); full help: `uv run python -m benchmark --help`. The generation instructions are in [`instructions/astroakd_bench/AstroAKD-Bench_Instruction.md`](instructions/astroakd_bench/AstroAKD-Bench_Instruction.md), distinct from the evaluated agent's specialist prompt. The advanced API commands are retained for specialized workflows and replay/regression testing.
