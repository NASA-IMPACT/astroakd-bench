# AstroAKD-Bench 0.1.0 — LOCAL_MCP_CONNECTION

**Scope:** Additive local FastMCP Streamable-HTTP client, tool/module/function discovery,
read-only SIMBAD smoke query, structured diagnostics, and offline unit tests. This
milestone does **not** yet implement synthetic-query generation, LLM evaluation,
benchmark scoring, or fixture replay.

## Installation

From the **astroquery-mcp repository root**, start the server in terminal A:

```bash
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

This exposes `http://127.0.0.1:8000/mcp`. Do not make this server publicly
accessible: it exposes a generic dynamic Astroquery executor and may use local
authentication credentials. All commands below are run from the repository root.

Copy the accompanying `benchmark/` directory into that root. No `server.py`,
`executor.py`, `pyproject.toml`, or `uv.lock` changes are necessary; the existing
`fastmcp>=2.14.2` project dependency is reused.

### Verify connectivity (terminal B)

```bash
# Fast connection/tool/module probe, no archive calls
uv run python -m benchmark doctor --fast

# Full introspection may take time on the first run (imports Astroquery modules)
uv run python -m benchmark doctor --timeout 180

# Full qualification including a live SIMBAD query
uv run python -m benchmark doctor --timeout 180 --smoke --object M31 \
  --output benchmark/local_mcp_qualification.json
```

Use these discovery commands to inspect the existing server independently:

```bash
uv run python -m benchmark tools
uv run python -m benchmark modules
uv run python -m benchmark functions --module simbad
uv run python -m benchmark info --module simbad --function query_object
uv run python -m benchmark simbad --object M31
```

The CLI also supports `--mcp-url http://127.0.0.1:8000/mcp` and the
`ASTROAKD_MCP_URL` environment variable; command-line values take precedence.
It prints machine-readable JSON. Exit status is `0` for PASS, `1` for FAIL,
`2` for report-output failure. The `--output` option saves exactly that JSON.

### Test the benchmark client without an archive or local server

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

The optional real integration test requires the server to be running and
SIMBAD to be reachable:

```bash
ASTROAKD_TEST_LIVE=1 uv run python -m unittest benchmark.tests.test_live_connection -v
```

## Acceptance gates

| Check | Gate |
| --- | --- |
| HTTP initialize + ping | PASS |
| `tools/list` includes four standard `astroquery_*` tools | PASS |
| `astroquery_list_modules` includes available `simbad` | PASS |
| `astroquery_list_functions('simbad')` includes `query_object` | PASS |
| `astroquery_get_function_info` includes `object_name` parameter | PASS |
| `astroquery_execute(simbad, query_object, M31)` | PASS, nonempty result |
| Disconnect / transport failure / MCP failure / app JSON error handling | Offline regression PASS |
| No edits to production server | Byte-identical original tree |

**Qualification status:** unit tests are run in the delivered package, but the
real local HTTP and SIMBAD host gates must be run on the user's laptop. If the
archive is unavailable, `doctor` without `--smoke` can still qualify the local
transport and introspection independently. `--fast` additionally avoids heavy
introspection.

## Error semantics

The server often returns errors as JSON with `error: true`, `success: false`,
or a string `error` field, rather than setting the MCP protocol `is_error` flag.
The client treats all of these as failures and preserves the error code and
message in exceptions and JSON reports. MCP protocol errors, transport errors,
and invalid/missing response fields are reported separately.

`doctor --smoke` deliberately avoids printing the entire SIMBAD table; it
stores row count/result type and object identifier for qualification. The
standalone `simbad` command prints the full response for inspection.

## Milestone boundaries

The `simbad` command is intentionally limited to the read-only `simbad.query_object`
operation. A later milestone should introduce an explicit per-method allowlist
before general tool execution is permitted. Capturing gold answers and scoring
agents belong to 0.2.0–0.5.0.
