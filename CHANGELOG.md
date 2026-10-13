# AstroAKD-Bench Changelog

All significant changes to the **AstroAKD-Bench subproject** are documented
here. This history is separate from the upstream `astroquery-mcp` project's
releases: AstroAKD-Bench versions track benchmark capabilities, not versions
of Astroquery or the MCP server.

The current implemented benchmark version is **0.4.0**.
Dates are in UTC. Release statuses distinguish **offline implementation
qualification** from **real laptop / live-service qualification**.

## [Unreleased]

- No unreleased implementation changes are recorded.
- Planned (not implemented): 0.5.0 automated evaluation and scientific
  scoring, and 0.6.0 offline record/replay and benchmark packaging.

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
- New `docs/benchmark/agent_execution.md`, updated project guide, and moved
  cumulative changelog to the repository root. The existing root README is
  **extended rather than overwritten**, preserving server documentation.

### Qualification

- Offline regression: **PASS**, 75 tests passed and one optional live-server
  test skipped. Includes mocked OpenAI tool-calling, resumed runs, reference
  isolation, unsafe tool rejection, and compatibility with the accepted
  0.2.0 dataset.
- Real laptop MCP + actual agent API: **PENDING**. No live OpenAI API calls were
  made in the delivery environment.

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
