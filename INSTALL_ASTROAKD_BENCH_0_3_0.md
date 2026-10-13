# Install AstroAKD-Bench 0.3.0

1. Keep your accepted 0.2.0 checkout, including the HEASARC `kwargs` signature fix.
2. Extract the `astroakd_bench_0_3_0_overlay.zip` at the root of the
   `astroquery-mcp` repository, allowing additive `benchmark/` and
   `docs/benchmark/` files to update. **Alternatively**, apply the Git patch
   `astroakd_bench_0_2_0_to_0_3_0.patch` from the repository root; use just
   **one** installation method.
3. Leave `benchmark/datasets/generated/synthetic_queries.jsonl` unchanged.
4. Run `uv run python -m unittest discover -s benchmark/tests -v`.
5. Start the MCP server (`uv run fastmcp run server.py --transport http --host
   127.0.0.1 --port 8000`).
6. Run the five-task `validate --limit 5` pilot, and use `validate --resume` to
   finish all 50 calls, following `docs/benchmark/reference_validation.md`.

**Do not** overwrite production `server.py`, `executor.py`, `pyproject.toml`,
`uv.lock`, or the existing generated 0.2.0 candidate dataset. The validator
uses no OpenAI API.
