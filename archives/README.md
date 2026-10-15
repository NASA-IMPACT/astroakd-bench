# Historical experiment archives (external to the source package)

The actual data archives are separate release downloads, **not** embedded in the main source package. The per-file SHA-256 manifest is `historical_datasets_manifest_0_6_7_11_3.json`.

- `astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz` — all 118 exact source dataset files from the 0.6.7.11.2 baseline.
- `astroakd_bench_frozen_gpt52_50_0_6_7_11_2.tar.gz` — original frozen 50-question tasks, oracle, saved three-arm journal and full paired reports, byte-identical to the corresponding files in the complete archive.

Both archives contain `ARCHIVE_MANIFEST.json`. The manifest is identical to the JSON in this source directory. The nine essential test fixtures are copied into `benchmark/tests/fixtures/legacy/`; test runs do **not** need the external archives. Use `scripts/verify_historical_dataset_archive.py` to verify an archive before restoring it. Do not unpack an archive over active study data.
