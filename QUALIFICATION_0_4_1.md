# AstroAKD-Bench 0.4.1 — Qualification

**Milestone:** `0.4.1 — AGENT_TOOL_SELECTION_AND_RECOVERY_CLOSURE`

## Implementation qualification (delivery environment)

- **PASS:** `python -m unittest discover -s benchmark/tests -q`
  — 81 discovered tests, **80 passed**, **1 skipped** (optional live HTTP test).
- **PASS:** Python compilation and `python -m benchmark --version` -> `0.4.1`.
- **PASS:** Regression reproducing the actual 0.4.0 five-task pilot failure
  modes: HEASARC/Gaia incorrectly routed to VizieR and non-MAST `max_rows`.
- **PASS:** Explicit archive hint only from natural-language question, not
  from reference call or reference answer; no restriction for multi-archive
  questions.
- **PASS:** Wrong-module invocation rejected before network dispatch, with
  corrective guidance. OpenAI mocked sequence recovers after a rejected tool
  and a premature failed final answer.
- **PASS:** Query-evidence reporting is distinct from answer completion; a
  response without successful execute evidence cannot produce `quality_gate=PASS`.
- **PASS:** Prior 0.1.0–0.4.0 regression tests, with an intentional update of the
  former harness-only-success expectation (now REVIEW without query evidence).
- **PASS:** Accepted 0.2.0/0.3.0 user-supplied datasets were read without
  changes. SHA-256 candidate `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`;
  references `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`.
- **PASS:** Root `README.md` focuses on AstroAKD-Bench, is based on the user
  attached prior benchmark README, and does not include the upstream server's
  contributor attribution. Root `CHANGELOG.md` retains the cumulative history.

## Earlier live-host findings, not 0.4.1 validation

- 0.4.0 OpenAI pilot with `gpt-4.1-mini`: five recorded answers, eight attempted
  MCP calls, three successful archive executions, five rejected calls;
  misrouting observed for HEASARC and Gaia.

## Outstanding

- **PENDING:** Run the new 0.4.1 five-task `--agent openai` pilot against
  `http://127.0.0.1:8000/mcp` on the user laptop, then inspect trace and report.
- **PENDING:** Real-host regression across all 50 candidate questions.
- **NOT INCLUDED:** Scientific result/answer scoring (planned 0.5.0), offline
  record/replay (planned 0.6.0).

`status=COMPLETE` only means that every task has an execution record.
`query_evidence=observed` and `quality_gate=PASS` **do not establish**
scientific truth or agent answer correctness.
