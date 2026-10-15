# ADS and MCP connectivity

ADS literature research is performed by the **external Astroquery MCP server**, not by the benchmark. The server must expose `astroquery_check_auth` and `ads_query_compact`, configure an ADS token, and reach the ADS service.

## Check before generation

```bash
uv run python -m benchmark literature-auth --probe
```

This performs a read-only authentication/tool inspection and a small real ADS bibliographic query. Successful configuration alone is insufficient: the request itself must succeed. The tool reports safe booleans and a diagnostic reason without printing credentials.

Failure reasons include `ads_not_configured`, `ads_tool_unavailable`, `ads_search_unavailable`, `ads_probe_empty`, and `mcp_auth_check_unavailable`.

The current Astroquery MCP server uses the `API_DEV_KEY` environment variable for ADS, with an `ADS_API_KEY` fallback. **Set the token in the environment of the MCP server process before starting the server**, not merely in the benchmark terminal. The token should never be checked into the repository or included in logs.

A failure of `ads_search_unavailable` means the MCP ADS request failed despite reaching that route. It does *not* prove authentication was missing. Check the server's network access to ADS, token validity, and ADS API availability. Run the probe again before repeating generation.

## Required vs optional ADS

With `--require-ads`, a failed ADS preflight stops `create-queries` before any question-generation OpenAI calls. No question files are published. Without that flag, a failed ADS research route may use an OpenAI web-search fallback, labeled with its true provenance; it is not ADS evidence.

## MCP endpoint

Default: `http://127.0.0.1:8000/mcp`. Override with `ASTROAKD_MCP_URL` or the CLI's `--mcp-url`. Protected MCP servers can use `ASTROAKD_MCP_TOKEN` for client bearer authentication; this is distinct from the ADS credential used by the **server**.

See the [Astroquery MCP server repository](https://github.com/NASA-IMPACT/astroquery-mcp) for server installation and authentication details.
