# AstroAKD-Bench 0.4.1 — Installation and Laptop Qualification

This **AstroAKD-Bench** release is an overlay for the existing
[NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp).
It does not change `server.py`, `executor.py`, or other MCP server code.

**Documentation ownership:** The root `README.md` documents **AstroAKD-Bench**
and names the MCP server only as a dependency. The root `CHANGELOG.md`
documents benchmark versions 0.1.0–0.4.1; neither document attributes
AstroAKD-Bench to the upstream MCP server contributor list.

## Option A: install the overlay archive (recommended for varied README baselines)

From the **repository root**, after downloading the ZIP to a known path:

```bash
mkdir -p /tmp/astroakd-bench-041
unzip -q /path/to/astroakd_bench_0_4_1_overlay.zip -d /tmp/astroakd-bench-041
cp -a /tmp/astroakd-bench-041/benchmark/. benchmark/
mkdir -p docs/benchmark
cp -a /tmp/astroakd-bench-041/docs/benchmark/. docs/benchmark/
cp /tmp/astroakd-bench-041/README.md ./README.md
cp /tmp/astroakd-bench-041/CHANGELOG.md ./CHANGELOG.md
uv run python -m benchmark --version
```

The `cp` operations add or update benchmark code/documentation but do **not**
remove `benchmark/datasets/` from the repository. The two root documentation
files are intentionally replaced with the complete AstroAKD-Bench versions.
Review/commit any local README edits before replacing them.

## Option B: Git patch

For a checkout matching the released 0.4.0 files and root docs:

```bash
git apply --check /path/to/astroakd_bench_0_4_0_to_0_4_1.patch
git apply /path/to/astroakd_bench_0_4_0_to_0_4_1.patch
```

If root `README.md` differs, use Option A. The optional
`astroakd_bench_0_4_0_to_0_4_1_code_only.patch` upgrades benchmark code and
benchmark-specific documentation **without touching root README/CHANGELOG**;
you must then copy those two files from the overlay ZIP.

## Start the local MCP server

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

## Run tests

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

Offline delivery result: **80 tests passed, 1 optional live-server test skipped**.
The live OpenAI API/astronomical archives were not called in the delivery
environment.

## First 0.4.1 real-agent five-task qualification

Use *new* paths for 0.4.1 artifacts; a 0.4.0 journal has a different routing
policy and must not be resumed with this release.

```bash
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --limit 5 \
  --max-turns 8 --max-calls 12 \
  --output benchmark/datasets/agent/openai_041_runs.jsonl \
  --report benchmark/datasets/agent/openai_041_report.json
```

This command requires `OPENAI_API_KEY` and may incur API usage charges.
Check the report's `query_evidence`, `successful_execute_calls`,
`rejected_mcp_calls`, and `quality_gate`, plus individual trace events. The
initial 0.4.0 five-task pilot had five final answers but only **three
successful executions**, with five rejected calls. The 0.4.1 pilot should
establish improvement; do not assume it from offline tests alone.

After a successful pilot, continue processing remaining tasks **without**
`--limit`, using `--resume` with all other settings unchanged. To intentionally
rerun from scratch, use `--replace` instead. The agent never receives the
reference answers. `query_evidence=observed` is transport/application evidence,
not independently verified astrophysical correctness.

See `docs/benchmark/agent_execution.md` for the external adapter contract.
