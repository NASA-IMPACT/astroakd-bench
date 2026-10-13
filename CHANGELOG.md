# AstroAKD-Bench Changelog

All significant changes to the **independent AstroAKD-Bench project** are documented
here. This history is separate from the external `astroquery-mcp` project's
releases: AstroAKD-Bench versions track benchmark capabilities, not versions
of Astroquery or the MCP server.

The current implemented benchmark version is **0.5.0**.
Dates are in UTC. Release statuses distinguish **offline implementation
qualification** from **real laptop / live-service qualification**.

## [Unreleased]

- Planned: 0.6.0 offline MCP record/replay and expanded scientific claim verification.

## [0.5.0] - 2026-10-13

### Added

- `AUTOMATED_EVALUATION_AND_SCORING`: new `benchmark/evaluator.py` and `benchmark evaluate` command score recorded agent tool selection, method selection, semantic parameter agreement, successful astronomical execution, reference-result agreement and a restricted set of answer claims. Scores are out of 100 and published as compact JSONL, CSV and JSON summary.
- Distinct **technical evidence score** and `scientific_answer_gate=INDEPENDENT_REVIEW_REQUIRED`; no claim of comprehensive astrophysical accuracy. Report `REVIEW` for truncated Gaia-style payloads, row-count drift and unassessed claims, rather than silently granting accuracy credit.
- MCP trace fingerprint checks, input coverage and hash validation, duplicate-ID rejection, no overwrite without `--replace`, and per-module aggregates.
- `--json-format {compact,pretty}` on CLI commands for console and JSON summary reports; compact remains default. `.jsonl` remains canonical compact one-record-per-line. New `benchmark inspect` creates a bounded, readable view of `.jsonl` or `.json` without modifying input files.
- Root-level `datasets/` layout for new generation, reference, agent and evaluation runs. Migration script refuses to merge existing roots and verifies frozen accepted dataset checksums. Accepted generated and reference files included in package with their original SHA-256.
- Standalone-repository `pyproject.toml` with FastMCP dependency and optional OpenAI extra. Complete updated root `README.md`, `CHANGELOG.md` and `docs/benchmark/evaluation_and_scoring.md` included in archives.

### Qualification

- Offline: **PASS**; 94 tests passed and one optional live-server test skipped, including fourteen new 0.5.0 tests and the complete previous regression suite. Five-task historical 0.4.1 OpenAI trace scored against frozen 50-task reference set; mean technical evidence score **94/100**, three technical PASS and two REVIEW (including truncated Gaia). This is not a science-accuracy percentage.
- Historical 0.4.1 laptop live pilot: **ACCEPT** for five-task execution/tracing (5/5 successful queries, zero rejected and zero failed MCP calls).
- 0.5.0 real laptop end-to-end qualification: **PENDING**.

### Boundaries

- AstroAKD-Bench is a standalone repository built to work with the NASA IMPACT Astroquery MCP server; it is not included in that server's repository. No unrelated MCP-server contributor attributions are included.
- Comprehensive scientific statement verification and MCP record/replay are future work, not 0.5.0 functionality.

## [0.4.1] - 2026-10-13

### Changed

- `AGENT_TOOL_SELECTION_AND_RECOVERY_CLOSURE`: explicit, single-archive
  references in natural-language questions now guide and constrain the agent's
  MCP archive selection. The hint is derived **only** from the question text;
  expected module, gold parameters and reference answers are never supplied.
  Questions naming multiple archives remain unrestricted by this hint.
- Strengthened tool-calling instructions and executable function descriptions:
  SIMBAD `object_name`, MAST `coordinates`, HEASARC `position`, Gaia
  `coordinate`, and VizieR `coordinates`. `max_rows` is MAST-only.
- Rejection messages include actionable recovery guidance. The OpenAI adapter
  can issue one additional prompt when a model produces an answer without a
  successful astronomical MCP execution and turn/call budgets remain.
- Added `query_evidence`, `successful_execute_count`, rejected/failed tool
  counts in per-task records and aggregate reports. An agent answer without a
  successful `astroquery_execute` is flagged for **REVIEW**; a successful
  MCP response is still not scientifically verified correctness.
- Versioned the routing policy in execution manifests, preventing resume of
  0.4.0 journals under changed 0.4.1 behavior.
- Corrected the root `README.md` to describe **AstroAKD-Bench** as the main
  project, based on its previous 0.3.0 benchmark README. The Astroquery MCP
  server is identified as a dependency, not as the benchmark project.
  No upstream MCP-server contributors are attributed to AstroAKD-Bench.
  Both complete root `README.md` and `CHANGELOG.md` ship in this release.

### Qualification

- Offline regression: **PASS**, 80 tests passed; one optional real-server
  integration test skipped. Added HEASARC/Gaia routing, MAST-only argument,
  real-trace reproduction, error-recovery and missing-execution-evidence tests.
- 0.4.0 laptop pilot: five `gpt-4.1-mini` tasks produced answers, but only
  three MCP executions succeeded; five calls were rejected, exposing the
  routing defects addressed here.
- 0.4.1 live laptop OpenAI regression: **ACCEPT** (five-task pilot, five successful MCP executions and zero rejected calls). Full 50-task agent run and scientific-answer correctness were not established.

### Limitations

- `query_evidence=observed` only means a server `success=true` response,
  **not** correctness of astronomy interpretations or final agent answers.
- The lexical routing restriction applies only when exactly one supported
  archive is explicitly named in the question; it is not a general
  multi-archive planner. Scientific scoring remains planned for 0.5.0.

## [0.4.0] - 2026-10-13

### Added

- `AGENT_EXECUTION_AND_TRACING`: `uv run python -m benchmark run` loads the
  accepted candidate and reference datasets, checks IDs, coverage and SHA-256,
  and independently asks an agent each candidate question.
- Bounded MCP tool proxy that captures attempted tools, arguments, outcomes,
  elapsed times, SHA-256 response fingerprints, size/truncation, and output
  excerpts; enforces an explicit read-only service/method and parameter policy.
- Optional OpenAI Chat Completions tool-calling agent (`--agent openai`) and
  pluggable external async AstroAKD adapter (`--agent external --adapter`).
  `--agent echo` is a harness-only test and explicitly not an AI evaluation.
- Durable per-task execution journal, `--resume`, `--replace`, output manifest,
  model/runtime provenance, completion/error reporting, and per-archive totals.
- Independent agent prompts: reference calls/results never enter the agent's
  context. No automated science scoring until planned 0.5.0.
- Added `docs/benchmark/agent_execution.md` and a cumulative root changelog.
  The original 0.4.0 package omitted the full benchmark-focused root README;
  0.4.1 corrects the documentation and packaging.

### Qualification

- Offline regression: **PASS**, 75 tests passed and one optional live-server
  test skipped. Includes mocked OpenAI tool-calling, resumed runs, reference
  isolation, unsafe tool rejection, and compatibility with the accepted
  0.2.0 dataset.
- Real laptop OpenAI five-task pilot: **EXECUTED**, five final responses,
  eight MCP calls, three successful archive executions, five rejected calls.
  HEASARC and Gaia routing defects identified; milestone 0.4.0 did not
  establish scientific correctness or full-run host acceptance.

### Limitations

- `COMPLETE` indicates all tasks have execution records, **not** accuracy.
  The `echo` harness mode receives `quality_gate=HARNESS_ONLY`.
- The OpenAI SDK/API is **optional**, and is used only when that adapter is
  selected; previous generation and reference validation are API-free.
- Existing AstroAKD agent integration needs an async adapter that calls the
  traced gateway. Direct external MCP connections are not observed.
- 0.5.0 will implement scoring; 0.6.0 will implement offline replay.

## [0.3.0] - 2026-10-13

### Added

- `REFERENCE_VALIDATION`: `uv run python -m benchmark validate` executes
  allowlisted 0.2.0 reference calls through the local FastMCP HTTP endpoint.
- Response-shape, row-count and truncation checks, with optional advisory
  coordinate evidence; every attempted task receives an explicit disposition.
- Per-task durable progress journal, execution manifest, `--resume`, optional
  strict accepted-0.2.0 dataset hash check, and fail-closed schema drift check.
- Configurable timeouts, bounded retries, delays, response-size limits, a
  five-task pilot option, and reports with counts by archive and disposition.
- Offline regression tests for classification, error handling, resume,
  safety, and a mocked execution of all 50 accepted tasks.

### Qualified

- Offline implementation: **PASS** (60 tests passed, one optional live test
  skipped in the delivery environment).
- Laptop pilot: **PASS** for five `accepted_nonempty` tasks (one per archive).
- Completed laptop run: **ACCEPT / CLOSED**, with all 50 candidates processed,
  `status=COMPLETE`, and `quality_gate=PASS`.
- Dispositions: 48 `accepted_nonempty`, 2 `accepted_empty`; the two empty
  results were HEASARC queries. SIMBAD, MAST, Gaia and VizieR returned ten
  nonempty results each; HEASARC returned eight nonempty.
- Validated output SHA-256:
  `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`.

### Limitations

- `accepted_*` means **structural response acceptance**, not independent
  astrophysical truth or agent-answer correctness. Scientific gold-label
  checks remain to be developed.
- The MCP server supports `--max-rows` for MAST `query_region` only; other
  archives require size-bound handling.
- No autonomous agent execution, evaluation scoring, or offline replay yet.

## [0.2.0] - 2026-10-13

### Added

- `SYNTHETIC_QUERY_GENERATION`: `uv run python -m benchmark generate`
  produces deterministic, UTF-8 JSONL benchmark candidates from templates,
  curated astronomical seed objects, and MCP introspection metadata.
- Five-archive support: SIMBAD, MAST, HEASARC, Gaia, and VizieR, with a strict
  read-only method allowlist.
- Seeded reproducibility, module selection, balanced task distribution,
  signature provenance, dataset/schema SHA-256 fingerprints, atomic output,
  and explicit overwrite protection.
- Narrow, documented signature adapters for MAST and VizieR wrappers when
  runtime introspection exposes only generic argument collectors.
- CLI and generator unit tests, including safety and reproducibility checks.

### Fixed (0.2.0 compatibility correction; no version bump)

- Resolved a laptop generation failure in `heasarc.query_region` caused by the
  introspection layer treating variadic `**kwargs` as a mandatory named
  argument. Added regression coverage for HEASARC's real signature form.
- The correction preserves strict validation of other required parameters
  without changing the production MCP server.

### Qualified

- Offline implementation and focused HEASARC correction: **PASS**.
- Laptop generation: **ACCEPT / CLOSED**, producing 50 unique candidate tasks
  (10 per archive), zero archive executions, and `status=PASS`.
- Accepted candidate dataset SHA-256:
  `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`.
- Candidate tasks remained `candidate_unvalidated` until milestone 0.3.0.

## [0.1.0] - 2026-10-13

### Added

- `LOCAL_MCP_CONNECTION`: asynchronous FastMCP HTTP client for the default
  laptop endpoint `http://127.0.0.1:8000/mcp`.
- MCP ping and tool catalog checks; discovery of Astroquery modules, methods,
  and callable signatures.
- `doctor` fast/full/smoke diagnostics, discovery CLI commands, and a
  read-only SIMBAD object query with structured JSON reporting.
- Handling for transport errors, MCP protocol failures, and server-returned
  application-error dictionaries.
- Offline client tests and optional real-server integration test.

### Qualified

- Offline unit suite: **PASS** (13 tests passed, one optional live test
  skipped in the original release qualification).
- Laptop: **ACCEPT / CLOSED**. `doctor --fast`, full `doctor`, and
  `doctor --smoke` all passed against the local MCP server. The server
  advertised seven MCP tools and 16 astronomical modules; SIMBAD exposed
  20 query functions; M31 lookup returned one row.

## Documentation maintenance rule

For **every future AstroAKD-Bench version**, in the **same delivery**:

1. Add a new version heading above older releases, documenting changes,
   compatibility fixes, tests, limitations and qualification status.
2. Update the root `README.md` AstroAKD-Bench section and `docs/benchmark/astroakd_bench.md` with the implemented version, commands,
   feature table and supported workflow. Keep planned features clearly
   labeled as not implemented until they are tested.
3. Keep `benchmark/__init__.py` version, command-line version reporting,
   README and changelog consistent. Do not bump the version for a
   documentation-only correction unless explicitly decided.
4. Record **offline** and **real-laptop** qualification separately, and do not
   describe structural archive response validation as verified scientific
   answer correctness.
5. Preserve accepted input artifacts and their hashes. If inputs or schemas
   change, document the impact on reproducibility and replay compatibility.

Starting in 0.4.0, the root `README.md` retains the original MCP server
documentation, and the root `CHANGELOG.md` maintains AstroAKD-Bench history.
Both will be updated with every new benchmark version.
