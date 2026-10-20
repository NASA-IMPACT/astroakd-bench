# Reference collection and scientific review

`create-queries --with-reference-answers` collects *reference observations*,
not independently verified gold answers. If question generation succeeded but
reference collection did not finish (or you intentionally generated only
questions), reuse the saved question files. Do **not** rerun OpenAI generation:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100_v2 \
  --output-dir datasets \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

This command is available natively in 0.6.7.11.10; `--timeout` applies to
MCP operations, while `--archive-timeouts`, `--archive-attempts`, and
`--reference-deadline` provide the specific collection policy. For an
interrupted collection append `--resume`; omit `--resume` on a first attempt.
For a pilot you can use `--limit 5` and subsequently resume. The reference
journal and output are under `datasets/validated/`. When all 80/80 references
have already been collected, do not call the collector again.

## Completeness reports and plots

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 \
  --output-dir datasets
```

Outputs appear in `datasets/reports/astroakd_100_v2/references/`. This is **reference evidence reporting**, not an agent A/B/C comparison. Run the command **after** `create-queries --with-reference-answers` or `collect-references`; it never runs GPT or makes MCP calls. It can also report on incomplete evidence, with pending multi-step tasks clearly labeled.

| File | Contents |
| --- | --- |
| `reference_summary.json`, `reference_questions.csv`, `reference_archives.csv` | Task and archive summaries, including pending/unreviewed status |
| `questions_by_archive.png`, `answer_shapes.png`, `reference_dispositions.png` | Distribution of questions, answer shapes and collection status |
| `review_flags.png`, `truncation_null_by_archive.png` | Scientific review, truncation and null-measurement flags |
| `response_times.png`, `response_time_distribution.png` | Median per-archive runtime and observed runtime distribution |

All plots also have SVG versions. **Archives with no recorded response times are omitted only from the median-runtime plot**, not from the question counts or pending status. This avoids calculating a median from empty data when multi-step reference collection is outstanding.

If a prior attempt produced only some report files, rerun with `--replace` (reports/plots only; **not** the original questions/references):

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 --output-dir datasets --replace
```

For CSV/JSON summaries without figures or matplotlib, run `uv run python -m benchmark reference-report --name astroakd_100_v2 --output-dir datasets --no-plots --replace`. For A/B/C runtime and token comparisons see [A/B/C evaluation and plots](evaluation_and_plots.md).

## Review before scoring

Archive observations are **unreviewed evidence**. Multiple matching rows, truncation, units, coordinates and ambiguous cross-identifications need scientific review. Literature and multi-archive tasks in a mixed set require separate multi-step evidence collection and cannot be considered complete gold through the single-call collector. A `status: REVIEW` report does not mean the
80 single-call references failed: 80 nonempty records may be collected while
20 literature/multi-archive questions still require separate multi-step
evidence and the references remain unreviewed.

The detailed commands `reference-review-draft` and `gold-finalize` remain available for explicitly reviewed single-call datasets. Do not promote generated questions or raw archive values to scientifically verified gold automatically.

## Feasibility gate versus collected references

`create-queries --with-reference-answers` in 0.6.7.11.10 first checks that each *proposed core query* returns bounded, nonempty, untruncated MCP evidence, including required answer columns and no null values. The precheck's source-response SHA-256 is retained in the question provenance and the selected plan is saved. The independent `collect-references` step later reexecutes those exact frozen calls; archives can change between calls, so precheck acceptance does **not** guarantee subsequent collection succeeds. All final reference dispositions and coverage/exclusion reasons must be reported. Literature/ADS and multi-archive tasks still need separate multi-step evidence. See [Creating questions](create_queries.md).

## Independent multi-step evidence (0.6.7.11.11)

`collect-multistep-references` executes only new saved read-only multi-archive steps; it does not repeat the 80 single-call references. Use `--limit 5` for a pilot, then `--resume`. Its per-task JSONL journal preserves evidence hashes, completed steps, exclusions and missing literature plans. Literature citations collected during synthetic question generation are not automatically a verified paper-to-observation reference answer. Run `score-reference-answers` separately after complete references have been collected; it never makes external calls.

## Multi-step evidence closure and literature draft report (0.6.7.11.12)

**Current `astroakd_100_v2` state (2026-10-19):** 80/80 single-call reference responses and 12/12 multi-archive references are complete. The six VizieR `not_structured_table` failures were resolved using `--resume --retry-incomplete`; no VizieR retries remain necessary. The remaining eight literature questions have no verified publication--observation association. Consequently 92/100 benchmark questions have complete automated reference evidence.

For other incomplete studies, `collect-multistep-references --resume --retry-incomplete --dry-run` previews only incomplete tasks. Add `--timeout 900 --attempts 2`, remove `--dry-run`, and retry; completed archive steps are reused. The pre-retry journal is saved under `*_multistep_references_preretry.jsonl`. Do not use `--replace` for selective recovery. VizieR responses may be a **list of tables**; every selected table is checked for the requested fields, truncation, and completeness.

### What `draft-literature-plans` actually produces

Run offline only when you need to generate or deliberately regenerate candidate literature plans:

```bash
uv run python -m benchmark draft-literature-plans \
  --name astroakd_100_v2 --output-dir datasets
```

The saved output `datasets/validated/astroakd_100_v2_literature_plan_drafts.jsonl` has **8 drafts**, summarized as `DRAFT_ONLY_NOT_REFERENCE`: **6 `DRAFT_UNVERIFIED`**, **2 `REQUIRES_TARGET_OR_ARCHIVE_RESOLUTION`**. This is a *drafting success*, **not** completion of eight literature references. The program makes no MCP, ADS, or OpenAI calls; `--replace` is needed only if you intentionally overwrite an existing draft output.

| Draft status | Task IDs | Meaning |
| --- | --- | --- |
| `DRAFT_UNVERIFIED` | `00004` PG 1211+143 (HEASARC); `00016` Haro 11 (HEASARC); `00029` NGC 1068 (HEASARC); `00045` PG 1211+143 (MAST); `00069` NGC 5548 (MAST); `00074` NGC 3783 (HEASARC) | A bounded archive call template can be prepared once SIMBAD coordinates and archive parameters are verified; cited papers are only candidates |
| `REQUIRES_TARGET_OR_ARCHIVE_RESOLUTION` | `00026` planetary nebulae in `2022MNRAS.514.1217D`; `00068` paper-identified tidal-disruption transient | The actual object/targets or query route must first be identified from the source literature |

Inspect the records using the existing CLI:

```bash
uv run python -m benchmark inspect \
  --input datasets/validated/astroakd_100_v2_literature_plan_drafts.jsonl \
  --limit 8
```

**Do not supply these draft records directly to `collect-multistep-references --literature-plans`.** The drafts contain `params_template` placeholders and are expressly **not executable reference plans**. `--literature-plans` expects separately specified `steps` containing complete, independently supported, read-only archive calls and expected fields. Even successful archive retrieval is insufficient when the question requires an observation linked to a particular paper; that association must also be verified. No inferred ObsIDs, invented associations, or automatic promotion of ADS candidates to references are allowed.

Once complete evidence exists, rerun the offline `score-reference-answers --name astroakd_100_v2 --output-dir datasets --replace` command. **Do not regenerate any synthetic questions or rerun the existing 300 A/B/C executions.** The current evidence-based score covers 92/100 questions, with all eight literature questions explicitly excluded.
