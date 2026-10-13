# Install AstroAKD-Bench 0.2.0

This package is an **additive overlay** on an existing checkout of
[NASA-IMPACT/astroquery-mcp](https://github.com/NASA-IMPACT/astroquery-mcp)
that already contains the accepted AstroAKD-Bench 0.1.0 directory. The overlay
contains the complete `benchmark/` directory plus `docs/benchmark/`; it does
not include or replace the upstream `server.py`, `executor.py`, `pyproject.toml`,
`uv.lock`, or top-level `README.md`.

From your astroquery-mcp checkout, either apply the delta Git patch:

```bash
git apply --check astroakd_bench_0_1_0_to_0_2_0.patch
git apply astroakd_bench_0_1_0_to_0_2_0.patch
```

or unzip `astroakd_bench_0_2_0_overlay.zip` into the repository root,
overwriting the previous benchmark files. Do **not** apply both the patch and
the overlay. The patch assumes the exact supplied 0.1.0 baseline.

Server in Terminal A:

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Terminal B:

```bash
uv run python -m benchmark doctor --fast
uv run python -m benchmark generate --count 50 --seed 42 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --output benchmark/datasets/generated/synthetic_queries.jsonl \
  --report benchmark/datasets/generated/generation_report.json
uv run python -m unittest discover -s benchmark/tests -v
```

Check output line count and the `status`, `count`, `by_module`,
`archive_queries_executed`, `signature_sources`, and `dataset_sha256` values in
the generated report. For exact requirements and limitations see
`docs/benchmark/synthetic_query_generation.md`.
