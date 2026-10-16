# Reference collection and scientific review

`create-queries --with-reference-answers` collects *reference observations*, not verified gold answers. Run collection separately (or resume an interrupted collection) with:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100_v2 --output-dir datasets --resume
```

If you generated questions without `--with-reference-answers`, omit `--resume` on the first collection. For a pilot use `--limit 5`. Single-call results and their progress journal are under `datasets/validated/`.

## Completeness reports and plots

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 --output-dir datasets
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

Archive observations are **unreviewed evidence**. Multiple matching rows, truncation, units, coordinates and ambiguous cross-identifications need scientific review. Literature and multi-archive tasks in a mixed set require separate multi-step evidence collection and cannot be considered complete gold through the single-call collector.

The detailed commands `reference-review-draft` and `gold-finalize` remain available for explicitly reviewed single-call datasets. Do not promote generated questions or raw archive values to scientifically verified gold automatically.

## Feasibility gate versus collected references

`create-queries --with-reference-answers` in 0.6.7.11.9 first checks that each *proposed core query* returns bounded, nonempty, untruncated MCP evidence, including required answer columns and no null values. The precheck's source-response SHA-256 is retained in the question provenance and the selected plan is saved. The independent `collect-references` step later reexecutes those exact frozen calls; archives can change between calls, so precheck acceptance does **not** guarantee subsequent collection succeeds. All final reference dispositions and coverage/exclusion reasons must be reported. Literature/ADS and multi-archive tasks still need separate multi-step evidence. See [Creating questions](create_queries.md).
