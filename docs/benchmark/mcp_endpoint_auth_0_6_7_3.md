# AstroAKD-Bench 0.6.7.3 — MCP endpoint and authentication

AstroAKD-Bench connects to an *external* Astroquery MCP server; its configuration is separate from the AstroAKD agent instructions and from synthetic query-generation instructions.

## Precedence and commands

| Setting | First | Second | Fallback |
| --- | --- | --- | --- |
| Endpoint | `--mcp-url` or `--mcp-server` | `ASTROAKD_MCP_URL` | `http://127.0.0.1:8000/mcp` |
| Bearer token | `--mcp-token` or `--mcp-server-token` | `ASTROAKD_MCP_TOKEN` | no authentication |

An empty environment string behaves as unset. An explicit `--mcp-token ''` disables a nonempty environment token for that command. The generic `MCP_URL` and `MCP_TOKEN` names are deliberately ignored.

In `~/.bashrc` for localhost:

```bash
export ASTROAKD_MCP_URL='http://127.0.0.1:8000/mcp'
unset ASTROAKD_MCP_TOKEN
```

For a remote server:

```bash
export ASTROAKD_MCP_URL='https://coming-gray-slug.fastmcp.app/mcp'
export ASTROAKD_MCP_TOKEN='REPLACE_WITH_YOUR_ACCESS_TOKEN'
```

Avoid placing your actual token in an invocation because shell history, process listings and job schedulers can expose command-line arguments. Consider your workstation's secret manager for production deployments. Never put a bearer token in the URL or upload a `.bashrc` that contains it.

After changing `.bashrc`, start a new interactive shell or run `source ~/.bashrc` (only when you trust that file). Then check:

```bash
uv run python -m benchmark doctor --fast --json-format pretty
```

To override the environment URL for one command:

```bash
uv run python -m benchmark doctor --mcp-server 'https://alternate.example/mcp' --fast
```

The selected URL is shown in connection failures, for example:

```text
Cannot connect to MCP server at https://alternate.example/mcp: ...
```

Bearer tokens are passed using FastMCP's `BearerAuth`. Authentication failures (401/403) and network failures are different errors; neither is evidence of an astrophysical query failure. Use HTTPS for remote authenticated servers.

## Resume and experimental integrity

`run-three-arm` records the effective MCP endpoint in its no-secret manifest. **Do not change the URL between a pilot and `--resume`**, even if the new server has the same tools. The result must reject, rather than silently mix, different science sources. The token itself is never saved in the manifest, so credentials may be rotated for the same endpoint without changing the frozen experiment context.

The three-arm runner checks a real MCP connection before attempting new tasks. This preflight requires the MCP server to be reachable even though the `web_only` arm itself uses web search. That preserves fair A/B/C comparisons on the same task set. Offline injected test clients bypass the real preflight.

Offline scoring and CSV generation (`score-scorable`) do not contact MCP, so token and URL variables do not affect their scientific scores.

## Limitations

Only bearer-token authentication is added here, not interactive OAuth authorization or dynamic token refresh. A custom server must implement a compatible Streamable HTTP MCP protocol and expose the Astroquery read-only tools required by the selected task set. This release's remote-server behavior is offline tested; live host acceptance requires a successful `doctor` call against your remote endpoint.
