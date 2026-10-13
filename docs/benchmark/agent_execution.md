# AstroAKD-Bench 0.4.1 — Agent execution and MCP tracing

`0.4.1` evaluates **how an independent agent behaves**, not whether its final answer
is scientifically correct. It does not automatically score answers; scoring is
planned for `0.5.0`.

## Input contract

- A completed 0.2.0 candidate JSONL file (`--tasks`).
- A completed 0.3.0 reference JSONL file (`--references`). These references
  must contain exactly one structurally accepted disposition per task.
- A running **local** Astroquery MCP server at `http://127.0.0.1:8000/mcp`.

The reference file is checked for dataset coverage and fingerprint consistency
before execution. **Neither the reference MCP call nor reference responses are
included in the agent prompt, tool catalog, trace, or final answer.** The
agent receives only the question and the allowable live MCP tools.

## Start the MCP server

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

## Step 1: No-LLM harness smoke (not a real agent)

```bash
uv run python -m benchmark run \
  --agent echo --strict-accepted-020 --limit 5 \
  --tasks benchmark/datasets/generated/synthetic_queries.jsonl \
  --references benchmark/datasets/validated/reference_answers.jsonl \
  --output benchmark/datasets/agent/echo_runs.jsonl \
  --report benchmark/datasets/agent/echo_report.json
```

`echo` only echoes the question. It makes no archive calls, is intentionally
marked `HARNESS_ONLY`, and must **never** be used as an agent-performance result.

## Step 2a: Actual OpenAI agent (optional API)

This is the first built-in LLM-backed agent option. Install the optional SDK
transiently (leaving `pyproject.toml` and `uv.lock` untouched) and supply
an OpenAI API key:

```bash
export OPENAI_API_KEY='your-api-key'
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --limit 5 \
  --max-turns 8 --max-calls 12 \
  --tasks benchmark/datasets/generated/synthetic_queries.jsonl \
  --references benchmark/datasets/validated/reference_answers.jsonl \
  --output benchmark/datasets/agent/openai_runs.jsonl \
  --report benchmark/datasets/agent/openai_report.json
```

This option **uses the OpenAI API**, may incur model charges, and is not needed
for the benchmark's earlier milestones or harness-only smoke tests. The selected
model must support Chat Completions function/tool calling.

The model decides which MCP tools to call; the benchmark validates and proxies
those calls. The gateway restricts operations to read-only discovery and bounded
queries on SIMBAD, MAST, HEASARC, Gaia, and VizieR.

## Step 2b: Integrate the existing AstroAKD agent

For a separate existing agent implementation, supply an importable async
adapter function via `--agent external --adapter module:function`.

The required contract is:

```python
async def run(question: str, gateway, max_turns: int) -> dict:
    # This is only an interface illustration, not a working astronomy agent.
    result = await gateway.call_tool('astroquery_list_modules', {})
    return {'answer': '...', 'turns': 1, 'token_usage': {}}
```

The `gateway` provides `advertised_tools()` and `call_tool(name, arguments)`.
The adapter must route **all MCP calls** through that gateway; a separate MCP
connection inside the agent will NOT appear in the benchmark's trace. No
specific AstroAKD production agent has been wired into this release because
its runtime integration interface has not been provided.

For example, if your adapter is `my_astroakd.bench_adapter:run`:

```bash
uv run python -m benchmark run \
  --agent external --adapter my_astroakd.bench_adapter:run \
  --strict-accepted-020 --limit 5 \
  --output benchmark/datasets/agent/astroakd_runs.jsonl \
  --report benchmark/datasets/agent/astroakd_report.json
```

## Step 3: Resume the same experiment

Repeat the same arguments but replace `--limit 5` with `--resume`:

```bash
uv run --with openai python -m benchmark run \
  --agent openai --model gpt-4.1-mini \
  --strict-accepted-020 --resume \
  --output benchmark/datasets/agent/openai_runs.jsonl \
  --report benchmark/datasets/agent/openai_report.json
```

The runner preserves journaled task results, even if an earlier task failed;
`--resume` does not re-execute already recorded task IDs. It checks the input
and reference SHA-256 fingerprints, endpoint, agent, model, and execution budgets
against the manifest before resuming. Outputs are not overwritten by default.
`--replace` explicitly discards earlier output and progress.

## Output files

```text
benchmark/datasets/agent/
  openai_runs.jsonl                      # completed runs, when all 50 processed
  openai_runs.jsonl.progress.jsonl       # fsynced results after each task
  openai_runs.jsonl.manifest.json        # immutable run configuration
  openai_report.json                    # totals, quality gate, SHA-256
```

Each task record has a task ID, question, agent type, final response or error,
start time, duration, model token usage when supported, and detailed MCP event
traces including tool name, bounded arguments, elapsed time, disposition,
response fingerprint and bounded tool output. Failed and rejected tool calls
are preserved too. Large tool results are omitted rather than written or sent
to the model in full. Sensitive JSON fields with standard credential names are
redacted, but **traces can still contain scientific data and potentially
sensitive prompt text**, so inspect before sharing.

The status `COMPLETE` means every benchmark task has an execution record;
`quality_gate=PASS` now also requires a successful `astroquery_execute` for
**every** real-agent task, not just nonempty text. The `query_evidence`
field reports whether archive execution evidence was observed. Even PASS is
**not** proof of scientific correctness. `REVIEW` includes answered tasks whose
MCP calls were all rejected. `HARNESS_ONLY` remains the echo disposition.

0.4.1 uses question-derived routing only when a question explicitly names
exactly one service. For HEASARC, Gaia and VizieR, the agent must use the
specified module, not substitute another archive. Rejections include valid
parameter guidance, and the OpenAI adapter offers one additional recovery
prompt within budgets. `max_rows` is restricted to MAST.

0.4.1 records its policy in the execution manifest, so an existing 0.4.0
pilot cannot be resumed under a modified policy. Start a new output path or
use `--replace` intentionally.

## Safety and limitations

- Only the four read-only Astroquery discovery/execution MCP tools are exposed;
  execute calls enforce allowed modules/methods, modest sky radii, bounded
  catalog names and object identifiers, and MAST-only `max_rows` support.
- No bulk downloads, mutation, arbitrary TAP/ADQL, file access, or
  authentication-management MCP tools are offered.
- One agent task at a time with per-task timeout, max reasoning turns and tool
  calls, plus a max tool-response size.
- A server/tool failure is captured as a trace event and returned to the agent.
- The OpenAI LLM is optional. The 0.4.0 five-task laptop pilot exposed archive
  misrouting; 0.4.1 needs a fresh live laptop qualification.
- Future `0.5.0` will compare these traces and answers to independent reference
  checks, and `0.6.0` will implement deterministic offline archive replay.

## Qualification

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

The offline suite mocks MCP HTTP calls and LLM tool-call responses. The accepted
0.2.0 dataset is retained byte-for-byte; the accepted reference data is a runtime
input from your laptop, not embedded in the distributable overlay.
