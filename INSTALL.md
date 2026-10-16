# Install AstroAKD-Bench

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

The archive service is a **separate** repository. In a first terminal, clone, install and start the local Astroquery MCP server:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Leave that terminal running. For strict ADS research, set `API_DEV_KEY` (or the server-supported `ADS_API_KEY` fallback) in **the server process environment before launching it**; never commit or log the token. If the token is added later, restart the server.

In a second terminal, change to the AstroAKD-Bench repository root, configure `OPENAI_API_KEY` securely, and install/check the benchmark:

```bash
uv sync
uv run python -m benchmark --version
uv run python -m benchmark --help
uv run python -m benchmark doctor --fast
```

The local MCP endpoint is `http://127.0.0.1:8000/mcp`; set `ASTROAKD_MCP_URL` if using another endpoint.

When using `--require-ads`, first run:

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
