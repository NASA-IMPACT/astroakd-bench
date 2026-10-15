# 0.6.7.10 — Archive policy, consolidated evidence, and scientific review

This milestone builds on **0.6.7.9** without modifying the frozen 50-question
experiment, its scientific reference snapshot, agent instruction, or 150-run
journal. It does not automatically certify scientific truth.

## A. Archive-specific timeouts and retry attempts

The default global options are **unchanged** (`--timeout 180`, `--attempts 2`
for `validate`). Per-archive overrides are explicit and optional:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_100_with_refs.jsonl \
  --output datasets/validated/synthetic_100_with_refs_references.jsonl \
  --csv-output datasets/validated/synthetic_100_with_refs_references.csv \
  --report datasets/validated/synthetic_100_with_refs_references_report.json \
  --archive-timeouts mast=60,simbad=30,heasarc=60,gaia=60,vizier=45 \
  --archive-attempts mast=1,simbad=1,heasarc=1,gaia=1,vizier=1 \
  --reference-deadline 70 --delay 2 --json-format pretty
```

For *new* question generation, the same three overrides are supported with
`generate --with-reference-answers`, alongside `--reference-attempts` and
`--reference-delay`. The task deadline bounds the archive attempts and their
retry delays, not generator calls, signature preflight, or a pre-request
inter-task delay. Every journal record stores the effective settings and each
attempt's elapsed time, outcome, and error. A failure remains a recorded
failure; lower timeouts trade wait time for a higher timeout rate.

The overrides intentionally are not included in the resume manifest: a pilot
may be continued with different archive budgets without altering task, endpoint,
schema, max-row or response-size identity. `--resume` skips **all** journaled
tasks, including failures; it is not a selective retry facility. The
`--reference-deadline` setting is optional and is not a substitute for a
separate host-level HTTP/archive deadline if upstream cancellation is ignored.

## B. One-row-per-question consolidated reference CSV

Whenever `validate --csv-output .../references.csv` is given, a companion
`.../references_review.csv` is automatically written. Use
`--consolidated-csv PATH` to select another destination. When generating
references, `--reference-consolidated-csv PATH` overrides the default.
All output collision protections apply. The CSV contains the question, module,
target, requested fields, answer-shape classification, *observed* field values,
non-null/null counts, returned/reported row counts, truncation, review flags,
provenance hash, and `gold_status=pending`. `reference_answer_values_json`
retains table/row/field/value provenance and may be a capped preview: check
`observed_values_preview_capped_at_100`. No archive value is filled in by an LLM.

## C. Offline scientific review and independent gold finalization

Use the **original generated tasks and saved reference JSONL**. The review draft
runs completely offline and does not regenerate questions or query any archive:

```bash
uv run python -m benchmark reference-review-draft \
  --tasks datasets/generated/synthetic_100_with_refs.jsonl \
  --references datasets/validated/synthetic_100_with_refs_references.jsonl \
  --output datasets/gold/synthetic_100_review_draft.jsonl \
  --csv-output datasets/gold/synthetic_100_science_review.csv \
  --report datasets/gold/synthetic_100_review_report.json \
  --json-format pretty
```

Each JSONL review entry has a source dataset SHA-256, a reference source SHA-256,
question text, observed values and provenance, and the editable fields
`question_review`, `gold_status`, `gold`, `sources`, `reviewer`, `review_notes`.
Shape categories include: `single_value`, `coordinate_pair`, `record_list`,
`coordinate_pair_list`, `vector`, `vector_list`, and `no_answer`.

### Critical review rules

- **Never** change `input_dataset_sha256`, `task_id`, question, or task order.
- Check target association and units, and identify the scientifically intended
  row. A valid nonempty archive response is not a unique answer.
- For multi-row lists, ensure the requested scope is **complete**. `truncated`
  means only a subset was observed; a verified set requires explicit
  `complete_scope_review: true` and documented supporting evidence.
- A lone ICRS position may be verified with
  `gold={"kind":"coordinate_pair","values":[ra_deg,dec_deg],
  "frame":"icrs","unit":"deg","absolute_tolerance":...}`.
  The scorer checks RA/Dec **in that order** and wraps RA at 360°.
- Multi-row coordinate-pair lists and multi-field vectors are identified, but
  cannot be finalized/scored as sets of unordered scalar values in this
  milestone. Reformulate to an unambiguous task or implement structured-row
  scoring first.
- Approved gold requires human attribution and two independently reviewed
  HTTP(S) source records with **different hosts**, plus the existing gold
  validation checks. This procedural check alone does not prove science truth.
- Keep all unreviewed tasks pending or rejected. A partially reviewed dataset
  may be *frozen* with `--allow-partial`, but the unverified tasks remain
  `UNSCORABLE_NO_GOLD` in evaluation.

After **human editing** of a *copy* of the review JSONL, run:

```bash
uv run python -m benchmark gold-finalize \
  --tasks datasets/generated/synthetic_100_with_refs.jsonl \
  --reviewed datasets/gold/synthetic_100_reviewed.jsonl \
  --output datasets/gold/synthetic_100_scientific_gold.jsonl \
  --report datasets/gold/synthetic_100_scientific_gold_report.json \
  --allow-partial --json-format pretty
```

For the future 300-run A/B/C experiment, prefer an intentionally scorable,
scientifically reviewed task subset with its own fingerprint and documented
sampling design. Never feed gold answers or this worksheet to the agent.

### Offline review of the user's existing 100 records

The 2026-10-15 saved validation evidence yielded 97 observed-field records,
three empty HEASARC responses, **0 verified gold**. Shape classification:
16 single values; 7 single coordinate pairs; 58 multi-row single-field lists;
8 coordinate-pair lists; 8 multi-field vector lists; 3 missing. Twenty
records are truncated (all MAST); 74 return multiple matching rows. This
is **review triage**, not independent scientific validation.
