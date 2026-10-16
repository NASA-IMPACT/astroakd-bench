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
