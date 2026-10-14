# Gold Benchmark task families and authenticated ADS search

## Reference workbook

The uploaded `Gold Benchmark Dataset.xlsx` contains **31** numbered rows in
`benchmark_queries`: 20 archive-driven, 7 coordinate-driven and 4 literature-driven.
The sheet is used to derive instructions and task types. It is **not copied into
this package**, and its expected answers are **not** treated as verified by the
synthetic-query generation engine.

| Family | Basis | Grounding required |
|---|---|---|
| `archive_driven` | named source, mission, instrument, year, identifier | correctly scoped archive metadata |
| `coordinate_driven` | ICRS/J2000 sexagesimal coordinates and angular radius | coordinate conversion and actual bounded archive search |
| `literature_driven` | published astrophysical description | paper/object discovery, then *separate* archive search |

## Astroquery MCP setup (required for ADS)

In the **astroquery-mcp** checkout, with ADS key exported in the process environment:

```bash
export API_DEV_KEY="your-ads-token"
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

If the key is in `~/.bashrc`, confirm it is available in the shell *that launches*
the server: `test -n "$API_DEV_KEY" && echo 'ADS configured' || echo 'ADS unavailable'`.
Do not paste the key into benchmark CLI arguments, the workbook, logs, or reports.
Restart a previously running MCP server if you changed its environment.

MCP provides `astroquery_check_auth` and the dedicated read-only literature tools
`ads_query_compact` and `ads_get_paper`. AstroAKD-Bench never imports Astroquery
or connects to NASA ADS directly. Server-reported ADS configuration takes precedence
over what the benchmark's own shell happens to expose.

## Literature research CLI

Check the server's ADS state without exposing any token or requiring OpenAI:

```bash
uv run python -m benchmark literature-auth --json-format pretty
```

Both `ads_authenticated` and `ads_tool_available` should be `true` for
MCP ADS search. If false, check the **server** shell environment and restart
the server; the benchmark process having a key does not mean the server has it.

From the independent AstroAKD-Bench checkout:

```bash
uv run --with openai python -m benchmark literature-search \
  --query 'z=0.0809 quasar ultra-fast outflow 17300 km/s HETGS' \
  --max-results 5 --json-format pretty \
  --output datasets/generated/literature_0644.json
```

- ADS configured in MCP: `astroquery_check_auth` -> `ads_query_compact`.
- Key absent in MCP: **automatically** use OpenAI Responses `web_search`.
- `--no-mcp`: use web search deliberately, even if ADS is configured.
- ADS search failed: fallback to OpenAI web search; report a generic reason and do not expose tokens.
- If the fallback is necessary, `OPENAI_API_KEY` and `uv run --with openai` are
  required. No search provider can be called without credentials/network access.

The fallback now handles both JSON and **ordinary Responses `web_search` prose**.
The report indicates `research_response_format`, carries
`research_summary_unverified` (prose) or `suggested_question_unverified` (JSON),
collects URLs from both web-search sources and message annotations, and marks
`source_review_required=true` if no verifiable source URLs were surfaced.
A sanitized `fallback_reason` such as `ads_not_configured`,
`ads_search_unavailable`, or `mcp_auth_check_unavailable` is also included;
none of these fields include tokens.

Every report has `scientific_truth_verified: false`; searching for a paper does
not verify telescope dataset existence. The evidence step is **separate** from
the existing `generate` workflow, which still produces single-archive questions
and does not yet automatically generate multi-stage literature-to-archive tasks.

## Python API

```python
from benchmark.api import AstroAKDBench
import asyncio

async def main():
    bench = AstroAKDBench(root='.')
    evidence = await bench.research_literature(
        'nearest tidal disruption event NICER observational papers')
    print(evidence['research_provider'], evidence['research_sources'])

asyncio.run(main())
```

## Official server references

- https://github.com/NASA-IMPACT/astroquery-mcp/wiki
- https://github.com/NASA-IMPACT/astroquery-mcp/wiki/MCP-Tools
- https://github.com/NASA-IMPACT/astroquery-mcp/wiki/Archive-ADS
