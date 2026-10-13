# AstroAKD-Bench 0.3.0 — REFERENCE_VALIDATION qualification

**Implementation:** complete. **Offline qualification:** PASS. **Real laptop/live archive:** PENDING.

## Frozen input

Source: user's accepted 0.2.0 50-task JSONL dataset.

- SHA-256: `e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`
- 50 unique records: 10 each for SIMBAD, MAST, HEASARC, Gaia, VizieR.
- Candidate dataset not modified. A duplicate small fixture is included strictly for offline tests under `benchmark/tests/fixtures/`.

## Offline qualification results

Run: `python -m unittest discover -s benchmark/tests -v`

- **61 discovered tests, 60 passed, 1 skipped** (optional live HTTP integration test).
- 0.1.0 client/doctor regression tests PASS.
- 0.2.0 synthetic generation/HEASARC signature regression tests PASS.
- 0.3.0 tests verify JSONL input safety, accepted fixture hash, success/empty/error classifications,
  MAST truncation metadata, coordinate evidence, schema drift, retries, size cap, journal/resume,
  overwrite protections, CLI options, and an offline mock run of all 50 accepted cases.
- `python -m compileall -q benchmark` PASS.
- Git patch apply against accepted 0.2.0 + HEASARC fix: PASS (see packaging validation).

## Host acceptance

1. Run MCP server on `http://127.0.0.1:8000/mcp`.
2. Run a 5-task `validate --limit 5 --strict-accepted-020` pilot.
3. `validate --resume --strict-accepted-020` to finish 50 tasks.
4. Inspect `validation_report.json` and `reference_answers.jsonl` for all dispositions.
5. Investigate `rejected_*`, `transport_error`, `archive_error`, or `review_required` cases
   before promoting them to scientific gold answers.

This implementation **cannot** be marked real-host ACCEPT until live archive responses
have been observed. A complete run with failures is `COMPLETE` but gets
`quality_gate=REVIEW`; it is not misrepresented as all 50 gold answers validated.
