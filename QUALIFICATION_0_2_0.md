# Qualification — AstroAKD-Bench 0.2.0

- Upstream Astroquery MCP server source: **unchanged** (not included in overlay).
- Existing 0.1.0 `client.py`, `diagnostics.py`, `errors.py`, and regression tests: **byte-identical**.
- Offline test suite: **30 passed, 1 optional live integration test skipped**.
- Python syntax compilation and CLI `generate --help`: **PASS**.
- Live laptop generation of 50 candidates: **PENDING user host verification**.
- Archive execution and reference-answer validation: **not in scope** (0.3.0).
- Generation is discovery-only; the `reference_call` in every record is a proposal.

For acceptance run the commands in `INSTALL_ASTROAKD_BENCH_0_2_0.md`,
inspect `generation_report.json`, and repeat `generate` with `--replace` to
verify byte-identical dataset SHA-256 under unchanged signatures.
