# Reference collection and scientific review

`create-queries --with-reference-answers` collects *reference observations*, not verified gold answers. Run collection separately (or resume an interrupted collection) with:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100 --output-dir datasets --resume
```

If you generated questions without `--with-reference-answers`, omit `--resume` on the first collection. For a pilot use `--limit 5`. Single-call results and their progress journal are under `datasets/validated/`.

## Completeness reports and plots

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100 --output-dir datasets
```

Outputs appear in `datasets/reports/astroakd_100/references/`. Plots and CSVs characterize archive mix, response statuses, answer shapes, missing data, null measurements, truncated responses, and response time. Reports can run even before all reference observations are collected and must accurately mark pending evidence.

## Review before scoring

Archive observations are **unreviewed evidence**. Multiple matching rows, truncation, units, coordinates and ambiguous cross-identifications need scientific review. Literature and multi-archive tasks in a mixed set require separate multi-step evidence collection and cannot be considered complete gold through the single-call collector.

The detailed commands `reference-review-draft` and `gold-finalize` remain available for explicitly reviewed single-call datasets. Do not promote generated questions or raw archive values to scientifically verified gold automatically.
