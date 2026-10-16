# ADS and MCP connectivity

ADS literature research is performed by the **external Astroquery MCP server**, not by the benchmark. The server must expose `astroquery_check_auth` and `ads_query_compact`, configure an ADS token, and reach the ADS service.

## Install and start the local MCP service

Run the following in a separate **server terminal**, outside the AstroAKD-Bench directory:

```bash
git clone https://github.com/NASA-IMPACT/astroquery-mcp.git
cd astroquery-mcp
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Keep the terminal open; AstroAKD-Bench connects to `http://127.0.0.1:8000/mcp` by default. If you will use `--require-ads`, configure the ADS API token **in this server terminal before starting the final command** (`API_DEV_KEY`, or the supported `ADS_API_KEY` fallback). Restart the server after changing credentials. The token does not belong in the benchmark's generated outputs.

In a **second terminal**, change to the AstroAKD-Bench repository root and install its dependencies with `uv sync`. Configure `OPENAI_API_KEY` securely in this benchmark terminal for question generation and A/B/C runs; ADS authentication remains on the server. The diagnostic commands below run from the benchmark root. See [Getting started](quickstart.md) for the complete two-terminal setup.

## Check before generation

```bash
uv run python -m benchmark literature-auth --probe
# Test the exact target that failed after the generic bibcode probe passed:
uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'
```

This performs a read-only authentication/tool inspection and a small real ADS bibliographic query. Successful configuration alone is insufficient: the request itself must succeed. The tool reports safe booleans and a diagnostic reason without printing credentials.

Failure reasons include `ads_not_configured`, `ads_tool_unavailable`, `ads_search_unavailable`, `ads_probe_empty`, and `mcp_auth_check_unavailable`.

The specific-query probe reports only sanitized error *classes* (for example `upstream_http_400_bad_query`, `upstream_http_401_authentication`, `upstream_http_403_forbidden`, `upstream_http_429_rate_limit`, `upstream_timeout`, or `mcp_ads_tool_error_unclassified`), not the server's original exception text. The client cannot resolve an unclassified upstream error without a private inspection of the MCP server logs. The benchmark explicitly sends the curated research target as a query hint (including PG 1211+143 even when the plan's long prose omitted it) and retries distinct query formulations using one compact ADS request each (the MCP server's field presets filter the results after the same upstream Astroquery call). All literature results remain unreviewed evidence, never gold answers.

The current Astroquery MCP server uses the `API_DEV_KEY` environment variable for ADS, with an `ADS_API_KEY` fallback. **Set the token in the environment of the MCP server process before starting the server**, not merely in the benchmark terminal. The token should never be checked into the repository or included in logs.

A failure of `ads_search_unavailable` means the MCP ADS request failed despite reaching that route. It does *not* prove authentication was missing. Check the server's network access to ADS, token validity, and ADS API availability. Run the probe again before repeating generation.

## Required vs optional ADS

With `--require-ads`, a failed ADS preflight stops `create-queries` before any question-generation OpenAI calls. The preflight now checks **each planned research query** with distinct query formulations and compact ADS field selection; success of a generic bibcode probe is not enough. Increasing archive reference timeouts does not correct an ADS HTTP 400/401/403/429 error. When strict ADS research is optional, omit `--require-ads` to allow explicitly labeled OpenAI web-search fallback instead. No question files are published when all ADS research alternatives fail. On errors after GPT authoring, completed batches are retained in `generated/<name>.progress.jsonl`; use `create-queries --resume` after correcting the service. Without that flag, a failed ADS research route may use an OpenAI web-search fallback, labeled with its true provenance; it is not ADS evidence.

## MCP endpoint

Default: `http://127.0.0.1:8000/mcp`. Override with `ASTROAKD_MCP_URL` or the CLI's `--mcp-url`. Protected MCP servers can use `ASTROAKD_MCP_TOKEN` for client bearer authentication; this is distinct from the ADS credential used by the **server**.

See the [Astroquery MCP server repository](https://github.com/NASA-IMPACT/astroquery-mcp) for server installation and authentication details.
