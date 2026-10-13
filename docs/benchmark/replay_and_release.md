# AstroAKD-Bench 0.6.0 — MCP record, replay and benchmark release

## Purpose

AstroAKD-Bench is an independent repository. It uses the external NASA IMPACT
Astroquery MCP server for archival queries, but offline replay can work without
an MCP server or public astronomy services. This makes trace regressions and
agent tool-selection tests repeatable on a laptop.

## Two fixture sources

1. `build-fixtures` imports responses already captured by 0.3.0 reference
   validation, verifies complete 0.2.0 candidate/reference coverage and frozen
   fingerprints, then stores the **exact reference-call arguments** and result
   objects. It generates a small, explicitly described safe bootstrap tool
   catalog. It neither executes remote queries nor exposes gold responses to
   the agent prior to a matching MCP call.
2. `run --mcp-mode record --fixtures datasets/replay/live_recording.json` sends
   each approved tool call to the live MCP server and records both the actual
   advertised tool catalog and each result. This is preferable when testing
   agents that discover functions dynamically or vary their tool arguments.

Both sources use a single JSON fixture with `format`, `catalog`, `entries`,
`source`, `dataset_sha256`, and `integrity_sha256`. Entries store tool name,
argument object, result or bounded failure, and SHA-256 digests of both the
normalized call key and returned payload. Corrupted entries or incompatible
fixtures fail before agent execution. Recording is atomic after every MCP call
and supports interrupted-run resume when the fixture and run manifest agree.

## CLI commands

```bash
# Offline seed: 50 validated MCP calls, no server required
uv run python -m benchmark build-fixtures --strict-accepted-020 \
  --output datasets/replay/reference_fixtures.json

# Offline archive replay; OpenAI itself still needs the network
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini --limit 5 \
  --strict-accepted-020 --mcp-mode replay \
  --fixtures datasets/replay/reference_fixtures.json \
  --output datasets/agent/openai_060_replay_runs.jsonl \
  --report datasets/agent/openai_060_replay_report.json

# Recording mode: requires live MCP HTTP endpoint
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini --limit 5 \
  --strict-accepted-020 --mcp-mode record \
  --fixtures datasets/replay/live_recording.json \
  --output datasets/agent/openai_060_record_runs.jsonl \
  --report datasets/agent/openai_060_record_report.json
```

For a fully no-network experiment, supply a locally running agent via
`--agent external --adapter package.module:run`, and select `--mcp-mode replay`.
`--agent echo` verifies only the harness and never performs archive queries.

## Invariants and interpretation

- No HTTP/DNS fallback from `ReplayClient`: a missing exact tool/arguments
  pair produces `OFFLINE_REPLAY_MISS` and a failed trace event.
- The existing `TracedMCPGateway` validates each operation with the
  read-only allowlist before the fixture lookup, just like live execution.
- The agent never receives expected task calls or reference records directly;
  it sees only tool schemas and responses to requested, allowlisted calls.
- `run` manifests include mode, absolute fixture location and replay fixture
  fingerprint. `--resume` rejects changed identity, schema, dataset or mode.
- 0.6.0 does **not** claim deterministic LLM reasoning. It freezes the archive
  response layer; hosted LLMs may still change their decisions or wording.
- The original candidate/reference SHA-256 values remain unchanged. Offline
  fixtures record structurally accepted archive outputs, not fully verified
  astrophysical ground truth. `evaluate` scores technical evidence, not general
  scientific truth.

## Qualification

Run `uv run python -m unittest discover -s benchmark/tests -v` and inspect the
included `QUALIFICATION_0_6_0.md`. The real-server integration test remains
opt-in; offline tests must run with the MCP server completely stopped.
