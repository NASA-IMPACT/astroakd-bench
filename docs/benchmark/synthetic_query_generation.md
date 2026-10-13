> **Version 0.6.3:** For the current diversity-safe workflow and answer-oriented task styles, see [query_diversity_0_6_3.md](query_diversity_0_6_3.md). Legacy seed=42 artifacts below are frozen and must not be regenerated over.

# AstroAKD-Bench 0.2.0 — SYNTHETIC_QUERY_GENERATION

## Scope and non-goals

**0.2.0 is a synthetic candidate generator, not an archive validation or agent
execution framework.** Its only server operations are discovery: `tools/list`,
`astroquery_list_modules`, `astroquery_list_functions`, and
`astroquery_get_function_info`. It does **not** execute `astroquery_execute`,
download files, authenticate to archives, or create reference answers.

All 0.1.0 `doctor`, `tools`, `modules`, `functions`, `info`, and `simbad`
commands remain present. The `doctor` command still describes milestone 0.1.0,
while `benchmark_version` will correctly report the installed 0.2.0 package.

## Usage on a laptop

Start the upstream server in Terminal A from the `astroquery-mcp` checkout:

```bash
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Then in Terminal B, from the separate AstroAKD-Bench checkout:

```bash
uv run python -m benchmark doctor --fast
uv run python -m benchmark generate \
  --backend template \
  --count 50 \
  --seed 42 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --timeout 180 \
  --output datasets/generated/synthetic_queries.jsonl \
  --report datasets/generated/generation_report.json
```

For a subsequent run targeting the same output, pass `--replace` explicitly.
The default endpoint is `http://127.0.0.1:8000/mcp`, or set
`ASTROAKD_MCP_URL`. No additional packages or CLI entrypoints are needed.
Discovery can be relatively slow since the server currently re-introspects
supported astroquery classes when requested.

To inspect generated output:

```bash
uv run python -m json.tool datasets/generated/generation_report.json
wc -l datasets/generated/synthetic_queries.jsonl
uv run python -m unittest discover -s benchmark/tests -v
```

Optionally perform the 0.1.0 live smoke after the generation qualification:

```bash
uv run python -m benchmark doctor --smoke
```

This tests the original server independently and must not be confused with
validating the 0.2.0 candidate dataset. Generation itself makes zero archive
queries.

## Dataset contract

Each canonical UTF-8 JSONL row contains:

- `id`, `benchmark_version`, `question`, `category`, `module`, `target`;
- `constraints`: object identifier or ICRS center plus explicitly unit-bearing
  angular radius and catalog where applicable;
- `reference_call`: the *proposed* `astroquery_execute` tool invocation with
  module, function, and params; **it has not been executed**;
- `validation_status`: always `candidate_unvalidated`;
- `provenance`: seeded generation index, seed catalog version, signature hash,
  and whether a documented wrapper adapter was needed.

The JSONL records have deterministic keys and order. For the same seed, module
set, program version, curated seed catalog and discovered signatures,
**bytes are identical**. `--output` is written atomically in the same folder
and cannot be replaced without `--replace`. The summary includes the exact
SHA-256 of output bytes and the schema fingerprint. No timestamps or host paths
are embedded in the candidate JSONL.

## Strict read-only allowlist

| Service | Permitted method(s) | Task |
|---|---|---|
| SIMBAD | `query_object` | Named-object lookup |
| MAST | `query_region` | Observation cone search |
| HEASARC | `query_region` | Catalog cone search |
| Gaia | `query_object`, `query_object_async` (fallback only) | Source cone search |
| VizieR | `query_region` | Catalog cone search |

All other dynamically advertised methods are excluded, including `delete_`,
`upload_`, `download_`, `launch_`, `save_`, `reset_`, and `clear_` methods.
Function and parameter names must be confirmed against server discovery.
Unrecognized required parameters abort generation rather than being guessed.

Some class/instance query wrappers expose only `*args/**kwargs`, which is not
sufficient to validate their keyword signatures. **Only** the documented
`mast.query_region` and `vizier.query_region` APIs have explicit conservative
keyword adapters (`coordinates`, `radius`, and `catalog` for VizieR).
This situation is marked `documented_mast_wrapper` or
`documented_vizier_wrapper` in the `signature_source` field and report. These
adapter-derived calls are **not claimed to be server-introspection-verified**;
they remain candidate calls until live execution validation in 0.3.0.

The coordinates are approximate seed centers used only for constructing
questions, and are not authoritative astrometric answers. The HEASARC and
VizieR catalog strings are curated options, not proof of successful archive
searches. A valid tool signature does not prove that the archive will return
records.

## Host qualification gates

1. Original 0.1.0 `doctor --fast` and `doctor --smoke` remain PASS.
2. `generate --count 50 --seed 42 ...` exits 0 and reports PASS.
3. Generated JSONL has exactly 50 rows and 50 unique task IDs/questions.
4. All five modules are represented by exactly ten candidates each.
5. Every proposed MCP function/argument tuple is on the explicit allowlist,
   with names backed by introspection or a labeled documented wrapper adapter.
6. `archive_queries_executed` equals 0 and every record is
   `candidate_unvalidated`.
7. Repeating the same command with `--replace` produces the same dataset
   SHA-256, provided the discovered method signatures have not changed.
8. Unsupported modules, missing functions, unknown required arguments, and
   accidental overwrite must produce nonzero exit codes.
9. Offline unittest suite passes (the optional live integration test is only
   enabled via `ASTROAKD_TEST_LIVE=1`).

**Host acceptance remains pending** until the user runs the generator against
their actual MCP endpoint and shares the resulting report. Actual archive
result validation remains milestone 0.3.0.


## 0.6.2: Human-readable CSV and pretty JSON exports

Canonical `.jsonl` stays **one compact JSON object per line**. Pass
`--csv-output PATH.csv` to create an inspection table and `--pretty-output
PATH.json` to save a complete indented JSON array. `--json-format pretty`
alone affects only terminal output and `.json` summary reports; it does **not**
change canonical JSONL encoding. Saved CSV/pretty views do not replace JSONL
in API calls, validation inputs or frozen-hash checks.

For generated queries:

```bash
uv run python -m benchmark generate \
  --backend template \
  --count 50 --seed 123 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --output datasets/generated/my_50_queries.jsonl \
  --csv-output datasets/generated/my_50_queries.csv \
  --pretty-output datasets/generated/my_50_queries_pretty.json \
  --report datasets/generated/my_50_report.json \
  --json-format pretty
```

For live validation of this **new seed=123 dataset**, start conservatively:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/my_50_queries.jsonl \
  --limit 1 --attempts 1 --timeout 30 --delay 0 \
  --output datasets/validated/my_50_references.jsonl \
  --csv-output datasets/validated/my_50_references.csv \
  --pretty-output datasets/validated/my_50_references_pretty.json \
  --report datasets/validated/my_50_validation_report.json \
  --json-format pretty
```

The validator reports progress on **stderr** at preflight, START, WAITING
(every 15 seconds), and DONE, so a slow remote archive cannot silently
appear idle. It saves completed-task results into an fsynced `.progress.jsonl`
journal. If interrupted, use `--resume` with the same input and output names,
and remove `--limit`. Do not use `--strict-accepted-020` for new seeds.
CSV and pretty JSON views are updated after each successful command invocation,
including pilot runs, and contain only processed records. The final canonical
reference `.jsonl` is published when all input tasks have dispositions.
