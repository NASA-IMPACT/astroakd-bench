# AstroAKD-Bench

**Reproducible, MCP-native benchmarks for astronomical data-discovery agents.**

AstroAKD-Bench generates astronomy research questions, constructs candidate MCP
calls from a curated read-only set of Astroquery functions, executes those calls
against astronomical archives, and records auditable reference responses. It is
intended to evaluate agents such as **AstroAKD**, which use natural language to
find and interpret astronomical archive data.

The benchmark lives in the `benchmark/` directory of the
[NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp).
It is an **additive local client**: it communicates with the server over MCP HTTP
and does not modify `server.py`, `executor.py`, or Astroquery itself.

**Current version: 0.3.0 (`REFERENCE_VALIDATION`).** The local HTTP connection,
synthetic candidate generation, and reference-query execution are implemented.
Autonomous agent execution, scoring, and offline replay are **not implemented
yet** (planned for 0.4.0, 0.5.0, and 0.6.0, respectively).

See [CHANGELOG.md](CHANGELOG.md) for release history and the documentation
maintenance policy.

## What it does

| Version | Capability | Current status |
| --- | --- | --- |
| 0.1.0 | Connect to a local MCP server, discover tools/functions, check SIMBAD access | Accepted on laptop |
| 0.2.0 | Produce deterministic synthetic astronomy questions and candidate calls | Accepted on laptop |
| 0.3.0 | Execute candidate calls, validate response structure, journal results, and resume interrupted runs | Accepted on laptop |
| 0.4.0 (planned) | Submit questions to an AI agent and record independent MCP traces | Not implemented |
| 0.5.0 (planned) | Score tool selection, parameters, results, and task completion | Not implemented |
| 0.6.0 (planned) | Record/replay archive responses for reproducible offline evaluation | Not implemented |

The current workflow has **three distinct stages**:

```text
Astronomical seed objects + query templates
           |
           v
0.2.0 generate ---> candidate JSONL (unvalidated)
           |                         |
           |                         v
           |                 0.3.0 validate
           |                         |
           |                         v
           |                MCP server on laptop
           |                         |
           |                         v
           |                Real astronomy archives
           |                         |
           v                         v
   Generation report         Reference JSONL + validation report
                                   |
                                   v
                         Future: agent runs + scoring
```

**Terminology matters:** a *candidate* is a proposed task/call, not an answer;
`accepted_nonempty` and `accepted_empty` indicate structurally valid serialized
archive responses, not independently checked astrophysical ground truth.
Additional scientific review is needed before treating them as gold answers.

## Requirements and local setup

- A checkout of `astroquery-mcp` with the `benchmark/` package installed.
- The repository's Python and `uv` dependencies (including FastMCP).
- A locally running Astroquery MCP HTTP server at
  `http://127.0.0.1:8000/mcp` (or specify another URL).
- Internet access **for live archive queries**. Candidate generation performs
  MCP discovery only and does not execute archive searches.

From the **repository root**, start the server in one terminal:

```bash
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Run the commands below from the repository root in a **second terminal**.
The URL may be overridden with `--mcp-url` on an individual command or with
`ASTROAKD_MCP_URL` in the environment.

### 1. Check connectivity (0.1.0)

```bash
# MCP ping, tool catalog and module discovery
uv run python -m benchmark doctor --fast

# Full function discovery and signature introspection
uv run python -m benchmark doctor --timeout 180

# Optional end-to-end SIMBAD M31 query
uv run python -m benchmark doctor --smoke --timeout 180
```

Other discovery commands: `tools`, `modules`, `functions --module simbad`,
`info --module simbad --function query_object`, and `simbad --object M31`.
Use `uv run python -m benchmark --help` to see the installed CLI.

### 2. Generate reproducible candidates (0.2.0)

```bash
uv run python -m benchmark generate \
  --count 50 \
  --seed 42 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --timeout 180 \
  --output benchmark/datasets/generated/synthetic_queries.jsonl \
  --report benchmark/datasets/generated/generation_report.json
```

The accepted 50-task dataset contains 10 questions per module and **zero
archive executions**. Each task is marked `candidate_unvalidated`. Tasks use predefined templates, a curated object seed
pool, and discovered or explicitly documented query signatures. The generator
does **not** call an LLM or the OpenAI API. Generated files are not silently
overwritten; pass `--replace` only when intentionally regenerating them.

### 3. Validate candidates with live archives (0.3.0)

Run a five-task pilot:

```bash
uv run python -m benchmark validate \
  --input benchmark/datasets/generated/synthetic_queries.jsonl \
  --strict-accepted-020 \
  --limit 5 \
  --attempts 2 --delay 2 --timeout 180 \
  --output benchmark/datasets/validated/reference_answers.jsonl \
  --report benchmark/datasets/validated/validation_report.json
```

Resume the same run to process the remaining tasks:

```bash
uv run python -m benchmark validate \
  --input benchmark/datasets/generated/synthetic_queries.jsonl \
  --strict-accepted-020 --resume \
  --attempts 2 --delay 2 --timeout 180 \
  --output benchmark/datasets/validated/reference_answers.jsonl \
  --report benchmark/datasets/validated/validation_report.json
```

The first command reports `PARTIAL` and journals every attempted task. The
second resumes without rerunning completed IDs. On completion, the validator
publishes `reference_answers.jsonl` and reports `COMPLETE` with a `quality_gate`.
`COMPLETE` means all candidates received a disposition; `quality_gate=PASS`
means all dispositions were structurally accepted. Neither proves scientific
answer correctness.

**Important:** `--replace` discards the previous validation state; do **not**
use it for ordinary resumptions. The validator checks schema drift before
executing calls and refuses mismatched accepted datasets when
`--strict-accepted-020` is enabled.

## Generated files

```text
benchmark/
  README.md
  CHANGELOG.md
  datasets/
    generated/
      synthetic_queries.jsonl      # 0.2.0 candidate tasks
      generation_report.json       # seed, signatures, counts, SHA-256
    validated/
      reference_answers.jsonl      # all 0.3.0 dispositions and response evidence
      reference_answers.jsonl.progress.jsonl
      reference_answers.jsonl.manifest.json
      validation_report.json
```

The persistent progress journal and manifest support recovery from interrupted
validation. The response byte-size limit (default 8 MiB), delays, retries, and
timeouts protect local storage and reduce load on external services. Only the
MAST `query_region` server path currently honors `--max-rows`; other archives
can return larger tables.

### Supported reference query types (0.2.0 / 0.3.0)

| Archive | Read-only operation | Example use |
| --- | --- | --- |
| SIMBAD | `query_object` | Resolve a named object |
| MAST | `query_region` | Search observations near a sky position |
| HEASARC | `query_region` | Search high-energy catalog rows in a region |
| Gaia | `query_object` (async fallback if required) | Retrieve source data near an object |
| VizieR | `query_region` | Search catalog records near a sky position |

A strict method allowlist prevents arbitrary discovery results from becoming
benchmark execution calls. The HEASARC generic `**kwargs` signature is handled
as a variadic collector, not a required named argument. MAST and VizieR use
explicitly labeled documented wrapper adapters where introspection cannot
recover usable keyword signatures.

## Accepted laptop qualification (2026-10-13)

The local server was run at `http://127.0.0.1:8000/mcp`.

| Check | Observed result |
| --- | --- |
| 0.1.0 doctor + live M31 smoke | PASS: 7 tools, 16 modules, SIMBAD M31 returned 1 row |
| 0.2.0 synthetic generation | PASS: 50 distinct candidates, 10 per archive |
| 0.3.0 five-task pilot | `PARTIAL`: 5/5 `accepted_nonempty` |
| 0.3.0 completed validation | `COMPLETE`, `quality_gate=PASS`: 48 `accepted_nonempty`, 2 `accepted_empty` |
| SIMBAD, MAST, Gaia, VizieR | 10 nonempty results each |
| HEASARC | 8 nonempty, 2 valid empty results |

**Frozen accepted candidate dataset SHA-256:**
`e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`

**Observed reference dataset SHA-256:**
`1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`

These checksums were independently verified against the uploaded run artifacts.
The accepted archive responses are **structurally validated references**; the
next scientific-evaluation stage should independently review physical
coordinates, catalog identity, units, observation IDs and expected constraints
before assigning final answer-correctness labels.

## Testing

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

The 0.3.0 offline qualification recorded **60 passed and 1 skipped** (the
optional live HTTP test). A separate live integration test can be enabled
when the local server and SIMBAD are reachable:

```bash
ASTROAKD_TEST_LIVE=1 uv run python -m unittest benchmark.tests.test_live_connection -v
```

## Project boundaries and safety

- **No OpenAI API required in 0.1.0–0.3.0.** Questions are template-generated;
  no model is queried. Future agent benchmarking may optionally require an
  LLM provider, depending on the agent under test.
- **No agent scoring yet.** Do not interpret structural archive-response
  acceptance as evidence that AstroAKD has answered these tasks correctly.
- **Avoid public server exposure.** Bind FastMCP to `127.0.0.1` for laptop
  evaluation; the upstream MCP server exposes dynamic Astroquery operations
  and may access local authentication context.
- **Respect archive services.** The validator is sequential by default, with
  a 2-second query delay and bounded retries; external service availability
  and result contents can change between runs.
- **Treat traces as research artifacts.** Preserve versions, dataset hashes,
  validation dispositions, and execution provenance. Review responses before
  sharing if they may contain sensitive query details or credentials.

## Documentation and future releases

Details and qualification constraints are maintained in
[local MCP connection](../docs/benchmark/local_mcp_connection.md),
[synthetic query generation](../docs/benchmark/synthetic_query_generation.md), and
[reference validation](../docs/benchmark/reference_validation.md).

**For every new AstroAKD-Bench version**, update this README (current version,
features, commands, status and limitations) and add a corresponding entry at
the top of [CHANGELOG.md](CHANGELOG.md). Record separately whether offline
qualification and real-laptop qualification have passed; do not silently
promote a milestone based on mocked tests.
