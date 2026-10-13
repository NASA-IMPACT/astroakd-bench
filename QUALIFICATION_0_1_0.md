# AstroAKD-Bench 0.1.0 — qualification status

- Source basis: public NASA-IMPACT/astroquery-mcp main inspected 2026-10-13.
- Scope: additive `benchmark/` package and `docs/benchmark/` documentation only.
- Python checked locally: 3.13.5.
- Offline unit tests: **13 PASS, 1 SKIP** (opt-in real HTTP + SIMBAD test).
- Python syntax/compile check: **PASS**.
- CLI argument parsing/help smoke: **PASS**.
- Invalid MCP URL diagnostic: **PASS** (returns structured FAIL as intended).
- Live HTTP endpoint at 127.0.0.1:8000/mcp: **NOT EXECUTED** in this environment.
- Live SIMBAD lookup: **NOT EXECUTED** in this environment.
- Full milestone acceptance: **HOST-PENDING** until the laptop `doctor --smoke`
  check reports PASS and the real HTTP integration test succeeds.

Host commands:

```bash
uv run python -m benchmark doctor --smoke --timeout 180 \
  --output benchmark/local_mcp_qualification.json
ASTROAKD_TEST_LIVE=1 uv run python -m unittest \
  benchmark.tests.test_live_connection -v
```
