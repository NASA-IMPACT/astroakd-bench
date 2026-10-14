# OpenAI-assisted synthetic query generation (0.6.4–0.6.4.2)

AstroAKD-Bench and the [NASA IMPACT Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp) are **separate** repositories. The benchmark does not alter the MCP server. This optional LLM generator uses the **OpenAI Responses API** to author questions; it never reads the answers in `Astro Benchmark V1.xlsx` as gold.

## 0.6.4.2 correction: model-altered or missing task IDs

A real 0.6.4.1 OpenAI + MCP generation stopped at **batch 6 of 10** with
`OpenAI changed or omitted task IDs`. The submitted failure report contains only
this error, not the model's raw response; the precise altered IDs are unknown.

All slot IDs and MCP calls are defined **before** contacting OpenAI. From 0.6.4.2,
model-written IDs are advisory. If the provided IDs are absent, changed,
repeated, or attached to reordered questions, the benchmark uses validated
**whole-target-name and archive** correspondence to find a *unique* assignment
back to its immutable slots. It never trusts an approximate target substring
(`M1` is not `M101`) and never changes stored reference-call arguments. A
missing archive name may still be prefixed using the approved 0.6.4.1 rule.

If no unique scientifically compatible assignment exists, the model is asked
to regenerate **only that batch, once**. The operation fails closed when the
retry is unsafe; it never invents task IDs or answers. Repaired records expose
`provenance.task_id_repaired` and `provenance.original_llm_task_id` (which may
be null if the model omitted it). The generation summary includes
`task_id_repairs`, `archive_name_repairs`, `openai_batch_retries`, and
`openai_requests`. Counts are auditable but not proof of astronomical accuracy.

For a new run use fresh paths such as `llm_0642_mcp.jsonl` and `llm_0642_mcp_report.json`;
previous FAIL reports may remain, even if no candidate JSONL was published.
The original seed=42 dataset and 50-entry replay fixture remain unchanged.

## 0.6.4.1 correction: omitted archive name

The first live OpenAI + MCP generation on version 0.6.4 stopped after the first five tasks because model question `ASTROAKD-020-00005` did not explicitly say *VizieR*. The strict question-derived archive router requires an unambiguous archive name. Version 0.6.4.1 adds a neutral `Using VizieR, ...` prefix **only if** the model omitted all supported archive names and retained its assigned target. Its MCP tool arguments remain prebound and unchanged.

Questions explicitly naming a different archive (or more than one), omitting their astronomical target, asking for unsupported fields, or adding unbound years still fail. The report contains `archive_name_repairs`; per-task `provenance` includes `archive_name_repaired` and (only when repaired) `original_llm_question`. This is an auditable correction of wording, **not a claim of scientific validity**.

To retry after a failed 0.6.4 run, use fresh output/report paths, for example change `llm_064_*` to `llm_0641_*` in the command below. An existing failed generation summary report may block a retry using the exact same paths without `--replace`.

## Three generation backends

- **`--backend openai` (default):** Select safe, diverse archive/target/intent slots; OpenAI writes fresh natural-language questions. The benchmark checks generated questions and refuses any invalid/duplicate batch. With MCP enabled, all MCP calls are obtained from live schema discovery and not chosen or edited by the model.
- **`--backend hybrid`:** The benchmark first creates an answer-oriented template question for each MCP-bound slot and asks OpenAI to rewrite it conservatively. Recommended when you want high constraint fidelity and moderate language diversity.
- **`--backend template`:** Original reproducible 0.6.3 generation, no OpenAI API calls. It requires the MCP server for signature discovery; pass `--backend template` explicitly for historical reproducibility.

## Instructions and archive discovery

By default, both `--instructions` **and** `--mcp` are enabled. `--no-instructions` removes the workbook-derived instructions (the short safety/JSON contract remains). `--instructions-file your_prompt.md` supplies a custom prompt (cannot combine with `--no-instructions`).

| CLI flags | MCP server | OpenAI tool | Task track | `benchmark validate` supported? |
|---|---|---|---|---|
| `--backend openai --instructions --mcp` **default** | Required for read-only signature discovery | Responses text generation | Executable Astroquery MCP-bound candidate | Yes, after generation |
| `--backend openai --no-instructions --mcp` | Required | Responses text generation | Executable Astroquery MCP-bound candidate | Yes |
| `--backend openai --instructions --no-mcp` | Not used | Responses `web_search` hosted tool | Web-research candidate, sources are advisory | **No** (separate future reference track) |
| `--backend openai --no-instructions --no-mcp` | Not used | Responses `web_search` hosted tool | Web-research candidate | **No** |

`--backend hybrid` supports the same flag combinations. For the no-MCP mode, local seed/intent **slots** are only a planning aid; the `reference_call` is deliberately null and `execution_track=openai_web_search_research`. The benchmark refuses to pass these tasks to the legacy Astroquery-only reference validator. Web-search results are model context, **not** verified astronomical answers. Only source URLs found in provider search metadata are retained, and sources may be empty if the API does not expose metadata.

## Setup

Install the project and OpenAI SDK as separate dependencies:

```bash
uv sync
export OPENAI_API_KEY="..."  # do not add keys to files or version control
```

`uv run --with openai` installs the optional OpenAI SDK for a command. Your OpenAI API account needs active billing; API usage and hosted web search may incur charges. A ChatGPT subscription is not an API key.

For MCP mode, start the external service in its own directory:

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

## Default: V1 instructions + MCP-bound OpenAI questions

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --instructions --mcp \
  --model gpt-4.1-mini --batch-size 5 --count 50 --seed 123 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --output datasets/generated/llm_064_mcp.jsonl \
  --csv-output datasets/generated/llm_064_mcp.csv \
  --pretty-output datasets/generated/llm_064_mcp_pretty.json \
  --report datasets/generated/llm_064_mcp_report.json \
  --json-format pretty
```

The model does not execute any archive queries during generation. For subsequent reference validation, use **the generated MCP-backed JSONL**, new output names, and a one-task pilot first:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/llm_064_mcp.jsonl --limit 1 \
  --attempts 1 --timeout 30 \
  --output datasets/validated/llm_064_refs.jsonl \
  --report datasets/validated/llm_064_report.json \
  --pretty-output datasets/validated/llm_064_refs_pretty.json
```

Then resume with `--resume` and the same paths. Do not use `--strict-accepted-020` for a new dataset. The candidate JSONL and every export remain user-controlled research artifacts, never independently verified gold.

## OpenAI web-search alternative (no MCP server)

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --no-mcp --instructions \
  --model gpt-4.1-mini --count 50 --seed 123 \
  --output datasets/generated/llm_064_web.jsonl \
  --csv-output datasets/generated/llm_064_web.csv \
  --pretty-output datasets/generated/llm_064_web_pretty.json \
  --report datasets/generated/llm_064_web_report.json
```

Every batch requires at least one observed hosted `web_search` tool call; if the tool is unavailable, generation fails closed without publishing output. This **does not** silently fall back to template generation or MCP. Since search is external, network/service/billing access is needed. The resulting tasks are not immediately interchangeable with the MCP agent scorer.

## Compare instructions on/off and MCP on/off

Use **different output paths for each condition** to keep controlled comparison datasets independent. Compare the same seed, count, model, modules and uniqueness policy; use `--no-instructions` and/or `--no-mcp`. `seed` selects deterministic slots, but OpenAI response wording, search results and answer quality are **not** guaranteed deterministic. Reports include model, instruction SHA-256, MCP flag, request count, and observed search tool calls.

## Python API

```python
import asyncio
from benchmark.api import AstroAKDBench

async def main():
    bench = AstroAKDBench(root=".")
    result = await bench.generate_queries(
        backend="hybrid", model="gpt-4.1-mini",
        use_instructions=True, use_mcp=True,
        count=10, seed=2026,
        output="datasets/generated/study.jsonl",
        csv_output="datasets/generated/study.csv",
        pretty_output="datasets/generated/study_pretty.json",
    )
    print(result["openai_requests"])

asyncio.run(main())
```

Supply `instructions_file="my_custom_prompt.md"` for future domain-specific guidelines. Tests can inject `openai_client_factory` and `session_factory` to avoid network calls.

## Reproducibility, safeguards and limitations

- Source workbook **guides question style** (observation IDs, exposure time, instrument/filter and proposal details); its expected answers are not imported, because they may be inconsistent or erroneous.
- In MCP mode, the LLM cannot mutate archive module/function arguments. Query wording is checked for target continuity and some unsupported restrictions. This is **not** a full semantic theorem prover: inspect all questions and archive result fields before scoring.
- No-MCP mode never makes an MCP connection, but uses paid OpenAI web search and yields research-only tasks, without guaranteed sources or gold.
- Script writes canonical compact JSONL, CSV, and pretty JSON when requested, using distinct destinations. Existing frozen seed=42 datasets and fixture files are untouched.
- No live OpenAI API credential was available during off-host qualification; OpenAI requests/web-search integration are qualified with SDK-shape mock clients and require laptop testing.

## OpenAI documentation

- [Responses API](https://platform.openai.com/docs/api-reference/responses/create)
- [Web search in the Responses API](https://platform.openai.com/docs/guides/tools-web-search)
