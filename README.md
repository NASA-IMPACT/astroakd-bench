# AstroAKD-Bench

**Reproducible synthetic astronomical queries and evidence-based evaluation of AI data-discovery agents.**

AstroAKD-Bench is an **independent Python repository** for developing and evaluating agents that discover astronomical data through the [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp). That server is an **external service**, not this repository or the owner of this benchmark. AstroAKD-Bench generates natural-language astronomy tasks, executes reference archive queries via MCP, collects independent agent traces, and scores observable execution and a bounded set of claims.

**Current implemented version: 0.6.7.3 — CONFIGURABLE_MCP_ENDPOINT_AND_BEARER_AUTH.** The default `generate` command now uses OpenAI to author diverse synthetic questions with workbook-derived instructions and the external Astroquery MCP server. `--backend template` retains the API-free legacy generator; `--no-mcp` uses OpenAI Responses `web_search` instead. OpenAI generation uses a separate API key/billing; offline audits and scoring do not.

## 0.6.7.3: MCP endpoint and bearer-token configuration

AstroAKD-Bench uses `--mcp-url` (alias `--mcp-server`) if supplied; otherwise it reads **`ASTROAKD_MCP_URL`**, falling back to **`http://127.0.0.1:8000/mcp`**. Authentication comes from `--mcp-token` (alias `--mcp-server-token`) or **`ASTROAKD_MCP_TOKEN`**. **Empty or unset tokens mean no bearer authentication.** Generic `MCP_URL` and `MCP_TOKEN` are intentionally not consulted.

```bash
# Local unauthenticated MCP server
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN
uv run python -m benchmark doctor --fast --json-format pretty

# Remote bearer-protected MCP server
export ASTROAKD_MCP_URL='https://coming-gray-slug.fastmcp.app/mcp'
export ASTROAKD_MCP_TOKEN='YOUR_ACCESS_TOKEN'
uv run python -m benchmark doctor --fast --json-format pretty

# CLI endpoint override; use the environment for secrets to avoid shell history
uv run python -m benchmark doctor --mcp-url 'https://alternate.example/mcp' --fast
```

If connection fails, `doctor` returns an actionable error naming the **selected server address**, never the bearer token. For a full `run-three-arm` experiment, the server is checked before new results are recorded. **Do not change a running/resumed experiment's endpoint:** its manifest binds the original `mcp_url` so datasets from different servers cannot be silently merged. This change is best applied after your current 150-run experiment finishes. See [endpoint and authentication guide](docs/benchmark/mcp_endpoint_auth_0_6_7_3.md).

## 0.6.7: Fifty objectively scorable questions and GPT-5.2 three-arm evaluation

The `build-scorable` command derives **new**, narrowly answerable one-field questions from the frozen 42 completed reference archive responses. It publishes a **50-question CSV with the reference answers** (kept separate from the agent), an immutable reference-snapshot oracle and a candidate file. Answers include an explicit record identifier plus field, numeric tolerance and source provenance; no LLM is allowed to invent the expected value.

All three AstroAKD arms now default to **`gpt-5.2`**. Use `run-three-arm` with `--model gpt-5.2`; then `score-scorable` exports the question, reference-snapshot answer, all three actual agent answers (including wrong and free-text answers), and per-arm reference-match percentages. **These percentages compare to frozen archive snapshot values and are not independently verified scientific gold accuracy.** The original 32/10/8 Gold mixed dataset remains unchanged: this new 50-question objective pilot excludes multistep literature questions until their separate ADS/archival scientific references are approved.

Offline qualification: **197 passed, 1 optional live test skipped, 26 subtests passed**. See [full instructions](docs/benchmark/reference_anchored_scorable_0_6_7.md), [install guide](INSTALL_ASTROAKD_BENCH_0_6_7.md), and [qualification record](QUALIFICATION_0_6_7.md).

## 0.6.6.1 — Export all benchmark questions, answers and success rates to CSV

The new `export-answer-csv` command produces a 50-question reference-and-answer spreadsheet view,
150 per-task/per-arm rows, separate A, B and C answer CSVs, a percentage summary, and a
full source-field-value table. It reads **incomplete** three-arm `.progress.jsonl` journals safely.
These are direct inspections of the real pilot, not synthetic replay data.

```bash
uv run python -m benchmark export-answer-csv \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --references datasets/validated/gold_mixed_065_ref_42.jsonl \
  --reference-tasks datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --runs datasets/agent/astroakd_three_arm_runs.jsonl.progress.jsonl \
  --questions-csv datasets/reports/questions_references_ABC.csv \
  --arms-csv datasets/reports/answers_all_arms.csv \
  --summary-csv datasets/reports/three_arm_success_rates.csv \
  --reference-values-csv datasets/reports/reference_values.csv \
  --per-arm-dir datasets/reports/per_arm \
  --report datasets/reports/answer_review_report.json
```

**Rate definitions:** operational completion = completed / attempted; coverage = completed /
all benchmark questions; scientific success = correct / *gold-scored* runs. Missing gold
means **N/A (not 0%)**, even if the agent produced a plausible answer. Reference
columns are observations from returned archive tables, not independently approved answers.
See [Answer inspection guide](docs/benchmark/answer_inspection_and_success_rates_0_6_6_1.md).

## 0.6.6 — Gold-answer review and three-arm AstroAKD science evaluation

The 50-task native Gold mixed generation is now **real-host PASS**, but all 50 reference answers remain scientifically **unverified**. A five-task reference validation pilot (5/42 single-call tasks) was accepted structurally, and the original journal is preserved for `validate --resume`. 0.6.6 adds human-reviewed `gold-draft` / `gold-finalize` and independent `run-three-arm` / `score-three-arm` workflows. The three arms are **MCP only (no domain instruction)**, **MCP + AstroAKD agent instruction**, and **web search only (no MCP)**. The benchmark question-generation prompt is a separate artifact and is **not** used in the agent experiment.

See [0.6.6 full protocol and commands](docs/benchmark/gold_reference_and_three_arm_0_6_6.md) and [current qualification](QUALIFICATION_0_6_6.md). Offline suite: **186 passed; 1 optional live skipped**. Actual gold science and three-arm run still pending.

## 0.6.5 — Native Gold-inspired mixed generation

The earlier 50-question Gold-inspired draft was constructed by an **external offline builder** and did not use a live generation run. **Do not present it as a native AstroAKD-Bench/OpenAI-generated dataset.** Version 0.6.5 adds `generate --task-mix gold50` inside the benchmark: 32 `archive_driven`, 10 `coordinate_driven`, and 8 `literature_driven` tasks. The 42 ordinary tasks are produced using the existing OpenAI/MCP-bound generation engine, while literature tasks invoke MCP ADS-first research (with OpenAI web-search fallback) followed by LLM question authoring. Neither search nor authoring verifies scientific answers. See [native mixed generation guide](docs/benchmark/native_gold_mixed_generation_0_6_5.md).

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --instructions --mcp --model gpt-4.1-mini \
  --task-mix gold50 --count 50 --seed 123 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target \
  --output datasets/generated/gold_mixed_065.jsonl \
  --single-call-output datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --literature-output datasets/generated/gold_mixed_065_literature_8.jsonl \
  --csv-output datasets/generated/gold_mixed_065.csv \
  --pretty-output datasets/generated/gold_mixed_065_pretty.json \
  --report datasets/generated/gold_mixed_065_report.json --json-format pretty
```

Only the 42 ordinary MCP-backed tasks can be sent to the existing single-call `validate` command. The eight literature tasks require a future multi-step paper-and-observation validation stage. `--no-mcp` works but makes all tasks research-only, not executable through the current one-call validator. You may also use `--no-instructions` or `--backend hybrid` as in 0.6.4.4. The native Gold mixed generation completed successfully on the user's laptop in 0.6.5; reference verification and real three-arm science evaluation remain pending.

## 0.6.4.4 — OpenAI-generated questions: quick start

OpenAI generation is now the default. To **reproduce the 0.6.3 template results**, specify `--backend template`; old reports and accepted dataset hashes are not changed. These model-authored questions are **unverified candidates**, not known scientific answers.

**Default OpenAI + V1 instructions + Astroquery MCP** (MCP server started separately):

```bash
uv run --with openai python -m benchmark generate \
  --count 50 --seed 123 --model gpt-4.1-mini \
  --backend openai --instructions --mcp \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --output datasets/generated/llm_064_mcp.jsonl \
  --pretty-output datasets/generated/llm_064_mcp_pretty.json \
  --csv-output datasets/generated/llm_064_mcp.csv \
  --report datasets/generated/llm_064_mcp_report.json --json-format pretty
```

**Use OpenAI hosted web search instead of MCP:** change to `--no-mcp` and use different filenames. This mode does not attempt to connect to MCP and **does not yield MCP-executable reference calls**; the existing `validate` command does not accept these research-only tasks.

Toggle instructions with `--instructions` (default) and `--no-instructions`. Pass `--instructions-file path/to/prompt.md` for a custom prompt. `--backend hybrid` rewrites a template question conservatively, and `--backend template` uses no OpenAI API. Across all modes, question/target deduplication is retained, and `--pretty-output` + `--csv-output` produce inspection views.

**0.6.4.1 hotfix (retained):** The generator now safely normalizes *omitted* archive names in model-authored questions (for example, adds `Using VizieR,` to a question already bound to VizieR). It refuses questions naming another archive, inventing years, omitting a target, or requesting unsupported fields. Each normalization appears in task provenance (`archive_name_repaired`, `original_llm_question`) and the report count (`archive_name_repairs`). The prebound MCP query is never modified. The 0.6.4 laptop pilot failed after its first OpenAI batch due to a missing VizieR name; real 0.6.4.1 live qualification remains pending. If retrying after that failure, use new output/report names or explicitly `--replace`.

**0.6.4.2 ID reconciliation:** A second live pilot stopped at batch 6/10 with `OpenAI changed or omitted task IDs`. OpenAI may rewrite the artificial slot labels; these are *never* authoritative. The benchmark now maps questions to frozen task IDs only when target/archive/question constraints determine a unique assignment, records `task_id_repaired` and `original_llm_task_id` per repaired record, and reports `task_id_repairs`. Unsafe/ambiguous responses are retried once (`openai_batch_retries`) and rejected if still unresolved. No MCP call, scientific constraint, or reference fixture is mutated. An API batch retry incurs an extra model request. A 50-question live OpenAI generation subsequently succeeded in 0.6.4.2.

See [full 0.6.4 usage and comparison matrix](docs/benchmark/llm_generation_0_6_4.md) and [V1 workbook-derived instructions](docs/benchmark/llm_generation_instructions_v1.md). No historical workbook expected answers are imported as gold.

## Literature search and ADS fallback (0.6.4.4)

The external [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp/wiki)
provides `astroquery_check_auth` and `ads_query_compact`; AstroAKD-Bench never
sends `API_DEV_KEY` to OpenAI or calls the ADS API directly. Check the server
safely **without exposing credentials**:

```bash
uv run python -m benchmark literature-auth --json-format pretty
```

`ads_authenticated=true` and `ads_tool_available=true` indicate that the
benchmark will attempt ADS via MCP first. If the server process lacks
`API_DEV_KEY`, its ADS tool errors, or the server is unreachable, the benchmark
uses OpenAI Responses `web_search` (requires `OPENAI_API_KEY`). The fallback
reason is printed to stderr and saved in the successful evidence report.
A web-search result may be *prose with citations*, not JSON; both are now
accepted as **unverified research evidence**, not scientific gold.

```bash
uv run --with openai python -m benchmark literature-search \
  --query 'z=0.0809 quasar ultra-fast outflow 17300 km/s Chandra HETGS' \
  --max-results 5 \
  --output datasets/generated/literature_0644.json \
  --json-format pretty
```

If the key is in `.bashrc`, it must be present in the shell that **starts the
MCP server**; restarting the server after setting it may be necessary. The
benchmark saves only booleans, source URLs, papers or unverified prose, never
credential values. See [Gold Benchmark and ADS usage](docs/benchmark/gold_benchmark_dataset_and_ads.md).

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
| **0.6.1 — SEMANTIC_REPLAY_ARGUMENT_CANONICALIZATION** | ICRS default-aware fixture lookup and public Python workflow API | **ACCEPT** (five-task laptop replay) |
| **0.6.2 — READABLE_DATASET_EXPORT_AND_VALIDATION_PROGRESS** | Optional query/reference CSV and pretty JSON exports, progress messages and bounded validation waits | **Offline qualification; laptop live validation pending** |
| **0.6.3 — QUERY_DIVERSITY_AND_DEDUPLICATION_CLOSURE** | Default archive-target uniqueness, optional global-target uniqueness, answer-oriented prompts, offline duplicate-return audit | **Offline qualification PASS; live laptop qualification pending** |
| **0.6.4.1 — OPENAI_ARCHIVE_NAME_NORMALIZATION** | Deterministic missing-archive wording normalization, explicit provenance, original MCP calls preserved | **Offline focused PASS; first full retry stopped at batch 6 for changed task IDs** |
| **0.6.4.3 — GOLD_BENCHMARK_MCP_ADS_LITERATURE_FALLBACK** | Immutable ID recovery from unique validated target/archive matches; one bounded unsafe-batch retry | **157 offline tests PASS; full OpenAI laptop run pending** |
| **0.6.4.4 — LITERATURE_SEARCH_FALLBACK_OUTPUT_CLOSURE** | Web-search prose/JSON normalization, cited URLs, safe MCP ADS auth command | **Offline 172 PASS, live provider retry pending** |
| **0.6.4 — LLM_ASSISTED_SYNTHETIC_QUERY_GENERATION** | Default OpenAI+instructions+MCP, optional web_search without MCP, hybrid/template modes, optional custom prompt | **Offline mocks PASS; real OpenAI qualification pending** |

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
│   ├── diversity.py                      # Diversity and returned-data audit
│   ├── llm_generation.py                 # Responses API question generation + web search
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

## Diversity-aware task generation (0.6.3)

Use `generate` for new synthetic tasks. **Do not overwrite the frozen accepted
seed=42 baseline or the legacy seed=123 dataset** when starting a new study.
The generator now uses `--uniqueness archive-target` by default: each archive
receives **distinct astronomical targets before any possible reuse** (in fact
repeated archive-target pairs are rejected altogether). The `--uniqueness
global-target` alternative prevents target reuse across *all* archives.

The bundled seed pool has **22 targets**. Fifty questions are possible under
`archive-target` with ten per archive, but **global-target uniqueness for
50 questions will fail explicitly** until at least 50 unique `SkyTarget`
objects are provided via the Python API.

```bash
uv run python -m benchmark generate \
  --backend template \
  --count 50 --seed 123 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --output datasets/generated/diverse_063.jsonl \
  --csv-output datasets/generated/diverse_063.csv \
  --pretty-output datasets/generated/diverse_063_pretty.json \
  --report datasets/generated/diverse_063_report.json \
  --json-format pretty
```

**Deduplication protections:** normalized question text, identical MCP calls,
reused archive-target combinations and (for `global-target`) repeated names
across modules all cause candidates to be skipped; missing capacity raises a
specific `GenerationError` rather than silently padding with radius variants.
Custom seed names and coordinates must also be unique. Template selection is deterministic
for a given seed, modules, target pool and MCP function signatures. OpenAI-authored wording is not byte-reproducible.

**Answer-oriented tasks** draw on observed fields of SIMBAD, MAST, HEASARC,
Gaia and the two supported VizieR catalogs: identifiers, coordinates,
instruments, proposal IDs, exposure/duration, astrometry and photometry.
The design draws on the question/expected-answer structure in the supplied
*Astro Benchmark V1.xlsx*. It does **not** copy workbook expected answers or
claim that the new questions have verified gold answers. The `intent` and
`answer_spec.expected_columns` fields specify what a later validator/evaluator
should check. Only fields actually returned by a given archive/catalog can
support an answer. `--question-style discovery` retains the older general
"search archive" style for comparison, with the new uniqueness policy still on.

**Audit existing tasks without a server or API key:**

```bash
uv run python -m benchmark audit-diversity \
  --input datasets/generated/diverse_063.jsonl \
  --report datasets/generated/diverse_063_audit.json \
  --json-format pretty
```

**Audit previously validated responses**, without requerying archives:

```bash
uv run python -m benchmark audit-diversity \
  --input datasets/generated/synthetic_queries.jsonl \
  --references datasets/validated/reference_answers.jsonl \
  --report datasets/validated/reference_diversity_audit.json \
  --json-format pretty
```

The audit separates duplicate wording, identical calls, reused targets and
**identical returned table rows**. It excludes empty tables from return-data
duplicate counts. Exact equality of the *returned subset* (especially a
truncated MAST response) is an advisory duplication signal, not proof that
underlying complete catalogs are identical. Cross-version reference datasets
with unchanged calls but changed input file hashes are flagged as **not
byte-exact reference provenance**. The `validate` summary now includes
`returned_data_redundancy`, a separate `diversity_gate`, and a summary of
answer-field availability; structural `quality_gate` is not silently conflated
with query diversity.

**Reusable Python API:** `AstroAKDBench.generate_queries(...,
uniqueness="archive-target", question_style="answer-oriented")` and
`AstroAKDBench.audit_diversity(tasks=..., references=...)`. For 50 globally
unique objects, pass a tuple of 50 or more scientifically verified custom
`SkyTarget` seeds. See [Diversity and deduplication](docs/benchmark/query_diversity_0_6_3.md)
and [Python API](docs/benchmark/python_api.md).

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
  --csv-output datasets/generated/synthetic_queries.csv \
  --pretty-output datasets/generated/synthetic_queries_pretty.json \
  --report datasets/generated/generation_report.json \
  --json-format pretty
```

Only run this if intentionally regenerating a dataset. The distributed 50-task seed=42 dataset is already accepted; `--replace` would intentionally replace an existing file. Generation makes **no astronomy archive queries** and **no LLM calls**. The CSV and indented JSON array are **optional inspection copies**; the canonical `.jsonl` remains compact to preserve deterministic hashes and stream processing. `--json-format pretty` affects the summary report and console, **not** the JSONL records. The `.json` saved with `--pretty-output` contains complete records, not just a summary.

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

### Generate inspectable data and diagnose a slow validation — 0.6.2

For a **new** seed=123 candidate dataset (without `--strict-accepted-020`), first run a **single-task pilot** with a short timeout and a single attempt:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/my_50_queries.jsonl \
  --limit 1 --attempts 1 --timeout 30 --delay 0 \
  --output datasets/validated/my_50_references.jsonl \
  --report datasets/validated/my_50_validation_report.json \
  --csv-output datasets/validated/my_50_references.csv \
  --pretty-output datasets/validated/my_50_references_pretty.json \
  --json-format pretty
```

The validator now writes **START**, **WAITING** (every 15 seconds during network I/O), and **DONE** messages to **stderr**, plus a preflight notification. This avoids mistaking slow external archive requests for CPU-bound processing. Disable messages with `--quiet-progress`. A single query attempt is bounded by `--timeout`; a server-side query already started may continue running after a client timeout.

When the pilot completes, resume without `--limit`, keeping the same input/output/report/export paths and the same endpoint/row and response-size constraints:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/my_50_queries.jsonl \
  --resume --attempts 1 --timeout 30 --delay 2 \
  --output datasets/validated/my_50_references.jsonl \
  --report datasets/validated/my_50_validation_report.json \
  --csv-output datasets/validated/my_50_references.csv \
  --pretty-output datasets/validated/my_50_references_pretty.json \
  --json-format pretty
```

If a validation is interrupted after a task completes, the `.progress.jsonl` journal retains that result and `--resume` skips it. A `.jsonl` reference file is published only when **all tasks have a disposition**; the optional CSV/pretty JSON are updated at the end of each completed pilot/resume invocation and show **processed tasks only**. If there is no manifest yet, preflight did not finish and `--resume` cannot be used. Do not use `--replace` unless intentionally discarding prior results. The 0.6.2 exports never alter the canonical JSONL bytes or hash.

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
- Comprehensive scientific statement verification is **not yet implemented**; LLM-generated variations have been available since 0.6.4. Offline MCP replay is implemented, but unsupported calls fail closed and the LLM itself is not necessarily offline.
- AstroAKD-Bench does **not** claim authorship of the NASA IMPACT Astroquery MCP server or attribute its contributors to the benchmark.

See [CHANGELOG.md](CHANGELOG.md) for cumulative release history and [docs/benchmark](docs/benchmark/) for implementation details. **Every new release updates the root README, root CHANGELOG, package metadata, CLI examples, and relevant docs together.**

## Gold Benchmark task families and ADS literature fallback (0.6.4.3)

The separate Gold Benchmark workbook contributes 31 numbered examples: 20
`archive_driven`, 7 `coordinate_driven`, and 4 `literature_driven`. The default
instructions at `docs/benchmark/llm_generation_instructions_v1.md` now cover all
three and preserve the workbook's scientific distinctions.

For **literature discovery**, AstroAKD-Bench uses only the separate NASA IMPACT
**Astroquery MCP** server, first querying `astroquery_check_auth`. When ADS is
configured by `API_DEV_KEY` in the server environment, it calls
`ads_query_compact` over MCP. When ADS is unavailable, it falls back to
OpenAI Responses `web_search` rather than terminating due to a missing ADS key.
The ADS key is never placed in client requests or saved in benchmark output.

```bash
uv run --with openai python -m benchmark literature-search \
  --query 'nearest tidal disruption event NICER observation papers' \
  --json-format pretty \
  --output datasets/generated/tde_literature_research.json
```

This is a **separate evidence-research stage**. Existing `generate` continues to
make single-archive candidate tasks; literature-driven multi-stage tasks need a
follow-on archive validation stage and cannot claim verified answers merely from
ADS or web-search results. See
[Gold Benchmark/ADS guide](docs/benchmark/gold_benchmark_dataset_and_ads.md).

## GPT-5.2 detailed answer / performance reporting (0.6.7.1)

`score-scorable` now optionally creates **detailed long-form CSV (150 task/arm rows)**,
**A/B/C performance summary CSV**, **per-task resource-use CSV**, and three reproducible
bar charts (reference-match percentage, mean wall time per attempted question,
recorded total tokens). Plots are exported as PNG **and** SVG; only the reporting
command needs optional `matplotlib` (`uv run --with matplotlib`). Full agent answers,
including incorrect answers, structured or free-form text, source identifiers,
errors and abstention flags, are preserved unchanged. Run progress and oracle hashes
are checked before scoring; existing candidate and agent journal bytes are not modified.

For the real 5-question GPT-5.2 pilot the frozen-snapshot match percentages were
A **5/5=100%**, B **5/5=100%**, C **1/5=20%**; mean observed wall times were
A **21.46 s**, B **7.58 s**, C **16.95 s**, and recorded token totals were
A **276,739**, B **308,724**, C **101,552**. **These are partial-pilot snapshot
matches, not independently verified scientific gold accuracy.** Per-arm resource
use can only be compared fairly across the same attempted question set.

See [0.6.7.1 reporting guide](docs/benchmark/three_arm_detailed_reporting_0_6_7_1.md)
and [installation instructions](INSTALL_ASTROAKD_BENCH_0_6_7_1.md).

## 0.6.6 — Scientific gold references and AstroAKD three-arm evaluation

**AstroAKD-Bench** constructs and scores the benchmark; **AstroAKD** is the evaluated agent. The user-provided AstroAKD agent instruction is retained unchanged in `docs/agent/AstroAKD_Instruction.md` and is never confused with the synthetic-generation instructions under `docs/benchmark/`.

This release adds four native commands: `gold-draft`, `gold-finalize`, `run-three-arm`, and `score-three-arm`. The gold lifecycle **never equates MCP reference-table structural acceptance with scientific truth**. The three arms use: (A) MCP only without detailed AstroAKD agent instructions; (B) MCP plus the full AstroAKD agent instructions; (C) OpenAI hosted web search only, without MCP. All receive the same question set and model. The approved gold answers and reference journal are never supplied to the agents. Auditable runs include per-task tool traces, source URLs, model usage, latency, and structured answer extraction.

Your real laptop dataset's 50 mixed tasks (32 archive / 10 coordinate / 8 literature) and the five completed single-call reference records are carried forward **unchanged**. No true gold answers have been approved yet. To continue the current 5/42 reference collection without restarting it, use `validate --resume` with the same `.jsonl` output and report names. See [0.6.6 Gold and three-arm guide](docs/benchmark/gold_reference_and_three_arm_0_6_6.md), [host installation and qualification](INSTALL_ASTROAKD_BENCH_0_6_6.md), and [full conversation handoff](CONVERSATION_HANDOFF_THROUGH_0_6_6.md).

### 0.6.7.2 resume compatibility

`run-three-arm --resume` now correctly compares the JSON-serialized arm list to its saved manifest. Pilot journals from 0.6.7 and 0.6.7.1 do **not** need any conversion. Keep the same question set, `AstroAKD_Instruction.md`, model, endpoint and resource budgets; do not use `--replace`. See `INSTALL_ASTROAKD_BENCH_0_6_7_2.md`.
