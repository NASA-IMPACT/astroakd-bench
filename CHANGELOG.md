# AstroAKD-Bench Changelog

All significant changes to the **independent AstroAKD-Bench project** are documented
here. This history is separate from the external `astroquery-mcp` project's
releases: AstroAKD-Bench versions track benchmark capabilities, not versions
of Astroquery or the MCP server.

The current implemented benchmark version is **0.6.4**.
Dates are in UTC. Release statuses distinguish **offline implementation
qualification** from **real laptop / live-service qualification**.

## [Unreleased]

- Planned after 0.6.1: broader scientific claim verification, multi-archive workflows and frozen evaluation suites.

## [0.6.4] - 2026-10-14

### Added

- **LLM_ASSISTED_SYNTHETIC_QUERY_GENERATION:** default `generate` backend is `openai`, with workbook-derived instructions (`--instructions`) and MCP signature discovery (`--mcp`). `--backend hybrid` conservatively rewrites template prompts, and `--backend template` preserves the deterministic, API-free 0.6.3 workflow.
- `--no-instructions` for ablations, `--instructions-file` for reusable experimental instructions, and `--no-mcp` for the OpenAI Responses API hosted `web_search` alternative. A web-search call is **required and auditable** for each no-MCP batch; there is no network fallback to MCP.
- The generated calls and constraints are locked to MCP-discovered signatures when MCP is enabled. In no-MCP mode, `reference_call=null`, candidates carry a research-only execution track, and the legacy MCP validator rejects them rather than treating guessed local method schemas as verified.
- API facade accepts the same backend/instructions/MCP options, including injected fake clients for offline qualification. Source URLs are retained only if exposed by provider web-search tool metadata. New reports include generation engine, model, instruction hash, mode, number of model calls, number of observed web searches, and caveats about nondeterministic wording.
- Added `docs/benchmark/llm_generation_instructions_v1.md` derived from three worksheets in *Astro Benchmark V1(1).xlsx*, emphasizing actual observation identifiers, proposals, instruments, exposure times, filters and timestamps while prohibiting unsupported detailed constraints or copied expected answers.
- Updated standalone README, cumulative changelog, usage/qualification docs and expanded offline mocks for all four instructions/MCP combinations. Preserved historical frozen dataset bytes and reference fixture.

### Qualification

- Full offline test suite PASS (see `QUALIFICATION_0_6_4.md`); **live OpenAI Responses API + hosted web search and MCP laptop runs remain PENDING**. Mocked web-search calls are not presented as live external qualification.

## [0.6.3] - 2026-10-13

### Added and changed

- **QUERY_DIVERSITY_AND_DEDUPLICATION_CLOSURE:** Default `generate
  --uniqueness archive-target` prevents repeated source/target pairs within
  each astronomical archive; `--uniqueness global-target` prevents reuse
  across all archives. Both enforce distinct normalized question strings and
  unique exact MCP calls. Deterministic round-robin archive balance retained.
- Explicit seed-pool feasibility errors: the built-in 22-object seed pool
  supports 50 archive-target-unique questions across five archives but cannot
  supply 50 globally unique targets. Custom `SkyTarget` coordinates and names
  must be unique; strict policy failures never trigger archive queries.
- `--question-style answer-oriented` (new default), using observationally
  documented candidate answer fields and archive-specific question intents
  modeled on the user's *Astro Benchmark V1.xlsx*. Each task carries
  `intent` and an **unverified** `answer_spec`; `--question-style discovery`
  retains general historical search phrasing. No ungrounded gold answers.
- `benchmark/diversity.py` and `audit-diversity` CLI: offline candidate
  deduplication audit, exact returned table-data hashing, and advisory
  answer-column availability checks, including distinct field contracts for
  VizieR II/246 versus I/355 and HEASARC xmmmaster versus chanmaster.
- Validation reports now include `returned_data_redundancy`,
  `answerability_advisory` summary, and separate `diversity_gate`; empty
  results and cross-archive similarities are not incorrectly counted as
  duplicate astronomical records. Saved reference JSONL is unchanged.
- Reusable `AstroAKDBench.generate_queries` selection options and
  `AstroAKDBench.audit_diversity` API, updated README, usage docs, source
  tests, qualification report and conversation handoff summary.

### Scientific qualification and preserved baselines

- Historical uploaded seed=123 dataset: 50 distinct strings, 50 distinct
  exact MCP calls, but **28 reused archive-target pairs**; conservative
  0.6.3 returned table audit found 10 redundant nonempty returned subsets
  (five groups). Its 50 structurally accepted references are **not**
  independent astrophysical gold and came from a different candidate-file
  hash than the later 0.6.2 generation, despite equal calls.
- Version 0.6.3 implementation and offline regression tests passed; live
  MCP regeneration and validation of the new diverse batch remain pending.
- Frozen accepted seed=42 candidate SHA-256
  `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`
  and reference SHA-256
  `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`
  remain untouched, as does the replay-fixture fingerprint
  `31a8ae8644765e6a7a00995883415e32f4412fd9ce7669bf760515567b3522fe`.

## [0.6.2] - 2026-10-13

### Added

- `READABLE_DATASET_EXPORT_AND_VALIDATION_PROGRESS`: optional `--csv-output` and
  `--pretty-output` on `benchmark generate` and `benchmark validate`. They
  create complete, readable tabular and indented JSON-array views alongside
  **unchanged compact canonical JSONL**. The same options are available from
  the reusable `AstroAKDBench` Python API.
- Generate CSV includes questions, target, sky coordinates, constraints,
  catalog and exact MCP parameters; validation CSV includes disposition,
  row counts, evidence hashes, errors and the original question.
- Validation emits flush-on-write preflight, per-task START/DONE, and 15-second
  WAITING messages to stderr (disable with `--quiet-progress`). Whole query
  attempts are limited by the configured timeout, and retryable timeouts are
  classified as transport errors. Journaling and resumability are retained.
- Path/collision, overwrite and extension checks on optional exports, atomic
  export publication, and CSV spreadsheet-formula injection protection.
- New local troubleshooting and reusable CSV/pretty-export documentation.

### Qualification

- Uploaded seed=123 generation run verified: 50 candidates, schema unchanged,
  canonical candidate SHA-256 `dbcfebaad9687f09c7778b83fc7e1e85d301c8548b30d15b01847ed62bb2b2cd`.
- The user's `validate` run apparently stalled without terminal feedback;
  its precise blocking archive/operation was not identifiable from the uploaded
  generation files. Live laptop qualification of these improvements is pending.
- Frozen seed=42 candidate, accepted references and replay fixtures preserved.

## [0.6.1] - 2026-10-13

### Changed

- `SEMANTIC_REPLAY_ARGUMENT_CANONICALIZATION`: replay first checks the original
  exact tool/argument hash, then a narrowly restricted fallback for omitted
  versus explicit `"frame": "icrs"` within the approved MAST, HEASARC, Gaia,
  and VizieR coordinate parameter. No other arguments are canonicalized.
- Added an ephemeral semantic lookup index without altering fixture JSON,
  original per-call fingerprints, response payloads or fixture integrity SHA.
  Ambiguous canonical aliases are rejected instead of selecting a response.
- Added `benchmark.api.AstroAKDBench`, a documented, root-relative Python
  facade for generation, validation, agent execution, offline scoring, fixture
  construction, loading and replay. Python APIs call the existing CLI engines;
  no parallel logic, upstream MCP-server modification, or OpenAI dependency
  was introduced for query generation.
- Expanded independent-project root README, replay guide, Python API examples,
  usage/extension instructions, tests, and package version metadata.

### Qualification

- 0.6.0 live-record and replay of captured agent calls: **ACCEPT** on the
  user's laptop for 5/5 tasks, with exact response SHA-256 equality and no
  MCP network access during replay.
- 0.6.0 reference-derived fixture replay had 1/5 successful because four
  otherwise equivalent agent calls omitted an explicit ICRS coordinate frame.
- 0.6.1 offline regressions verify all 50 original fixture entries replay with
  omitted ICRS frame and that altered coordinates, radii, catalogs, top-level
  limits, and unsafe operations cannot match. Frozen dataset and fixture hashes
  remain unchanged. The full offline regression suite: **120 PASS, 1 SKIP**.
  Real laptop 0.6.1 five-task replay qualification subsequently **ACCEPTED** (5/5 successful, no replay misses).

### Limits

- Offline replay freezes tool responses, not LLM behavior, model parameters or
  final-answer scientific correctness. Semantic equivalence is intentionally
  restricted to the documented default coordinate frame for allowlisted tools.

## [0.6.0] - 2026-10-13

### Added

- `REPLAY_AND_BENCHMARK_RELEASE`: new `benchmark/replay.py` with integrity-checked,
  read-only MCP fixtures, a no-network replay client, and a transparent live
  recorder. Fixture lookups match the exact MCP tool name and canonical JSON
  arguments. Unknown calls produce an explicit `OFFLINE_REPLAY_MISS` without
  a live-archive fallback.
- `benchmark build-fixtures` constructs 50 deterministic, offline source-backed
  MCP fixtures from the accepted 0.3.0 reference data, using a documented
  **bootstrap** tool catalog. No internet connection, MCP server or LLM call
  is required; these are validated structural references, not scientific truth.
- `benchmark run --mcp-mode {live,record,replay} --fixtures PATH` selects live
  network access, automatic fixture recording, or deterministic offline replay.
  `record` saves the actual advertised MCP catalog and each successful/error
  tool result with fsynced atomic publication; `replay` uses no HTTP client.
- Fixture content and individual results are SHA-256 authenticated against the
  recorded payload. Mutation, unsafe operations, duplicate/conflicting calls,
  mismatched candidate fingerprints and incompatible run-resume manifests are
  rejected. Recorded fixtures distinguish from gold reference data passed to
  the scoring process; agents receive only response data for the calls they make.
- The release includes root README/CHANGELOG, root-level accepted datasets,
  a built offline fixture, a detailed replay guide, test suite, and local
  installation/qualification instructions. No changes to the external NASA
  IMPACT Astroquery MCP server or its contributor attribution.

### Qualification

- User-uploaded 0.5.1 evaluation results checked: two saved compact JSONL
  streams exactly match their respective pretty JSON arrays, each containing
  five scores [100,100,100,80,90]. Mean 94/100; 3 technical PASS, 2 REVIEW.
  These are **technical evidence** scores and do not establish scientific
  accuracy for the 50-task benchmark.
- Offline unit suite: **PASS**, 110 tests passed with one optional live HTTP test skipped (previous regressions plus replay tests),
  including the actual frozen 50-task fixture build, no-network agent replay,
  recorder capture, fingerprint tamper rejection, missing-call handling and
  fixture-file protection. The optional real MCP test remains skipped.
- Real laptop 0.6.0 five-task record/replay (live-captured fixture): **ACCEPT**. Generic reference-derived replay had the ICRS mismatch corrected in 0.6.1.

### Limitations

- Archive replay can be offline, but OpenAI API agents still need internet.
  Reference-derived fixture catalogs are bootstrap schemas, not an exact copy
  of the live server's catalog; `record` captures a live catalog when needed.
- Fixture equality does not guarantee identical LLM wording, token usage, or
  scientific interpretation. A replay miss is **not** a live archive error.

## [0.5.1] - 2026-10-13

### Added

- `PRETTY_SCORE_EXPORT_CLOSURE`: `benchmark evaluate --pretty-output PATH.json` writes **all** per-task scoring records as an indented JSON array to a separate saved file. The ordinary compact, streaming-friendly `.jsonl` and CSV files are still emitted as before.
- `--pretty-output` is independent of `--json-format {compact,pretty}` (the latter continues to control console and summary-report formatting only). The new output is always pretty-formatted.
- Reject `.jsonl` pretty-export destinations, collisions with any input/output path, and existing artifacts without an explicit `--replace`. Individual JSON output is published via atomic rename.
- Added regression tests for saved-file contents, equality with compact JSONL, CLI integration, destination safety, unchanged accepted data fingerprints, and optional export behavior.
- Updated the root `README.md`, `CHANGELOG.md`, detailed scoring documentation, installation guide, package version, and release archives. AstroAKD-Bench remains an independent repository; the NASA IMPACT Astroquery MCP server is an external dependency.

### Qualification

- Offline: **PASS** — 100 executed tests passed; one optional live MCP test skipped. The historical five-task 0.4.1 OpenAI trace scored identically to version 0.5.0 (technical mean 94/100, three PASS and two REVIEW).
- Frozen accepted candidate/reference SHA-256 fingerprints preserved. No new archive queries or OpenAI API calls were made.
- Real-laptop 0.5.1 qualification: **PENDING**. Score outputs do not certify astrophysical correctness.

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
