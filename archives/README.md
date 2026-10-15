# Historical reproducibility records

`datasets/` is a clean working directory. Historical experiments, prior installation notes, qualification logs and earlier documentation are **not installed** by unpacking the current source archive.

For scientific provenance, the source ships **manifests** listing the per-file SHA-256 checksums of separate, downloadable archives:

- `historical_datasets_manifest_0_6_7_11_3.json` — frozen historical dataset snapshot. Its separate data archive is `astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz`; the 50-question stand-alone archive is `astroakd_bench_frozen_gpt52_50_0_6_7_11_2.tar.gz`.
- `historical_documentation_manifest_0_6_7_11_4.json` — prior version-specific installation guides, qualification reports, development handoffs, and old Sphinx Markdown source pages. Its separate archive is `astroakd_bench_0_6_7_11_3_historical_documentation.tar.gz`.

A fresh source checkout does **not** contain the archived files. Download the relevant external tarball separately if you need historical audit evidence, and inspect it in a separate directory rather than overlaying a live `datasets/` working tree.

Frozen 50-question regression inputs are still available in `benchmark/tests/fixtures/legacy/` with unchanged bytes. Use `scripts/verify_historical_dataset_archive.py` and `scripts/verify_historical_documentation_archive.py` to verify the corresponding optional archives against manifests.
