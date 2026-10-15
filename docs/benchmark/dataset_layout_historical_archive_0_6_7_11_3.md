# Dataset layout and historical archive — 0.6.7.11.3

The new source package keeps `datasets/` as an **empty user-facing workspace** (except for `datasets/README.md`). Old benchmark results were archived **outside** the source release, not discarded. By design, `create-queries`, `collect-references`, `reference-report`, `run-benchmark`, and `agent-report` create output subdirectories as needed. The paths passed with `--output-dir datasets` are **the root**, and new files go to `datasets/generated/`, `validated/`, `agent/`, and `reports/`.

## Recommended command

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers
```

The CLI has an optional `--seed` with default `20261018`, which helps reproduce local target selection but not byte-identical model output. The 100-question balanced recipe includes 80 eligible single-call tasks and 20 literature/multi-archive tasks that **do not** receive complete automatic multi-step references. All gathered reference values remain unreviewed until independent science review.

## Separate archives

The complete 0.6.7.11.2 `datasets/` snapshot (118 files) is preserved byte-for-byte in:

- `astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz`: **every original dataset file**, with its original relative `datasets/` path and `ARCHIVE_MANIFEST.json`.
- `astroakd_bench_frozen_gpt52_50_0_6_7_11_2.tar.gz`: a convenience subset containing the frozen 50-question GPT-5.2 experiment tasks, oracle, saved run journal, and all `gpt52_full_paired_0678` report files. This is a second copy, not an altered version of those files.

The source release includes the independent [per-file SHA-256 manifest](../../archives/historical_datasets_manifest_0_6_7_11_3.json) containing paths, byte sizes, original SHA-256 digests, and frozen task/oracle hashes. To recover the full historical tree without overwriting a new study:

```bash
mkdir -p /tmp/astroakd-history
tar -xzf astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz \
  -C /tmp/astroakd-history
```

For an older experiment command, run it in the restored historical checkout or explicitly pass input file paths from `/tmp/astroakd-history/datasets/`. **Never extract over live `datasets/`** or regenerate the original reference data.

## Frozen scientific fingerprints

| File | Accepted SHA-256 |
| --- | --- |
| `datasets/generated/scorable_50.jsonl` | `4744ae4df40381eea635a92a13d8af6f83fd69c0e2274c839e1dbb04f382bbb8` |
| `datasets/gold/scorable_50_reference_oracle.jsonl` | `58caf910963cdce4e333ae5a0a6d48501ece27bce71352b15664a10a76fc1d5e` |

The historical file `datasets/agent/scorable_50_gpt52_runs.jsonl.progress.jsonl` is preserved with its **actual** SHA-256 in the manifest. These reference-snapshot agreements are **not independently verified scientific accuracy**. Do not claim scientific correctness from a snapshot match. No old bytes were edited or re-generated during cleanup.

## Minimal offline regression inputs

Nine byte-exact files required by the existing tests are available in `benchmark/tests/fixtures/legacy/` with the original subpaths: `generated/`, `validated/`, `agent/`, `gold/`, and `replay/`. Tests use these paths instead of depending on a populated working `datasets/`. The original upstream `datasets/` paths remain preserved in the complete historical archive and advanced command defaults are not silently changed.

## Verifying archives

You can independently recompute the digest for any file in the source-independent archive:

```bash
python - <<'PYTHON'
import hashlib, json, tarfile
from pathlib import Path
manifest = json.loads(Path('archives/historical_datasets_manifest_0_6_7_11_3.json').read_text())
with tarfile.open('astroakd_bench_historical_datasets_0_6_7_11_2.tar.gz', 'r:gz') as archive:
    for entry in manifest['files']:
        content = archive.extractfile(entry['path']).read()
        assert len(content) == entry['bytes']
        assert hashlib.sha256(content).hexdigest() == entry['sha256'], entry['path']
print('All 118 archived files verified')
PYTHON
```

Archive files are distributed **beside** the release; copy/download both the source and archive first, or update the paths in the verification example. The archive's internal `ARCHIVE_MANIFEST.json` matches the source manifest byte-for-byte.
