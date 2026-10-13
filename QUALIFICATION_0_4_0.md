# AstroAKD-Bench 0.4.0 — AGENT_EXECUTION_AND_TRACING

## Disposition

**Implementation: COMPLETE. Offline qualification: PASS. Laptop qualification: PENDING.**

This is not a claim that a deployed AstroAKD agent or an OpenAI-backed model
has been executed against the user's local MCP server. Such live qualification
requires the user's localhost server and (if selected) provider credentials.

## Source changes

- Add `benchmark/agent_runner.py`: reference-isolated independent agent runner,
  optional OpenAI tool-calling adapter, external AstroAKD adapter interface,
  no-LLM echo harness, bounded traced MCP gateway, input validation, durable
  journal and completion report.
- Extend CLI with `python -m benchmark run` flags for agent selection, budgets,
  input paths, pilot runs, resume and overwrite control.
- Bump `benchmark.__version__` to 0.4.0.
- Add `benchmark/tests/test_agent_execution.py`, documenting model/mock and
  trace constraints. Preserve all earlier regression tests.
- Add `docs/benchmark/agent_execution.md`. Move detailed benchmark README to
  `docs/benchmark/astroakd_bench.md`. Migrate benchmark changelog to root
  `CHANGELOG.md`, preserving 0.1.0–0.3.0 history.
- Add a small non-destructive AstroAKD-Bench section to the existing top-level
  server `README.md`. Retain the pre-existing server README content.

Production MCP server modules `server.py` and `executor.py`, `pyproject.toml`,
`uv.lock`, accepted generated dataset, and accepted reference dataset are unchanged.

## Offline checks (2026-10-13)

| Check | Result |
| --- | --- |
| Full unittest discovery | **75 PASS, 1 SKIP**, 76 total |
| Original 0.1.0–0.3.0 regressions | PASS |
| MCP tool allowlist, unsafe actions and bounded params | PASS |
| Independent agent reference isolation | PASS |
| Optional OpenAI agent's mocked function-call workflow | PASS |
| Pilot, durable journal, resume, full 50-task mock run | PASS |
| Input/reference dataset consistency and hash enforcement | PASS |
| Patch `git apply --check`, actual patch application | PASS |
| Tests rerun after applying the patch | PASS |
| Root README original server content retained | PASS |
| Root changelog and benchmark docs path migration | PASS |

Real archived input qualification used the actual uploaded files from the
accepted laptop runs:

- Candidate SHA-256:
  `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`
- Reference SHA-256:
  `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`
- An **offline mock agent** processed 50/50 accepted tasks and generated 50
  auditable mock MCP calls. It does not establish real archive or model success.

The optional test `benchmark.tests.test_live_connection` remains SKIPPED unless
explicitly enabled with `ASTROAKD_TEST_LIVE=1` against the user's running MCP
server. No actual LLM/provider network calls were executed in this environment.

## Laptop acceptance gates

1. Start the local MCP HTTP server at `http://127.0.0.1:8000/mcp`.
2. Execute a five-task `run --agent echo --limit 5` harness smoke (gate:
   `status=PARTIAL`, `quality_gate=HARNESS_ONLY`, `processed=5`).
3. Execute a five-task run with either the optional `openai` adapter or a
   real AstroAKD async external adapter. Inspect at least one `astroquery_execute`
   event and the question-independent MCP trace. The agent should not receive
   `reference_call` / `reference_answers` fields.
4. Resume the same agent configuration through all 50 tasks, and check all
   dispositions and SHA-256. `quality_gate=PASS` means all answers were
   recorded, not scientifically accurate.
5. Confirm 0.1.0–0.3.0 user datasets remain unchanged.

## Planned next milestones

- 0.5.0: Independent answer/scientific-result scoring, tool selection metrics,
  failed-result handling and evaluation reports.
- 0.6.0: Offline record/replay of MCP archive responses and replay qualification.
