## Unreleased — Published example dataset and documentation figures (2026-10-28; version unchanged)

- Add a curated `examples/astroakd_100_v2/` study with 100 generated questions, a joined question/reference CSV (92 complete reference sets; 8 excluded literature cases), original reference CSVs, representative agent answers, published scoring summaries, plots, and checksums.
- Add `examples/README.md` and embed selected original figures in the examples and root README; provide an illustrated `docs/benchmark/example_results.md` in the current Sphinx site.
- Extend the GitHub Pages documentation trigger to `examples/**` and include a Wiki example-results page with image paths rewritten to public repository links.
- Preserve the frozen scientific data and scoring results; this is documentation/example packaging only, with no benchmark behavior, version, or science change.

## 0.6.7.11.13 — GH_PAGES_AND_WIKI_DOCUMENTATION_PUBLISHING

- Add `.github/workflows/publish-docs.yml` on `main` to build warning-clean Sphinx HTML on documentation/source changes and manual dispatch, mirror the built site (with root `index.html` and `.nojekyll`) to `gh-pages`, and deploy that same artifact with GitHub Pages Actions. A `GITHUB_TOKEN` push to `gh-pages` alone does not trigger the live Pages build.
- Export current Markdown guides, the README and CHANGELOG to GitHub-wiki-compatible pages with rewritten internal links, preserving the source in `main`; update only managed wiki pages and retain unrelated human-maintained pages.
- Use least-privilege repository token permissions and an optional scoped `WIKI_TOKEN` secret if the wiki does not accept the built-in token. GitHub Pages and wiki setup are documented, including the required initial wiki page.
- Add offline validation and tests for documentation export, managed-page synchronization, GitHub Actions configuration, shell syntax, and Sphinx entrypoint. No benchmark generation, MCP tool calls, frozen data, scoring, prompts, or A/B/C behavior changed.

## 0.6.7.11.12 — Documentation follow-up (2026-10-19; version unchanged)

- Document successful live recovery of all six VizieR-containing multi-archive steps: 12/12 multi-archive references complete, 92/100 questions evaluable; all eight literature questions remain excluded.
- Explain `draft-literature-plans` live-output terminology: `DRAFT_ONLY_NOT_REFERENCE` with six `DRAFT_UNVERIFIED` candidate templates and two unresolved target/route cases; drafts are not executable `--literature-plans` inputs or paper-linked observation references.
- Update README and current Sphinx guides only. No generator, reference collector, scoring, prompts, CLI, frozen data, or agent behavior changed.

## 0.6.7.11.12 — MULTISTEP_REFERENCE_AND_SCORING_CLOSURE

- Fix strict scoring false negatives from archive-labelled observation IDs, comma-separated ObsID lists, and mixed-field measurement unit metadata. Multi-archive comparison now preserves explicit archive/field provenance and duplicate multiplicity; ambiguous unlabeled values are not promoted to correct answers.
- Accept both single-table MCP results and VizieR-style lists of structured tables, preserving table indices and completeness checks. Record bounded response shape diagnostics and hashes on failed steps, not full raw payloads.
- Add `collect-multistep-references --resume --retry-incomplete [--dry-run]` with optional `--retry-task-ids`. Completed archive steps are reused; one immutable pre-retry evidence journal is created, and retry history is retained.
- Add offline `draft-literature-plans` to produce bounded, source-independent SIMBAD target-resolution calls and dependent archive-query templates for resolvable literature targets. These are explicitly **unverified drafts**: candidate ADS bibcodes alone cannot establish paper--observation associations, so literature records remain unscorable until complete independently supported evidence exists.
- Verified offline against the frozen 100-question and original 300-run `astroakd_100_v2` evidence: 86 evaluable references before any new live retry, A and B 85/86 (98.84%) strict archive-reference agreement, C 13/86 (15.12%). This is not independently adjudicated scientific accuracy. Live MCP VizieR retry and literary association collection remain host pending.
- Preserve source-level question-generation instructions, original question files, 80 single-call references, and agent run journals. Update CLI, README, Sphinx documentation, and tests.

## 0.6.7.11.11 — AUTOMATED_REFERENCE_ANSWER_SCORING

- Adds `score-reference-answers`, an **offline** comparison of saved A/B/C agent answers with independently collected Astroquery MCP reference observations. No regenerated questions, replayed agent calls, or manually authored gold answers are required.
- Supports scalar fields, multiplicity-preserving lists, normalized numeric measurements, coordinates, vector fields (such as J/H/K magnitudes and pmra/pmdec), and row-associated multi-field records. The scoring policy distinguishes `correct`, `partially_correct`, `incorrect`, `abstained`, and `failed` while reporting exact evaluable denominators and exclusions.
- Generates `match_rate.png`, `accuracy_by_archive.png`, and `accuracy_by_question_type.png`, with SVG equivalents plus per-question CSV, breakdown CSV and JSON summary. The existing `agent-report` also includes the new scoring result while retaining operational measurements and a separate strict-snapshot summary.
- Adds resumable `collect-multistep-references` for independently specified read-only archive calls. The mixed two-archive tasks have machine-readable query plans. Literature candidates without independently specified observation calls, or without paper-to-observation association evidence, remain **unscorable**, never silently promoted to verified reference answers. Existing 80 single-call references are not queried again.
- Tested against the frozen `astroakd_100_v2` 100-question dataset and original 300 runs: 80/100 automatically evaluable single-call tasks; A and B each 79 strictly matching, one partial; C 13 matching. These are **archive-reference answer agreement rates**, not separately adjudicated scientific accuracy. Multi-step live collection remains host-pending.

## 0.6.7.11.10 — documentation follow-up (no version or science change)

- Document the full `collect-references` archive-timeout/retry/deadline command
  for recovery of saved `astroakd_100_v2` questions, plus offline
  `reference-report` in the README and current Sphinx guides.
- Clarify first collection versus `--resume`, preservation of paid question
  generation, and why 80/80 accepted reference responses can coexist with
  `status: REVIEW` and 20 pending multi-step references.
- No changes to the generator, reference validator (including the previously
  applied recovery patch), MCP calls, agent scoring, or frozen scientific data.

## 0.6.7.11.10 — DURABLE_REFERENCE_AWARE_SELECTION

- Atomically checkpoint each live reference-feasibility probe and accepted slot
  with SHA-256 integrity, preserving all work on interruption or budget failure.
- Add `create-queries --resume` for incomplete reference-aware probe selection;
  allow increasing only the maximum number of probes without invalidating prior decisions.
- Avoid repeated oversized MAST cones by searching smallest radii first and
  stopping enlargement after truncation, then fall back to other supported
  archive modules while reporting the actual mix. No relaxed science acceptance.
- Fix version-specific README guidance, Sphinx docs and generator instructions.
- Preserve original 0.6.7.11.9 data and scoring behavior; no revised scoring.

## 0.6.7.11.9 — REFERENCE_AWARE_SYNTHETIC_QUERY_GENERATION (candidate)

- Added live, agent-independent read-only feasibility checks for named mixed-dataset candidate slots *before* GPT authoring when `--with-reference-answers` is enabled.
- Candidate gating rejects empty, truncated, oversized, too-many-row, missing-answer-field and null-answer-field archive responses. Narrowing bounded Gaia/MAST/HEASARC/VizieR radii and alternative curated targets are supported without inventing reference values.
- Added `--reference-aware`/`--no-reference-aware`, `--max-reference-rows`, `--max-reference-bytes`, and `--max-feasibility-probes` to the simplified CLI and Python facade.
- Added checksum-protected saved candidate plans for `--resume`; revised the generation instruction policy for answer feasibility and ambiguity.
- Current README and Sphinx guides now recommend a new `astroakd_100_v2` study while preserving previous frozen 100-question and 300-agent-run artifacts. The 20 multi-step questions still require separate reference evidence; no scoring algorithm was modified.
- Offline regression qualification is recorded separately. Live feasibility with the user's independent MCP server is pending.

## 0.6.7.11.8 — SELECTIVE_MCP_RETRY_AND_REFERENCE_SNAPSHOT_AGREEMENT

- Add `run-benchmark --retry-errors` with `--dry-run`, automatic failed MCP-only selection, changed-budget metadata, and immutable original run preservation. Store only retries and a separately labeled derived A/B/C diagnostic journal; do not rerun successful arms.
- Add native `agent-report --runs` for diagnostic reports separate from baseline figures.
- Create `match_rate.png` / `.svg` only from available comparable unreviewed reference snapshots, with an explicit UNREVIEWED label, transparent restricted paired denominators, strict matching and exclusions in reference-agreement CSV/JSON. Never present provisional agreement as reviewed scientific gold.
- Update current-only README and Sphinx workflow guides with both commands, output directories, provenance rules, and scientific limitations. Frozen experimental datasets and scientific code are unchanged.

## 0.6.7.11.7 — EXTERNAL_MCP_SETUP_DOCUMENTATION_RESTORE

- **Applied source hotfix to the attached 0.6.7.11.7 distribution:** exclude archives with no timing observations from median response-time plots, avoiding `StatisticsError: no median for empty data` when mixed tasks remain uncollected. Questions and missing-evidence counts remain present in reference reports.
- Expand the current README and Sphinx workflow guides with the exact `reference-report` and `agent-report` plot commands, output paths, figure names, `--replace` usage, and the distinction between operational plots and historically scored `match_rate.png`.

- Restore the complete external MCP installation workflow (`git clone`, `cd`, `uv sync`, and `uv run fastmcp run`) prominently in README, INSTALL and the current Sphinx getting-started and ADS pages.
- Clarify the two terminal/process environments, the local MCP endpoint, server-side ADS tokens versus the benchmark `OPENAI_API_KEY`, and read-only ADS verification.
- Documentation-only behavior change: question generation, archive reference collection, science data, agent evaluation and all frozen inputs are unchanged.

## 0.6.7.11.6 — ADS_EXACT_QUERY_DIAGNOSTICS_AND_README_CLOSURE

- Added `literature-auth --probe --query "PG 1211+143"` to test the actual failing query.
- Classify upstream MCP/ADS errors into a strictly bounded vocabulary of HTTP/auth/rate-limit/timeout/network categories; never print opaque server exception bodies or token-bearing diagnostics.
- Reduce ADS retry traffic: request each unique search formulation only once with the compact `minimal` preset, since MCP presets filter the same upstream ADS.query_simple call.
- Add a symbol-normalized query alternative for plus-sign source identifiers without fabricating paper references. Pass the curated literature plan's target name explicitly into ADS search, correcting the earlier PG 1211+143 plan whose long search text omitted that target entirely.
- Revise README, INSTALL and current Sphinx guidance to distinguish passing authentication probes from failing literature searches and to explain strict ADS versus labeled web fallback.
- Scientific datasets, frozen fixtures and agent scoring remain unchanged. No live ADS recovery claimed until tested on the user's server.

## 0.6.7.11.5 — ADS_RESEARCH_AND_DURABLE_GENERATION_CLOSURE

- Fix the mismatch between generic ADS authentication preflight and actual literature research: inspect all planned research queries **before** paid GPT batches and reuse the resulting ADS evidence.
- Try conservative, grounded target-query forms and `minimal` ADS fields when the `standard` request fails; do not invent papers or silently allow OpenAI web research with `--require-ads`.
- Support `--archive-timeouts`, `--archive-attempts`, and `--reference-deadline` directly in the short `create-queries --with-reference-answers` command and Python API.
- Save each validated GPT question batch in an fsynced, checksummed progress journal and a separately labeled non-gold partial JSONL. Persist completed literature questions as well.
- Add `create-queries --resume` to reuse successful GPT batches and literature questions after failures, checking inputs and immutable scientific task bindings before reuse. Remove partial files after successful final publication.
- Update current-only README, installation guide and Sphinx workflow documentation. Earlier failed v0.6.7.11.4 runs without a progress journal cannot be recovered from the console log.
- Offline host qualification does not establish live ADS connectivity; verify with the external MCP server before using real data.

# Changelog

## 0.6.7.11.4 — CURRENT_DOCUMENTATION_AND_ADS_PREFLIGHT_CLOSURE

- Current-only Sphinx guide and navigation; release read from `pyproject.toml`.
- Moved 77 old root installation, qualification and handoff files and 28 old documentation pages into a separate checksum-indexed historical Markdown archive; no science fixture changes.
- Updated `datasets/README.md` to describe a clean working directory without implying archived files are installed.
- `create-queries --require-ads` now probes authenticated `ads_query_compact` **before any GPT question generation**. Failed authentication, unavailable tool, empty known-paper probe and ADS request failures report safe reasons without credential values.
- `literature-auth --probe` enables explicit live ADS route diagnostics. The preflight does not supply scientific gold answers.
- Kept the CLI/Python API and five named directory-creating workflows; updated tests and docs to current version.

# AstroAKD-Bench Changelog

All significant changes to the **independent AstroAKD-Bench project** are documented
here. This history is separate from the external `astroquery-mcp` project's
releases: AstroAKD-Bench versions track benchmark capabilities, not versions
of Astroquery or the MCP server.

The current implemented benchmark version is **0.6.7.11.2**.
Dates are in UTC. Release statuses distinguish **offline implementation
qualification** from **real laptop / live-service qualification**.

## 0.6.7.11.3 — DATASET_LAYOUT_AND_HISTORICAL_ARTIFACT_CLEANUP (offline qualification pending)

- Moved the complete 118-file historical dataset snapshot to independent, versioned TAR.GZ archives; verified every archived byte with a per-file SHA-256 manifest.
- Preserved frozen 50-question candidate and oracle SHA-256 values without editing them; copied nine required regression inputs byte-for-byte to `benchmark/tests/fixtures/legacy/` and updated those tests to use the new paths.
- Retained `datasets/` as the clean user workspace; generated files are excluded from Git and all five easy commands create their own output directories as needed.
- README and Sphinx quick-start now lead with the requested `astroakd_100 --count 100 --output-dir datasets --require-ads --with-reference-answers` example, omitting optional `--seed` (default `20261018`).
- Science constraints unchanged: only 80 single-call questions are eligible for automatic reference collection; 20 literature/multi-archive questions require multi-step evidence, and none are automatically verified gold.


## [0.6.7.11.2] — NAMED_MIXED_GENERATION_WITH_SINGLE_CALL_REFERENCES (offline qualified; 2026-10-15)

- Expose `create-queries --with-reference-answers` and `--reference-limit N` with the named dataset, count, output directory and ADS options. It creates the question files first and then invokes the existing bounded, resumable validator on the eligible archive/coordinate single-call subset; interrupted collection resumes with `collect-references --resume` without repeated OpenAI generation.
- The default 100-task mix has 80 single-call and 20 ADS-literature/multi-archive multi-step tasks. The latter retain an explicit pending state and are **not** assigned fabricated or incomplete reference answers. All observed archive values remain scientifically unreviewed; zero automatic gold promotions.
- Mirror the new options in `AstroAKDBench.create_synthetic_queries`. Document exact working command, pilot/resume workflow, output paths and scientific limitations in README and Sphinx guides. Tests use mocked archive collection; live server, ADS, and OpenAI qualifications remain host-pending.

## [0.6.7.11.1] — CONFIGURABLE_SYNTHETIC_COUNT_AND_OUTPUT_ROOT (offline qualification; 2026-10-15)

- `create-queries --count N` now works with the default scaled `balanced100` mix for N=1..100, without manually spelling quotas; N=100 retains the same 60/20/8/12 design. Counts above the curated seed capacity are rejected early and are not silently padded with duplicate targets.
- `create-queries --output-dir PATH` saves generated questions and sidecars to `PATH/generated/`; the four downstream short commands accept the same `--output-dir` and place references, agent journals and reports under `PATH/validated/`, `PATH/agent/`, and `PATH/reports/`.
- Default dataset name is `synthetic_N` when `--name` is omitted (still `synthetic_100` with default count). Python convenience APIs mirror count/path selection. Existing default `datasets/` paths and all frozen experiment data remain untouched.
- Qualification: offline tests and archive checks recorded in `QUALIFICATION_0_6_7_11_1.md`. Live OpenAI, MCP and ADS generation remain host-pending.

## [0.6.7.11] — MIXED_100_SIMPLE_WORKFLOWS_AND_NATIVE_REFERENCE_REPORT (2026-10-15)

- New short, first-class named commands: `create-queries`, `collect-references`, `reference-report`, `run-benchmark`, and `agent-report`. The default name is **`synthetic_100`**, not `synthetic_100_new_with_refs`.
- Mixed 100-question generation includes 60 archive, 20 coordinate, 8 ADS/literature, and 12 genuine two-archive questions. Cross-archive queries combine pre-bound same-target calls and do not forge a gold answer or pretend to be a single-call validator input. Multi-step questions retain their distinct evidence contract.
- Strict optional `--require-ads` refuses OpenAI-web fallback when authenticated MCP ADS research is requested. Standard mode records ADS versus web provenance and remains explicit when ADS is unavailable.
- `collect-references` validates only the 80 single-call subset with per-module timeouts; multi-step tasks remain pending separate evidence. Resume is safeguarded by existing dataset/schema/endpoint manifests.
- Native offline `reference-report`: per-task/per-archive CSV and JSON, with PNG/SVG archive distributions, answer shapes, completeness/review flags, truncated/null counts and response-time distributions. Dataset hashes and individual call contracts are verified.
- Native offline `agent-report`: CSV with full retained A/B/C answers, operational metrics and PNG/SVG plots. No correctness/accuracy claim without human-verified gold.
- Python `AstroAKDBench` convenience methods match the CLI. Current README and Sphinx/MyST guide are simplified; the frozen 50/150 GPT-5.2 experiment, accepted oracles, datasets and instruction hashes are unchanged.
- Offline suite: see `QUALIFICATION_0_6_7_11.md`. Live MCP, authenticated ADS, OpenAI generation and 300-arm scientific evaluation remain **host-pending**; no new live dataset or verified science answer is claimed in the release.

## [0.6.7.10] — ARCHIVE_REFERENCE_POLICY_AND_SCIENTIFIC_REVIEW (offline qualified; live host pending; 2026-10-15)

- Optional `--archive-timeouts` and `--archive-attempts` route per-task archive budgets without changing legacy global defaults; `--reference-deadline` bounds combined task attempts and backoff. Store effective policy and attempt events in the reference journal, support policy adjustment on resume while continuing to protect dataset/endpoint/schema identity. No selective requery of journaled failures is claimed.
- Produce an automatic one-row-per-question consolidated review CSV when a reference CSV is requested. The original generated-candidate CSV remains unchanged. Maintain task, field, row and provenance evidence; all observed answers are **unreviewed**.
- Add network-free `reference-review-draft`: produce an editable, `gold-finalize`-compatible JSONL and consolidated CSV, with cardinality/shape and truncation, null, multi-row and preview-cap flags. Never promote observations to gold automatically.
- Extend human gold finalization and offline scoring for explicitly reviewed single ICRS RA/Dec pairs in degrees, retaining two independently cited source hosts and reviewer attribution. Ambiguous multi-row coordinate/vector results remain unscorable until task redesign or structured-row scoring. Existing gold semantics remain intact.
- Apply changes to CLI, documentation and offline tests; preserved baseline instructions, frozen 50-task oracle and prior 150-run journal are not modified. Live per-archive qualification remains pending.
- Final release qualification: 252 tests passed, 1 optional live test skipped, 41 subtests passed. Fixed an end-to-end CLI output-routing bug before release: `reference-review-draft` now preserves its editable JSONL rather than overwriting it with summary JSON. See `QUALIFICATION_0_6_7_10.md`.

## [0.6.7.9] — INTEGRATED_LIVE_REFERENCE_ANSWER_COLLECTION (offline-qualified; 2026-10-15)

- Add explicit `generate --with-reference-answers` to perform live Astroquery MCP reference validation after candidate generation, saving full response evidence, fsynced progress journal, reference summary and CSV. Bounded retry/pilot/resume remain delegated to the existing validator. No LLM-written gold answers.
- Add observed matching field values and per-task reference-answer review status to existing validation CSV exports. Missing/empty responses are never silently assigned values.
- Preserve existing generation-only behavior without the flag, separate new outputs from the frozen 50-task/150-run experiment, update Python API/README/100-query Sphinx guide, add offline integration tests.

## [0.6.7.8] — PAIRED_THREE_ARM_ERROR_AND_EFFICIENCY_ANALYSIS (offline-qualified; 2026-10-15)

- Documentation-only follow-up (same software version): add first-time local NASA IMPACT `astroquery-mcp` clone and FastMCP HTTP launch instructions, then a new 100-query candidate generation / resumable validation / conditional scorable oracle / 300-arm-run / offline-score walkthrough. The strict all-`accepted_nonempty` reference gate, frozen-data preservation and no-live-100-run qualification are explicit. README, current quick-start and Sphinx navigation updated; no runtime, oracle or experiment data changes.

- Add optional five CSV reports to `score-scorable`: overall A/B/C results including MCP and web statistics; MCP A/B summary; per-question A/B/C paired answers and runtime/token/tool deltas; pairwise match contingency and efficiency summary; and observable-category mismatch audit requiring independent science review. Existing reports remain compatible.
- Calculate exact two-sided McNemar discordance p-values, paired means and medians, quartiles, and deterministic 2000-resample percentile bootstrap intervals on paired **mean differences**. Missing arm runs remain unavailable rather than being coerced to zero or an incorrect answer.
- Add four paired PNG/SVG figures, separate from the five original figures. Preserve recorded model responses, source-derived oracle, instruction contents and input hashes.
- Real 150-record GPT-5.2 journal (SHA-256 `58824a2b71e7063b550c3fa16592f70307f11f6ace7293bf7fe81a47c334daaf`) scored offline: A 48, B 49 and C 12 reference matches; 41 arm-level mismatches requiring review. The A/B correctness table is 48 both match / 0 A-only / 1 B-only / 1 neither, exact McNemar p = 1.0. Mean B-minus-A runtime ~ -6.48 s, median ~ -0.24 s; do not interpret the difference as typical speedup on every question.
- Refresh CLI, Python API, README, Sphinx navigation, quick-start, tests and conversation handoff. The 50-task archive-focused snapshot is not independent gold or a general astronomy-discovery benchmark. Sphinx host rendering remains a separate qualification.

## [0.6.7.7] — MCP_TOOL_CALL_REPORTING_AND_AB_PLOTS (offline-qualified; 2026-10-14)

- Expose every recorded MCP gateway call from existing GPT-5.2 A/B run traces in a new `--mcp-calls-csv` (question, arm, call index, tool/function, status, outcome, duration and bounded already-redacted parameters). Preserve the original run journal as the authoritative full tool trace. No new calls or changes to agent behavior.
- Add `--mcp-tool-frequency-csv`: per-tool and per-archive-function A/B totals, including attempts, successes, rejected calls, errors and number of questions using the function. Extend existing detailed answer, per-task performance and per-arm CSVs with MCP call sequences, totals and attempted-query averages. Web-only C remains excluded from MCP-specific denominators.
- Add two new PNG/SVG barplots to the existing three: `mean_mcp_tool_calls` (attempted/successful A vs B) and `mcp_tool_calls_by_name` (A/B tool-function frequency), with pilot denominators and N/A when no arm executions exist. The other three A/B/C plots remain intact.
- Qualify the offline scorer on the retained five-query GPT-5.2 pilot: A/B each have 6 attempts, 5 successful and 1 rejected, for 1.20 mean attempted calls per query; source hashes, original instruction contents, model and completed runs unchanged.
- Update CLI, Python API, Sphinx docs, README and regression coverage. Live 50-query MCP tool summaries must be regenerated on the host from its completed JSONL run journal.

## [0.6.7.6] — SPHINX_RTD_THEME_AND_MAKEFILE_LAYOUT (offline qualified; host RTD build pending) — 2026-10-14

- Inspected the user-provided 0.6.7.5 `html.tar.gz`: 22 documentation pages, plus search and index, successfully generated with Sphinx 9.1.0/MyST 5.1.0 using the **Alabaster** theme. Three historic Markdown links rendered as dangling fragment anchors; no current guide page was missing. Host Make clock-skew warning concerned future timestamps, not the Sphinx build.
- Match the XSTAR-Tools documentation design using the official `sphinx_rtd_theme` 3.1+ (`docs/conf.py`, optional `docs` dependencies); enable responsive left navigation, built-in search, and a stable sidebar. The new-theme HTML render requires a host Sphinx install and is tracked separately from the user-proven original Alabaster build.
- Move the documentation-only root `Makefile` to `docs/sphinx/Makefile`. Canonical build is `make -C docs/sphinx html` (or `cd docs/sphinx && make html`); output remains `docs/_build/html/index.html`. `clean` and `linkcheck` remain. Use rooted paths so `make -f docs/sphinx/Makefile html` is also valid.
- Update current README, quick-start, documentation-build guide, docs index, installation, and source-level regression expectations; adjust three obsolete archive-only links and remove misleading external-to-source Sphinx links. Preserve the agent and benchmark instruction file contents, frozen datasets, answer oracle, live GPT-5.2 journal, and resume context.
- Add a 0.6.7.6 standalone handoff and checks for Makefile relocation, theme configuration, documentation paths, instruction hashes, and command dry-runs. No new model execution or MCP archive calls.

## [0.6.7.5] — SPHINX_HTML_AND_INSTRUCTION_NAMING (offline qualified; HTML host build pending) — 2026-10-14

- Rename the **AstroAKD-Bench synthetic generation instruction** from
  `instructions/astroakd_bench/llm_generation_instructions_v1.md` to
  `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` without changing
  content (SHA-256 `d430cf4d2508f124abee4deb23da44b3aca1618707f6c052fea8ee9deda47acf`). Update the default generation loader, tests and active instructions/documentation links. The separate AstroAKD instruction for arm B remains byte-identical.
- Add a native **Sphinx + MyST** HTML documentation configuration in `docs/conf.py`,
  a repository-root `Makefile` with `make html` / `make clean` / `make linkcheck`,
  `pyproject.toml` optional `docs` dependencies and `.gitignore` for generated
  `_build` outputs. Add navigation trees covering current guides and historical
  references, plus a dedicated documentation-build guide.
- Refresh README and quick-start to demonstrate **fresh full run without `--resume`**,
  **five-question pilot with `--limit 5`**, **continuation via `--resume`**, and
  **first-time scoring without `--replace`**. Rename the scoring section to
  *Score and generate CSV reports / plots*.
- Preserve frozen science and reference datasets, all model settings, experiment
  journal contents and manifest semantics. No new GPT-5.2 or MCP evaluation was
  performed. Run offline regression and static Sphinx configuration/navigation
  checks; actual HTML render remains **host pending** because Sphinx/MyST could
  not be installed from the container's disabled package network.

## [0.6.7.4] — DOCUMENTATION_AND_INSTRUCTION_SEPARATION (offline qualified; 2026-10-14)

- Relocate the **AstroAKD agent instruction** unchanged to `instructions/astroakd/AstroAKD_Instruction.md` and the independent **AstroAKD-Bench synthetic-question-authoring instruction** unchanged to `instructions/astroakd_bench/llm_generation_instructions_v1.md`. Both files retain their original SHA-256 hashes. Neither specialized instruction is stored inside `docs/` anymore.
- Update `benchmark.llm_generation.INSTRUCTIONS_PATH` to the relocated default question-generation instruction; `generate --instructions-file` continues to allow a custom prompt. Change current `run-three-arm` examples to the new agent instruction path. Runtime A/B/C model/tool policy is unchanged; the resume manifest records instruction **content hash**, not location.
- Add `instructions/README.md` to explain the project boundary, and add `docs/index.md`, `docs/benchmark/quickstart.md`, and `docs/benchmark/experimental_methods.md` to make current usage and interpretation discoverable. Update active versioned guides to use the new paths; historical handoffs and prior release entries remain historical evidence.
- Rewrite the overly long root README as a current-version project entry point covering setup, namespaced endpoint/token variables, current GPT-5.2 experiment, 50-question reference-snapshot evaluation, offline scoring/CSV/barplots, and scientific limitations. Preserve its 0.6.7.3 predecessor at `docs/history/README_0_6_7_3.md`.
- Add `INSTALL_ASTROAKD_BENCH_0_6_7_4.md`, source-hash/layout regression checks, and documentation-link QA. No science or benchmark datasets, agent prompts, MCP transport policy, scoring logic, or existing journals are changed. An existing running 150-run experiment should finish before replacing source files; the moved prompt has the same hash for subsequent resumed runs.

## [0.6.7.3] — CONFIGURABLE_MCP_ENDPOINT_AND_BEARER_AUTH (offline qualified; remote host pending) — 2026-10-14

- Standardize on **`ASTROAKD_MCP_URL`** and **`ASTROAKD_MCP_TOKEN`** only; deliberately ignore the generic `MCP_URL`/`MCP_TOKEN` variables. Endpoint order: explicit `--mcp-url`/`--mcp-server` > `ASTROAKD_MCP_URL` > `http://127.0.0.1:8000/mcp`. Empty environment values are treated as unset. Validate HTTP(S) URLs and reject URL-embedded credentials.
- Provide `--mcp-token` / `--mcp-server-token` overrides, with `ASTROAKD_MCP_TOKEN` as default. Empty or unset tokens use unauthenticated MCP; tokens are sent as bearer authentication through FastMCP `BearerAuth` and are not placed into question data, reports, trace journals, or resume manifests.
- All native MCP workflows use the shared transport, including discovery, generation, validation, legacy agent tracing, literature tools, and both MCP evaluation arms. Endpoint failures explicitly say **`Cannot connect to MCP server at <selected-address>`**; authentication errors are surfaced without revealing secrets.
- Three-arm runner now tests the actual MCP connection **before recording new runs** (only for a real client, not injected offline test doubles), preventing unreachable endpoints from filling the evaluation journal with misleading errors. No web-only tool access or scientific scoring policy changed.
- An existing in-progress experiment should continue without changing its address or other manifest-bound settings. Changing endpoints mid-experiment is intentionally blocked by the resume guard. The bearer token can rotate without being persisted in the manifest.
- Offline tests exercise precedence, ignored legacy names, unauthenticated and bearer clients, redaction, diagnostic error address, and fail-fast three-arm offline behavior. Real deployment and authentication remain host-qualified only when user runs `doctor` against a connected service.

## [0.6.7.2] — THREE_ARM_RESUME_MANIFEST_JSON_CLOSURE (offline-qualified; real host resume pending) — 2026-10-14

- Fix a persisted-manifest type mismatch in `run-three-arm --resume`: Python tuple `ARMS` serialized to a JSON array (list), causing an unequal comparison despite identical settings and rejecting every valid resume with `Resume context differs; refuse data mixing`. New contexts use `list(ARMS)`, preserving the same serialized JSON bytes and all existing pilot manifests.
- Retain the existing dataset hash, instruction hash, GPT-5.2 model, MCP endpoint and resource-budget checks. Genuine mismatches must still reject. No changes to agent scientific behavior, tools, prompts, frozen reference keys, scoring algorithms, saved journals, or completed GPT-5.2 runs.
- Add an offline regression exercising two-task/three-arm partial execution, an intentionally invalid changed-model resume, and successful continuation to six unique arm records without re-running the first three. Real user 45-task continuation remains **PENDING**.

## [0.6.7.1] — THREE_ARM_DETAILED_ANSWER_PERFORMANCE_PLOTS (offline-qualified; live pilot files analyzed) — 2026-10-14

- Extend native `score-scorable` with `--detailed-csv`, `--performance-csv`, `--task-performance-csv`, and `--plots-dir` options, preserving the old two CSV/report outputs and the unchanged `gpt-5.2` agent runner.
- Detailed 150-row (50 tasks × 3 arms) CSV includes each full question, frozen reference, actual answer text and array, structured/unstructured status, source identifiers, abstention flag, match result, compact tool-event summary (complete raw trace remains in the saved JSONL journal), run errors, duration and token counts. Mark a response with both `abstained=true` and nonempty answer values explicitly as `ABSTAIN_WITH_VALUES` instead of disguising it as an ordinary abstention; **do not change the existing reference-match scorer**.
- New three-arm `performance_observations.csv` separately records snapshot-match percentage, attempted/completed coverage, mean and summed wall time, prompt/completion/total tokens, per-query token mean, web searches, successful/rejected MCP calls, and errors. A companion per-task resource CSV keeps all 150 rows, including `not_run`.
- Three barplots saved to PNG and SVG: **reference-snapshot match rate (% of attempted), mean runtime per attempted question (seconds), total recorded tokens**. Annotate actual attempted counts; output displays N/A when an arm has no attempts. Optional dependency `matplotlib` is required only when plots are requested, via `uv run --with matplotlib` or `.[plots]`.
- Export remains offline and gold-blind (agents are never rerun). All new destination paths are preflight-checked for overwrite and collision; source data and frozen scientific reference hashes remain unchanged. Existing CSV reports are backward compatible.
- Real GPT-5.2 5-question pilot reprocessed: **A 5/5 (100%), B 5/5 (100%), C 1/5 (20%)** snapshot matches; mean times **21.4642 / 7.5763 / 16.9497 s**; totals **276739 / 308724 / 101552 tokens**. These are **not independently verified scientific truth**, and 45 questions remain unrun.
- Added installation, docs, tests and conversation handoff. Full offline suite qualification results in `QUALIFICATION_0_6_7_1.md`. Native live 150-run follow-up pending.

## [0.6.7] — REFERENCE_ANCHORED_SCORABLE_QUERIES (offline-qualified; GPT-5.2 live pending) — 2026-10-14

- Default agent, literature and synthetic-question model advanced from `gpt-4.1-mini` to **`gpt-5.2`** (the OpenAI API model ID, not deprecated `gpt-5.2-chat-latest`). The three-arm pilot and future full run MUST use the same `--model gpt-5.2`; earlier GPT-4.1-mini pilot results are retained separately and cannot be combined with GPT-5.2 rates.
- Added native `build-scorable` to convert the accepted **42/42 real MCP reference responses** into **50 distinct one-field questions with explicit answer keys**, source task IDs, row/field indexes, field units and numeric tolerances. Output includes 50-row question/answer CSV, new candidate JSONL, separate reference snapshot oracle JSONL and audit report. No new archive calls or LLM-generated answers are needed to construct this key.
- Added native `score-scorable` to compare 3-arm agent replies against those frozen snapshot values; saves a **50-row CSV containing each question, expected reference answer, and *all* A/B/C responses (correct or incorrect)**, plus per-arm percentages of exact reference matches over attempted questions and all 50. Model mismatch, run/candidate hash mismatch, and tool-arm violations fail closed. A pilot does not masquerade as complete coverage.
- The snapshot oracle is explicitly `reference_anchored_unreviewed` rather than `verified` scientific gold. Published percentages are **archive-snapshot reference match rates**, not externally verified scientific accuracy; literature-driven multistep answers still need independent ADS/archival validation and are not manufactured.
- Added GPT-5.2 structured JSON-answer schemas for MCP Chat Completions and web-only Responses; the actual answer value remains hidden from all three arms. Higher completion token budget for GPT-5.x; preserve wrong/unstructured/abstained replies for manual review.
- Extended read-only agent path allows SIMBAD name resolution as an intermediate when another archive is requested, removing the pilot's false tool-guard rejection without permitting unrequested final-archive substitution.
- Original source hashes retained: `gold_mixed_065.jsonl` = `139e895c63a0c0834f282fe4bf0622470f3a5ff7760343384f690ae567ded9eb`; accepted 42 references = `fd359a148c3b9137e09cb07cdb100b2b6f1266ce76290cf2c33a2f5f64c2aa5`.
- Added new 0.6.7 install, guide, tests, qualification and conversation handoff. No real GPT-5.2 A/B/C execution or independently verified science score claimed.
- Offline qualification: **197 passed, 1 optional live test skipped, 26 subtests passed**; 50 source-keyed task/answer rows across 18 requested fields successfully generated from 42 immutable reference responses. Numerically equivalent unit spellings (such as degree/deg and second/s) are normalized without unit conversion.

## [Unreleased]

- Planned after 0.6.1: broader scientific claim verification, multi-archive workflows and frozen evaluation suites.

## [0.6.6.1] — ANSWER_INSPECTION_AND_SUCCESS_RATE_CSV (offline qualified; real data imported) — 2026-10-14

- Added `export-answer-csv` CLI and `AstroAKDBench.export_answer_csv()` Python API. The benchmark exports a 50-question CSV with returned reference values and A/B/C agent answers, a 150-row long-form arm comparison, an independent A/B/C percentage summary, a full source-value CSV, and optional separate A, B and C CSVs.
- Ingested the user's **complete 42/42 real-host reference results** (SHA-256 `fd359a148c3b9137e09cb07c0db100b2b6f1266ce76290cf2c33a2f5f64c2aa5`) and the real five-task/15-run three-arm pilot journal. Initial extraction produced 1,709 individual source table-field observations. All historical candidate files are unchanged.
- Distinguished **operational completion rate** (completed / attempted) from **whole-dataset coverage** (completed / 50) and **scientific success** (correct / scientifically graded). The pilot shows 5/5 completed for each arm (100% operational completion, 10% of the 50-task experiment per arm); scientific success remains unavailable because zero independently approved gold answers exist.
- Recorded structured-answer compliance (1/5 for A, 0/5 for B and C), full free-text replies, source citations, run errors, trace counts, timing, token usage and missing/unrun status. A completed reply, even if nonempty, is **not** automatically counted as scientifically correct.
- Archived each requested field value with source table and row index; explicitly flag truncation, unverified reference values and absent gold. MAST returned subsets and other large catalogs are not silently promoted to complete gold answers.
- Guarded dataset SHA-256 bindings, duplicate run IDs, web/MCP tool isolation, verified gold provenance, output collision checks, atomic formula-safe CSV publication. Added focused tests, release instructions, and a continuation handoff.
- Offline qualification: **190 passed, 1 optional live test skipped, 26 subtests passed** (including 4 new targeted CSV tests). No new live OpenAI, ADS, or archive requests are claimed.

## 0.6.6 — GOLD_REFERENCE_AND_THREE_ARM_EVALUATION (offline qualification)

- Added `gold-draft` to safely import completed, partial MCP validation journals with dataset SHA checks and generate an unapproved scientific answer review worksheet covering all 50 mixed tasks. **No automatic answer promotion**.
- Added `gold-finalize` to freeze human-reviewed, provenance-linked set/text/numeric answers, with strict unit/tolerance checks, reviewer and independent source-host gates, truncated table review, and partial-gold support explicitly marked unscorable.
- Added `run-three-arm` for clean AstroAKD comparisons (A: MCP without domain instruction, B: MCP with the complete user-provided **AstroAKD agent instruction**, C: web search without MCP), matched question set/model/tool budgets, auditable per-arm traces and interruption-safe journaling/resume. No gold/reference data are accepted as inputs to this runner.
- Added a guarded read-only ADS literature tool policy for evaluated MCP agents (only when advertised by Astroquery MCP), with independent web-search tool isolation for arm C.
- Added `score-three-arm`: strictly structured scientific gold answer matching for sets (F1), scalar numbers (specified units/tolerance), and text (normalized exact match), with REVIEW for unstructured answers, UNSCORABLE for pending gold, and paired-task coverage metrics.
- Preserved the real five-task (of 42) structural validation journal and manifest; original Gold mixed, single-call and literature candidate hashes unchanged. Added new 0.6.6 guide, installation, qualification and conversation handoff.
- Offline full suite: 186 passed, one optional live test skipped. **Live gold-answer approval and full AstroAKD three-arm science evaluation pending.**

## [0.6.5] — NATIVE_GOLD_MIXED_QUERY_GENERATION (offline PASS; live PENDING)

- Integrate native Gold-inspired generation with `generate --task-mix gold50` (32 archive, 10 coordinate, 8 literature) or custom family quotas. Previously shared Gold50 file was made by a separate offline builder, **not** AstroAKD-Bench live OpenAI generation.
- Execute OpenAI/MCP-bound archive generation inside AstroAKD-Bench; add grounded ICRS coordinate questions and eight research-based, multistep literature questions. Research uses **MCP ADS first** and falls back to OpenAI `web_search` when ADS fails or the key is missing.
- Preserve immutable reference calls, prompt/source provenance, no invented expected answers, uniqueness audit and split outputs to keep literature tasks out of the one-call validator.
- Add Python API mixed generation, mock/offline tests, usage guide, installation/qualification and conversation handoff. All-suite offline result 177 passed, 1 optional live skipped; no new live OpenAI/ADS run claimed.

## [0.6.4.4] - 2026-10-14

### Fixed — LITERATURE_SEARCH_FALLBACK_OUTPUT_CLOSURE

- User's real-host `literature-search` in 0.6.4.3 reached the OpenAI web-search fallback, but the fallback reused the strict LLM synthetic-question JSON parser. Ordinary search prose (with source citations) raised `GenerationError: OpenAI output is not valid JSON`. The saved FAIL report did not include the raw provider response, so the reason ADS was bypassed is unknown.
- OpenAI web-search evidence now accepts either the historical JSON question form or ordinary citation-bearing research text, without treating either as independently verified astronomical truth. Preserve optional source URLs from both search actions and Responses message citation annotations. Missing citations become `source_review_required=true`, not invented citations.
- Added the `literature-auth` read-only CLI to query the external MCP server's `astroquery_check_auth` and tool catalog; reports ADS booleans only and never token values or token length. Emit sanitized fallback reasons on stderr and in successful web-search evidence reports. Preserve ADS-through-MCP first choice; no direct ADS client/API.
- Added eight mock regressions covering prose, JSON compatibility, fallback routing, annotations, no-citation review, incomplete output and safe authentication probe. Original candidate/reference/fixture artifacts remain unchanged.

### Qualification

- Source tree: **173 tests run, 172 passed, one optional live MCP test skipped**. Real ADS authentication and OpenAI web-search requalification **PENDING**.

## [0.6.4.3] — GOLD_BENCHMARK_MCP_ADS_LITERATURE_FALLBACK

- Analyzed the separate Gold Benchmark Dataset (31 numbered queries: 20 archive-driven, 7 coordinate-driven, 4 literature-driven). Expanded the default LLM instructions to cover scientific question structure, units, and literature-to-archive evidence chains.
- Added `literature-search` CLI and `AstroAKDBench.research_literature()` reusable API. All ADS research is routed **through the external Astroquery MCP server** using `astroquery_check_auth` and `ads_query_compact`. No direct Astroquery or ADS HTTP calls.
- Automatically fallback to OpenAI Responses `web_search` if ADS is not configured/usable; missing `API_DEV_KEY` alone is not fatal. Token values are never saved or logged by AstroAKD-Bench.
- Preserve strict distinction between literature discovery and independently verified archive observations / scientific answers. Existing frozen datasets and single-archive generator behavior unchanged.
- Added mocked ADS-auth, fallback, API and token-redaction tests; live service/API qualification pending.

## [0.6.4.2] - 2026-10-14

### Fixed — OPENAI_TASK_ID_RECONCILIATION

- Real laptop OpenAI+instructions+MCP generation 0.6.4.1 completed five batches but failed after batch 6/10: `GenerationError: OpenAI changed or omitted task IDs`. User-provided FAIL report contains no raw model response, so the exact changed IDs are unknown.
- Treat model-returned task IDs as advisory only. Reassociate a question with its immutable prebound task ID when strict astronomical target/archive/field guards admit **exactly one complete assignment**. Reordered rows and omitted/rewritten/duplicated ID labels are supported if scientifically unambiguous; never alter MCP reference calls or constraints. A complete target-name boundary check prevents substring collisions.
- If mapping is ambiguous, request one corrected batch; then reject safely. Original ID and repair flag are retained in per-record provenance, and summary reports show `task_id_repairs` and `openai_batch_retries`. Each retry is an additional OpenAI request. Existing 0.6.4.1 archive-name normalization is preserved.
- Added batch-6 regression tests with missing, rewritten and reordered IDs (including no-MCP web mode), retry, unsafe-response rejection, target-boundary checks and exact MCP-call parity.

### Qualification

- Complete offline suite: **158 tests run, 157 passed, 1 optional live MCP test skipped**. Frozen historical candidate/reference datasets and reference fixture preserved. Live 50-question OpenAI rerun is still **PENDING**.

## [0.6.4.1] - 2026-10-14

### Fixed — OPENAI_ARCHIVE_NAME_NORMALIZATION

- First real OpenAI+instructions+MCP generation pilot failed after batch 1/10: task `ASTROAKD-020-00005` omitted the explicit name `VizieR`. Version 0.6.4 rejected the entire batch even when the question otherwise matched the already-bound target/intent.
- When a *valid question* mentions its target but no known astronomical archive, insert the prebound archive name as a neutral question prefix. Do not modify tool name, parameters, target, scientific constraints, answer spec, reference response, or validation outcome.
- Reject conflicting archive names; retain existing restrictions on malformed questions, invented date/year constraints, and fields not supported by MCP reference calls. Record each wording correction in question `provenance` (`archive_name_repaired`, `original_llm_question`) and `archive_name_repairs` in the run summary.
- Added mock regression replicating missing VizieR in the first 5-task OpenAI batch of a 50-task generation. The 50 frozen MCP calls remained byte-equivalent under the same seed/discovery fixture. Documentation explains retry destinations and live qualification status.

### Qualification

- Focused LLM tests and affected generation, diversity, exports, evaluator, validator and replay subgroups PASS offline. Some legacy integration-like modules stalled in this environment; full standalone suite not claimed. **Real laptop 0.6.4.1 OpenAI retry: PENDING.**
- Historical accepted candidate, reference dataset and replay fixture preserved.

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

