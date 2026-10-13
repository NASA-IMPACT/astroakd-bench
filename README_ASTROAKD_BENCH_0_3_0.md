# AstroAKD-Bench 0.3.0 — Reference validation

An additive benchmark package that validates the **unchanged, accepted 0.2.0
synthetic task set** against a local Astroquery FastMCP HTTP server. The benchmark
uses no OpenAI API and changes no production MCP server modules.

## New CLI

`uv run python -m benchmark validate` executes safe reference calls, verifies
response table shape and row-count consistency, and captures complete MCP query
payloads, responses, attempt histories, and an auditable disposition for every
candidate. One outstanding request at a time, retries for recoverable errors,
per-task durable progress and `--resume`, strict dataset hash option, and fail-closed
schema drift checks are included.

See `docs/benchmark/reference_validation.md` for pilot and full-run commands,
output schemas, `--resume` semantics, and scientific validation limits.

## Status

Offline unit qualification: 60 PASS + 1 optional live test SKIP.
Live HTTP qualification: not run from this development container; run on laptop.
