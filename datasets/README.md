# Datasets — user working directory

`datasets/` is an initially empty workspace for **your own** experiments. It does not ship previous experiments, validated science answers or the historical data archive. A freshly unpacked AstroAKD-Bench release is expected to contain only this README in this directory.

A named study created with `--name astroakd_100_v2 --output-dir datasets` writes to:

- `generated/`: synthetic question JSONL, CSV, family subsets and generation report
- `validated/`: single-call reference observations and resumable journal (if requested)
- `agent/`: A/B/C execution journal and summary
- `reports/`: offline CSV summaries, PNG and SVG plots

The short commands (`create-queries`, `collect-references`, `reference-report`, `run-benchmark`, `agent-report`) create their own output directories when they write files. You do **not** need to create them manually. `--with-reference-answers` covers eligible single-call observations only; literature and multi-archive reference work remains pending, and no collected value is automatically verified scientific gold.

Historical experiment results are distributed **separately** from the source package; you will not find them here unless you explicitly restored an optional archive. A checksum manifest of the previous historical dataset snapshot is retained under `archives/` for scientific provenance. The small number of inputs required for regression tests are instead kept under `benchmark/tests/fixtures/legacy/`.

For normal use, follow the [current README](../README.md) and [documentation](../docs/index.md).
