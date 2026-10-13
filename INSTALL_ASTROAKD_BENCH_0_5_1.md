# AstroAKD-Bench 0.5.1 — install and qualification

AstroAKD-Bench is a **standalone repository**, separate from the NASA IMPACT Astroquery MCP server. The full ZIP/TAR.GZ includes `README.md`, `CHANGELOG.md`, Python source, tests, docs and the immutable accepted candidate/reference datasets at **root-level `datasets/`**.

## Preferred: complete standalone checkout

Extract the 0.5.1 ZIP into a new or dedicated AstroAKD-Bench directory. Do **not** extract it over the unrelated Astroquery MCP server repository; that server has its own root `README.md` and `pyproject.toml`.

From the AstroAKD-Bench repository root:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m unittest discover -s benchmark/tests -v
```

If upgrading from 0.5.0 with the focused 0.5.0-to-0.5.1 Git patch, apply it from the **AstroAKD-Bench** root. Accepted datasets stay in `datasets/` unchanged:

```bash
git apply --check astroakd_bench_0_5_0_to_0_5_1.patch
git apply astroakd_bench_0_5_0_to_0_5_1.patch
```

For older 0.4.1 installations, use the 0.5.0 migration instructions before this update. The historical migration script is retained below for reference:

```bash
git apply --check astroakd_bench_0_4_1_to_0_5_0_code_only.patch
git apply astroakd_bench_0_4_1_to_0_5_0_code_only.patch
uv run python scripts/migrate_datasets_0_5_0.py
```

The 0.5.0 migration **refuses to overwrite** when both old and new dataset directories exist. For full release archives the accepted root datasets are already included, so do not run the migration on top of conflicting root datasets. Preserve any custom run journals manually if merging local work into a fresh installation.

## Verify frozen data and evaluate historical 0.4.1 trace

```bash
sha256sum datasets/generated/synthetic_queries.jsonl \
  datasets/validated/reference_answers.jsonl

uv run python -m benchmark evaluate \
  --strict-accepted-020 \
  --runs datasets/agent/openai_041_runs.jsonl.progress.jsonl \
  --output datasets/evaluation/openai_041_scores_recheck.jsonl \
  --report datasets/evaluation/openai_041_report_recheck.json \
  --csv datasets/evaluation/openai_041_scores_recheck.csv \
  --pretty-output datasets/evaluation/openai_041_scores_recheck_pretty.json \
  --json-format pretty
```

The `--pretty-output` file is a fully indented JSON array containing the same five score records as compact JSONL. `--json-format pretty` alone only affects stdout and summary reports.

The included historical five-task pilot yields mean technical evidence 94/100, 3 PASS and 2 REVIEW. Scientific answers require independent verification. On re-execution, add `--replace` to overwrite previously generated evaluation artifacts intentionally.

To inspect a JSONL file without changing its SHA-256:

```bash
uv run python -m benchmark inspect \
  --input datasets/evaluation/openai_041_scores.jsonl \
  --limit 2 --json-format pretty \
  --output datasets/evaluation/inspection.json
```

## Live qualification

Start the external Astroquery MCP server in its own checkout:

```bash
cd /path/to/astroquery-mcp
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

In the separate AstroAKD-Bench checkout, check MCP and optionally execute a **new** five-task OpenAI run:

```bash
uv run python -m benchmark doctor --smoke --json-format pretty

uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --limit 5 --max-turns 8 --max-calls 12 \
  --output datasets/agent/openai_050_runs.jsonl \
  --report datasets/agent/openai_050_report.json \
  --json-format pretty
```

`OPENAI_API_KEY` is needed only for `--agent openai`. Use `--runs datasets/agent/openai_050_runs.jsonl.progress.jsonl` for a partial pilot when evaluating the new trace; do **not** mistake a partial run for full 50-task qualification. No live agent run was performed in the delivery environment.
