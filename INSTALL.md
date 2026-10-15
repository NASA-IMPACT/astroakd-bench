# Install AstroAKD-Bench

Use Python 3.11+ and `uv` from the source root:

```bash
uv sync
uv run python -m benchmark --help
```

To generate questions, set `OPENAI_API_KEY` and run the Astroquery MCP server as a **separate process**. When using `--require-ads`, configure the ADS token on the MCP server and first run:

```bash
uv run python -m benchmark literature-auth --probe
```

Follow the [README](README.md) for the exact 100-question workflow and [HTML quick-start](docs/benchmark/quickstart.md) for the steps and safety notes. To build the current documentation: `make -C docs/sphinx html`.

If generation is interrupted after any successful model batch, look in `datasets/generated/` for `<name>.progress.jsonl` and `<name>_partial.jsonl`. Correct the error and repeat the identical `create-queries` command with `--resume` to reuse completed batches. A failed ADS preflight before the first batch deliberately saves no progress file.

## Verify strict ADS literature searches

The MCP server's ADS token must be configured in **the server process**. Before enabling
`--require-ads`, check both the generic known-bibcode lookup and an actual target:

```bash
uv run python -m benchmark literature-auth --probe
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

If the known-bibcode lookup passes but the target lookup fails, inspect the sanitized
HTTP/error class and the private MCP server logs. Archive-reference timeout settings do
not change ADS authentication or Solr query behavior. Omitting `--require-ads` allows
OpenAI web-search fallback, clearly labeled as non-ADS evidence.
