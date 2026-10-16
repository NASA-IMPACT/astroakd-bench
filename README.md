# AstroAKD-Bench

**Current version: 0.6.7.11.10** · Benchmark for astronomy archive-search agents using an independent [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp). Benchmark questions, archive observations, independently reviewed gold answers, and agent responses remain distinct.

## Quick start: 100 new questions with references

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), an `OPENAI_API_KEY`, and an independent Astroquery MCP server. **Install and start the MCP server first, in its own terminal.** It is a separate repository, not part of AstroAKD-Bench.

### Terminal 1 — install and start Astroquery MCP

From a suitable parent directory, clone the [NASA IMPACT Astroquery MCP repository](https://github.com/NASA-IMPACT/astroquery-mcp) and start the HTTP server:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Keep this terminal running. The endpoint should be `http://127.0.0.1:8000/mcp`. For `--require-ads`, set `API_DEV_KEY` (or the server's supported `ADS_API_KEY` fallback) **in this server terminal before the last command**. Never commit the token or paste it into benchmark questions or logs. If you set the token after launching the server, restart the server.

### Terminal 2 — install and verify AstroAKD-Bench

Open a **different terminal**, switch to the AstroAKD-Bench repository root (not `astroquery-mcp`), and run:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark doctor --fast
```

Set `OPENAI_API_KEY` securely in this benchmark terminal before question generation or A/B/C runs. The MCP server defaults to `http://127.0.0.1:8000/mcp`; use `ASTROAKD_MCP_URL` and, if required, `ASTROAKD_MCP_TOKEN` for a remote/protected MCP endpoint. The MCP bearer token is **not** the ADS API key.

**Verify ADS access and an actual literature search from the benchmark terminal before spending OpenAI credits:**

```bash
# General authentication plus read-only known-bibcode lookup
uv run python -m benchmark literature-auth --probe

# Important: directly test the query that previously failed
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

A successful known-bibcode lookup does **not** establish that general literature searches work. `--require-ads` probes the real literature plans before GPT generation and refuses an OpenAI web-search fallback. The strict default is intentional: when ADS errors persist, it is safer to stop than label web evidence as ADS evidence. The literature plan's *target name* is now supplied to ADS even when the old science-topic search string omitted the object identifier (as it did for PG 1211+143). Query retries use distinct ADS formulations and a compact field list; no citation is fabricated.

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

**Reference-aware question generation (0.6.7.11.10).** With `--with-reference-answers`, the benchmark now prechecks candidate *archive calls before GPT authoring*. It tries bounded search radii (particularly for Gaia/MAST), verifies that the returned data are nonempty, untruncated, contain all requested fields without nulls, and fit **20 complete rows / 65,536 response bytes** by default. It may probe several candidate targets/radii; `--max-reference-rows 20 --max-reference-bytes 65536 --max-feasibility-probes 500` adjusts these limits. Candidate acceptance is independent of agent A/B/C performance. **No GPT question batches are requested unless the single-call candidate quota can be filled.** An exhausted archive is replaced by another feasible module, with the actual module balance recorded. If candidates or the probe budget run out, every completed feasibility probe and accepted slot is saved for `--resume`; a failed run is still not a completed dataset. Live success depends on the MCP server and archive content.

After all slots are accepted, the finalized question-slot plan is saved with a SHA-256 checksum at `datasets/generated/astroakd_100_v2_feasibility_plan.json` for reproducible `--resume`. Accepted probes are **not gold answers**; the collector independently retrieves the 80 eligible single-call references. The remaining 8 literature and 12 multi-archive questions still need multi-step reference collection. This milestone **does not change A/B/C scoring**. To keep the original 100-question/300-run benchmark frozen, generate with **a new name** (`astroakd_100_v2`, not `astroakd_100`). Use `--no-reference-aware` only when you explicitly want the legacy, potentially large-result question policy.

`--name` sets the file prefix; `--count` selects 1–100 questions; `--output-dir` is the study root. The `--seed` option is optional (default `20261018`); fixed seeds do **not** guarantee byte-identical results from remote GPT models. To reproduce an evaluation, **reuse the saved JSONL**. New outputs create their own subdirectories; there is no need for manual `mkdir`.

For 100 questions, the default mix contains **60 archive-driven, 20 coordinate-driven, 8 ADS-literature, and 12 multi-archive** questions. `--with-reference-answers` collects live, **unreviewed** archive evidence for up to 80 eligible single-call questions; the 20 multi-step questions remain pending separately. Collected observations are **not** independently verified scientific answers. For question generation only, omit `--with-reference-answers`. To allow slow archives, pass `--archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 --reference-deadline 2100` to the same one-step command.

### Recover reference-aware archive probes without repeating them

**0.6.7.11.10 fixes a data-loss problem in 0.6.7.11.9.** Each archive
feasibility probe (accepted or rejected) is written atomically to
`datasets/generated/astroakd_100_v2_feasibility_progress.json` along with
approved candidate slots and a SHA-256 checksum. The selector now tries another
archive when a preferred module (such as MAST) runs out of complete, bounded
results. It tries the smallest cone first and skips larger cones after
truncation, avoiding many redundant MAST requests. The *actual* archive mix
is reported; per-question limits and reference completeness are never relaxed.

If probes exhaust their budget or the process is interrupted, keep the
`datasets/generated/` files and add `--resume` to the **same** command:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 --count 100 --output-dir datasets \
  --require-ads --with-reference-answers --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100 --resume
```

You may **increase only `--max-feasibility-probes` on resume** if the original
probe budget was exhausted. A lowered budget or changes to targets, seed,
question count, archive modules or response-size thresholds are rejected.
The former 0.6.7.11.9 implementation did not save incomplete feasibility
plans, so its already-failed archive calls cannot be recovered retroactively.
No GPT batches were requested in the reported 275-probe MAST failure; those
calls consumed external archive resources and time, not GPT question-writing
requests. Once selection completes, the full feasibility plan is written and
its temporary probe checkpoint is removed. Incomplete progress **is not a
published or verified dataset**. ADS preflight may be repeated on resume.

### Recover from interrupted question generation

Each successful GPT batch is now written to a durable journal at `datasets/generated/astroakd_100_v2.progress.jsonl` and a human-inspectable **partial, unvalidated** file at `datasets/generated/astroakd_100_v2_partial.jsonl`. If a later literature request, model call or archive step fails before final question publication, these records preserve already completed work. Once ADS/service problems are corrected, **reuse the same inputs** and add `--resume`:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 --count 100 --output-dir datasets \
  --require-ads --with-reference-answers --timeout 900 --resume
```

Resume must use the original name, count, seed, model, mix, module list, batch size, MCP endpoint and ADS requirement. Completed batches are not sent to GPT again. The partial file is **not** a valid final evaluation dataset and must never be treated as reviewed gold. After all questions and output files pass final checks, the progress files are removed and the ordinary `astroakd_100_v2.jsonl`/CSV outputs are published. A preflight failure *before* any GPT batch makes no progress journal because no paid generation has been completed. Versions 0.6.7.11.4 and earlier did not save such checkpoints: prior unsaved GPT responses cannot be recovered from console output.

### Finish or recover single-call reference collection / make plots

If `create-queries` has already published the 100 questions but its reference
collection did not run or was interrupted, **do not regenerate the paid GPT
questions**. Reuse the saved
`datasets/generated/astroakd_100_v2_single_call.jsonl` with the same archive
policy used for generation:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100_v2 \
  --output-dir datasets \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

For an interrupted reference collection, add `--resume` to the above command
to reuse its saved progress journal. Use the command **without `--resume`** for
the first collection attempt. If `create-queries --with-reference-answers`
already collected all 80 single-call references, **do not rerun collection**.
The existing references are under `datasets/validated/`, and the 20
literature/multi-archive tasks still require separate multi-step evidence.

Create the offline reference-quality summary and figures without calling MCP
or GPT:

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 \
  --output-dir datasets
```

Output is in `datasets/reports/astroakd_100_v2/references/`. The report
classifies 80/80 nonempty single-call references as **collection complete**;
`status: REVIEW` is expected while the 20 multi-step tasks and independent
scientific review remain outstanding. Use `reference-report --replace` **only**
when regenerating an existing report; this option does not change the
questions or collected references.

### Execute A/B/C and generate reports

```bash
# Five-question pilot followed by a resumable 100-question three-arm experiment
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets --resume

# Offline A/B/C CSV and PNG/SVG figures
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets
```

The three arms are **A** (MCP only), **B** (MCP with the [AstroAKD instruction](instructions/astroakd/AstroAKD_Instruction.md)), and **C** (web only). A full 100-question experiment can generate 300 runs. Runtime, completion, tool-use, and token-consumption plots are **operational measures**, not scientific correctness without reviewed gold references.

### How to create the A/B/C comparison figures

`run-benchmark` **only executes** the A/B/C experiment and saves the run journal in `datasets/agent/`. It does **not** generate figures. After it finishes (or during a partial run), generate the plots **offline** with:

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 \
  --output-dir datasets
```

If the plots/reports already exist, use the same command with `--replace` to regenerate the **reports only**; agent runs and archive observations are not overwritten.

The figures are saved to `datasets/reports/astroakd_100_v2/agents/`:

| Output | What it compares across A / B / C |
| --- | --- |
| `mean_runtime.png` and `.svg` | Mean runtime per **recorded** run (seconds) |
| `total_tokens.png` and `.svg` | Total recorded input + output tokens in each arm |
| `completed_runs.png` and `.svg` | Completed agent runs, **not** correct answers |
| `mean_mcp_events.png` and `.svg` | Mean MCP tool events per recorded run |
| `web_search_calls.png` and `.svg` | Number of web-search calls |
| **`match_rate.png` and `.svg`** | **Strict unreviewed reference-snapshot agreement** on eligible questions; explicitly not scientific accuracy |
| `reference_agreement_per_question.csv` | Per-task match decisions and exact exclusion reasons |
| `reference_agreement_summary.json` | Scorable denominator, excluded counts, per-arm provisional agreement |
| `arm_operational_summary.csv` | Counts, runtime, tokens, tool activity, and partial-run denominators |
| `abc_answers.csv` | Agent answers retained side by side for scientific review |

**Match-rate qualification:** In 0.6.7.11.8, `agent-report` also generates `match_rate.png` **when the saved `validated/<name>_references_review.csv` contains automatically comparable single-call evidence**. The plot title reads **“UNREVIEWED, not scientific accuracy”** and uses a *common scorable denominator*: complete single values, single-field record lists and coordinate pairs. Truncated, null, ambiguous/multifield, empty and missing multi-step references are excluded with reasons in CSV. Run errors and abstentions on eligible tasks count as nonmatches. This is *strict reference-snapshot agreement*, not a scientific-gold correctness rate, and must not be compared directly to the old 50-question figure without noting the different dataset and denominator. For verified accuracy, review/approve a gold oracle and use the established `score-three-arm` workflow separately.

### Rerun only failed MCP-only tasks (do not rerun all 300)

A completed 300-run A/B/C journal is intentionally immutable. To check which failed records would be retried **without any API calls**:

```bash
uv run python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --retry-errors --dry-run --max-turns 16 --max-calls 20
```

To retry only the failed `mcp_only` tasks (in the observed dataset, `ASTROAKD-MIX-00016` and `ASTROAKD-MIX-00029`), preserving the original runs:

```bash
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --retry-errors --max-turns 16 --max-calls 20 \
  --timeout 900 --task-timeout 2400
```

The command creates separate `datasets/agent/astroakd_100_v2_mcp_only_turn16_retries.jsonl` (only retried records) and `astroakd_100_v2_ABC_runs_turn16_diagnostic.jsonl` (derived 300-run comparison). **It never modifies** `astroakd_100_v2_ABC_runs.jsonl`; a changed turn budget is a diagnostic, not a replacement experimental arm. To plot the diagnostic separately:

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets \
  --runs datasets/agent/astroakd_100_v2_ABC_runs_turn16_diagnostic.jsonl
```

The diagnostic figures are saved under `datasets/reports/astroakd_100_v2/agents_diagnostic/`; the baseline figures remain in `agents/`. Preserve both for comparison. No OpenAI or MCP calls occur during `agent-report`.

### How to create reference-completeness figures

These are **different** from A/B/C figures and do not run agents. After collecting available references:

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 \
  --output-dir datasets \
  --replace
```

The `--replace` flag is useful if a previous plotting attempt left partial report files: it **does not** replace generated questions or reference evidence. Outputs go to `datasets/reports/astroakd_100_v2/references/`, including `response_times.png`, `response_time_distribution.png`, `questions_by_archive.png`, `answer_shapes.png`, and completeness figures. Archives with no recorded runtimes (such as pending multi-archive questions) are excluded from median-time computation without removing them from the overall counts. If matplotlib is unavailable, pass `--no-plots` and omit `--with matplotlib` to create the CSV/JSON summaries only. See [References and scientific review](docs/benchmark/references_and_review.md).

## Troubleshoot ADS literature generation

If the known-bibcode probe passes but PG 1211+143 fails, **do not increase `--archive-timeouts` or `--reference-deadline`**: these control later archive references, not ADS literature searches. Diagnose the *same* target search:

```bash
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

The current diagnostics report safe failure classes such as `upstream_http_400_bad_query`, `upstream_http_401_authentication`, `upstream_http_403_forbidden`, `upstream_http_429_rate_limit`, `upstream_timeout`, `mcp_transport_error`, or `mcp_ads_tool_error_unclassified`. Raw upstream exception text and credentials are **not** written into diagnostic reports. The server-side ADS error/HTTP status is necessary to resolve an unclassified failure. Check the **server logs privately** without copying token values into tickets or chats.

The [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp) requires the ADS credential in the **server process** (typically `API_DEV_KEY`, with an `ADS_API_KEY` fallback). A valid configured token does not guarantee the remote ADS API will accept every search. If ADS is inaccessible and ADS-specific provenance is not required, you may omit `--require-ads`, which allows an explicitly labeled OpenAI web-search fallback; it **must not** be represented as ADS evidence. This route uses OpenAI credits and is not equivalent to strict ADS qualification.

For the reference/agent timeout examples see [Create synthetic queries](docs/benchmark/create_queries.md). For detailed failure diagnosis see [ADS and MCP](docs/benchmark/ads_and_mcp.md).

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
    name='astroakd_100_v2', count=100, output_dir='datasets',
    require_ads=True, with_reference_answers=True,
))
report = bench.create_reference_report(name='astroakd_100_v2', output_dir='datasets')
```

## Documentation and development

Read the [current documentation](docs/index.md) for [getting started](docs/benchmark/quickstart.md), [synthetic question generation](docs/benchmark/create_queries.md), [ADS configuration](docs/benchmark/ads_and_mcp.md), [reference review](docs/benchmark/references_and_review.md), [A/B/C evaluation and plots](docs/benchmark/evaluation_and_plots.md), and [Python API](docs/benchmark/python_api.md). All documentation describes **the supported current release**, not previous-version commands.

Build HTML:

```bash
make -C docs/sphinx clean
make -C docs/sphinx html
```

Source history: [CHANGELOG](CHANGELOG.md); [installation](INSTALL.md); full help: `uv run python -m benchmark --help`. The generation instructions are in [`instructions/astroakd_bench/AstroAKD-Bench_Instruction.md`](instructions/astroakd_bench/AstroAKD-Bench_Instruction.md), distinct from the evaluated agent's specialist prompt. The advanced API commands are retained for specialized workflows and replay/regression testing.

## Reference-aware v2 A/B/C study (0.6.7.11.9)

After `astroakd_100_v2` generation and reference collection finish, keep its question JSONL and generation report unchanged and run a **new** A/B/C study (not `astroakd_100_v2`):

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 --output-dir datasets
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --timeout 900 --task-timeout 2400 --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100_v2 --output-dir datasets \
  --timeout 900 --task-timeout 2400 --resume
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100_v2 --output-dir datasets
```

`agent-report` creates A/B/C operational plots and a **provisional** `match_rate.png` only for automatically comparable reference snapshots. Inspect `reference_agreement_summary.json` and its exclusion counts: the generator's feasibility gate aims to improve that coverage but does **not guarantee** full 100-question reference accuracy, and it does not yet collect multi-step gold answers. If the feasibility quota fails before GPT, choose a different valid candidate mix or extend the curated target inventory; do not bypass the gate just to improve reported accuracy.
