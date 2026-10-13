# AstroAKD-Bench 0.5.0 offline qualification

**Milestone**: `0.5.0 — AUTOMATED_EVALUATION_AND_SCORING`

- Implementation and offline qualification: **PASS**.
- Host/laptop MCP and OpenAI qualification for the new release: **PENDING**.
- Full test suite: **95 tests, 94 passed, 1 optional live integration skipped**.
- Previous 0.1.0–0.4.1 regressions: PASS, including HEASARC variadic signature, archive routing/recovery, and reference isolation.
- New evaluator tests: PASS (selection errors, semantic coordinate parameters, genuine response fingerprints, reference consistency, Gaia truncation review, score publication, overwrite guards, historical pilot).
- Root datasets tests: PASS (preventing merges/overwrites, rejecting wrong accepted input hash, preserving unrelated files).
- CLI readable JSON test: PASS (`--json-format pretty`, bounded `inspect` output; JSONL stays compact).
- Compilation: PASS.
- Accepted candidate SHA256: `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`.
- Accepted reference SHA256: `1bfe4028f5533d3d7a1e5756bb26809e7e359f6a7640059ca07dcb295855da87`.
- **Real 0.4.1 pilot re-evaluation**: 5 recorded tasks; 94/100 mean technical evidence; 3 technical PASS, 2 REVIEW (including truncated Gaia), scientific accuracy independent review required.

**Crucial distinction:** An evidence score or structurally accepted MCP response does not prove the scientific correctness of all the model's claims. This release does not claim to run OpenAI or MCP live from the delivery environment. 0.6.0 offline record/replay remains planned.
