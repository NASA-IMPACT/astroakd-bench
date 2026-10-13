# AstroAKD-Bench reusable Python API (0.6.1)

AstroAKD-Bench is an **independent** synthetic astronomical query and
agent-evaluation project. It connects to the **separately operated** NASA IMPACT
Astroquery MCP server over `http://127.0.0.1:8000/mcp`, or uses stored MCP
fixtures when working offline. It does not contain or modify the server's
source code, and the server's contributors are not automatically benchmark
contributors.

## Install and import

Run in the AstroAKD-Bench checkout with Python 3.11+ and `uv sync`:

```python
from benchmark.api import AstroAKDBench, SkyTarget

bench = AstroAKDBench(root=".", mcp_url="http://127.0.0.1:8000/mcp", timeout=180)
print(bench.tasks_path)
print(bench.references_path)
```

`root` is the directory **containing** the root-level `datasets/` directory.
Use an independent root for each experiment, such as `root="experiments/test-A"`.
Output paths supplied to methods are relative to that root (absolute paths
are accepted). Existing files are never overwritten unless `replace=True`.

## 1. Make reproducible synthetic questions (no LLM)

Start the **external** MCP server in a separate checkout to make discovery
calls. This step does not execute data-archive queries.

```python
import asyncio
from benchmark.api import AstroAKDBench

async def main():
    bench = AstroAKDBench(root="experiments/pilot01")
    report = await bench.generate_queries(
        count=30, seed=123,
        modules=("simbad", "mast", "gaia"),
        report="datasets/generated/generation_report.json",
    )
    print(report["count"], report["dataset_sha256"])
    print(bench.load_records("datasets/generated/synthetic_queries.jsonl")[0]["question"])

asyncio.run(main())
```

`generate_queries` uses read-only tool discovery and the benchmark's
signature-aware, allowlisted templates. `seed` controls repeatability.
No OpenAI key is needed. The output JSONL uses one compact object per line.

### Use your own astronomical sources in a new experiment

```python
import asyncio
from benchmark.api import AstroAKDBench, SkyTarget

custom_objects = (
    SkyTarget("My target A", ra_deg=10.6847, dec_deg=41.2688),
    SkyTarget("My target B", ra_deg=182.6357, dec_deg=39.4057),
)

async def main():
    bench = AstroAKDBench(root="experiments/custom-objects")
    report = await bench.generate_queries(
        count=8, seed=2026, modules=("mast", "heasarc"),
        targets=custom_objects,
        output="datasets/generated/custom_tasks.jsonl",
        report="datasets/generated/custom_report.json",
    )
    print(report["dataset_sha256"])

asyncio.run(main())
```

Names and coordinate values are treated as **seeds**, not verified gold
answers. `SkyTarget` inputs must be unique, finite and valid ICRS degrees;
provenance contains a fingerprint of the custom seed catalog. Current templates
support SIMBAD, MAST, HEASARC, Gaia and VizieR only, with bounded radii and
allowlisted catalogs. This API does **not** generate arbitrary ADQL, execute
unapproved methods, or infer scientific truth.

**For new query types:** add/modify read-only function allowlists and semantic
parameter aliases in `benchmark/generator.py`, add templates in
`_description`/`_candidate`, extend the seed configuration in
`benchmark/seeds.py` and tests in `benchmark/tests/`. Do this in a **new
experiment/version** rather than editing the frozen `datasets/generated/`
accepted 50-task baseline.

## 2. Validate generated questions against archives

Validation requires the external MCP server and live archive connectivity.

```python
async def validate_my_queries():
    bench = AstroAKDBench(root="experiments/pilot01")
    result = await bench.validate_queries(
        input="datasets/generated/synthetic_queries.jsonl",
        output="datasets/validated/reference_answers.jsonl",
        report="datasets/validated/validation_report.json",
        attempts=2, delay=2.0, limit=5,
    )
    print(result["status"], result["dispositions"])

# asyncio.run(validate_my_queries())  # Only with server and archives running
```

Resume the same output by calling `validate_queries(..., resume=True)` with
identical input and validation parameters, omitting `limit` to complete the
remaining tasks. Never set `strict_accepted_020=True` for a **new**,
noncanonical seed dataset; that flag applies **only** to the frozen accepted
50-task data. A structurally valid reference response is not independently
verified astrophysical truth.

## 3. Build read-only replay fixtures (offline)

```python
from benchmark.api import AstroAKDBench
bench = AstroAKDBench()
report = bench.build_fixtures(
    strict_accepted_020=True,
    output="datasets/replay/new_reference_fixtures.json",
)
print(report["records"], report["fixture_fingerprint"])
```

This reads the existing reference JSONL without contacting MCP, archives or
an LLM. Save under a new filename to avoid overwriting the bundled fixture.

Use the same object directly in a notebook:

```python
store = bench.load_fixtures("datasets/replay/reference_fixtures.json")
result = store.lookup("astroquery_execute", {
    "module_name": "mast", "function_name": "query_region",
    "params": {
        "coordinates": {"ra": 214.498, "dec": 25.1369},
        "radius": {"value": 5, "unit": "arcmin"}
    }
})
print(result["success"])
```

**0.6.1 semantic replay:** exact call keys are checked first. Only the
approved ICRS-coordinate fields for MAST/HEASARC/Gaia/VizieR treat absent
`frame` and explicit `"frame":"icrs"` as the same lookup identity. No numeric
rounding, catalog aliasing, radius/unit conversion, function substitution or
network fallback is performed. Existing fixture files and their integrity
SHA-256 values are unchanged. Distinct recorded calls that would become
ambiguous under this rule are rejected.

## 4. Run an agent and preserve every MCP tool trace

The `run_agent` method supports `agent="openai"`, `agent="external"` and
`agent="echo"` (harness only). For an OpenAI agent, install its optional SDK,
set the API key in your environment and use new unique run output paths:

```python
async def run_pilot():
    bench = AstroAKDBench()
    result = await bench.run_agent(
        agent="openai", model="gpt-4.1-mini", mcp_mode="replay",
        fixtures="datasets/replay/reference_fixtures.json",
        strict_accepted_020=True, limit=5,
        output="datasets/agent/api_061_runs.jsonl",
        report="datasets/agent/api_061_report.json",
    )
    print(result["successful_execute_calls"], result["failed_mcp_calls"])

# asyncio.run(run_pilot())  # Calls OpenAI but not the MCP server
```

For a local custom AstroAKD agent, implement the async adapter interface
in [agent execution](agent_execution.md) and pass
`agent="external", adapter="your_module:run"`. Its tool calls must use
`gateway.call_tool` for recorded safety/trace provenance. The accepted
reference records are never passed to the agent. For test mocks, the API
also accepts `agent_factory` without importing external agents.

## 5. Score recorded agent traces offline

```python
from benchmark.api import AstroAKDBench
bench = AstroAKDBench()
result = bench.evaluate_agent(
    runs="datasets/agent/openai_041_runs.jsonl.progress.jsonl",
    strict_accepted_020=True,
    output="datasets/evaluation/api_061_scores.jsonl",
    report="datasets/evaluation/api_061_report.json",
    csv="datasets/evaluation/api_061_scores.csv",
    pretty_output="datasets/evaluation/api_061_scores_pretty.json",
    json_format="pretty",
)
print(result["status"])
```

Scoring uses saved agent traces and stored reference data; there are no live
MCP/archive/model calls. Technical scores and final-answer scientific accuracy
remain separate. Large/truncated tables and unsupported textual claims require
independent review, not invented correctness labels.

## 6. Standard CLI alternative

All API methods delegate to the same code paths used by the CLI. Example:

```bash
uv run python -m benchmark generate --count 20 --seed 123 \
  --modules simbad,mast --output datasets/generated/pilot.jsonl
uv run python -m benchmark build-fixtures --strict-accepted-020 \
  --output datasets/replay/local_061_fixtures.json
uv run python -m benchmark run --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --mcp-mode replay \
  --fixtures datasets/replay/reference_fixtures.json \
  --limit 5 --output datasets/agent/openai_061_runs.jsonl \
  --report datasets/agent/openai_061_report.json
```

Never execute evaluation against the `echo` harness as though it were a real
astronomical agent. `--json-format pretty` affects stdout and summary JSON;
`--pretty-output` saves an additional indented per-task score array. JSONL
stays compact. Always preserve provenance and SHA-256 for research reports.
