# AstroAKD-Bench — 0.1.0 LOCAL_MCP_CONNECTION

This archive is an **additive overlay**, not a modified copy of the upstream
[NASA-IMPACT/astroquery-mcp](https://github.com/NASA-IMPACT/astroquery-mcp)
repository. Copy the `benchmark/` and `docs/benchmark/` directories into an
existing checkout of that repository. No production files need replacing.

Quick start, using two terminals in the repository root:

```bash
# Terminal A
uv sync
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000

# Terminal B
uv run python -m benchmark doctor --fast
uv run python -m benchmark doctor --smoke --output benchmark/local_mcp_qualification.json
uv run python -m unittest discover -s benchmark/tests -v
```

For detailed setup, behavior, and acceptance gates see
`docs/benchmark/local_mcp_connection.md`.

*Source basis:* NASA-IMPACT/astroquery-mcp, `main` as inspected 2026-10-13.
This archive does not contain upstream code because the implementation is
purely additive.
