# MCP tool-call recording and A/B comparison — 0.6.7.7

The native `run-three-arm` gateway already records each agent MCP tool call in the
per-run `trace` array of the JSONL journal. Release 0.6.7.7 makes this evidence
**inspectable without rerunning GPT-5.2**, including the exact tool sequence
per question and per-arm tool-use summaries. This workflow is completely offline.

## Export individual calls and plot comparisons

From the repository root, after a full run has produced its final `.jsonl`:

```bash
uv run --with matplotlib python -m benchmark score-scorable \
  --tasks datasets/generated/scorable_50.jsonl \
  --oracle datasets/gold/scorable_50_reference_oracle.jsonl \
  --runs datasets/agent/gpt52_fresh_runs.jsonl \
  --comparison-csv datasets/reports/gpt52_fresh_ABC_answers.csv \
  --summary-csv datasets/reports/gpt52_fresh_rates.csv \
  --detailed-csv datasets/reports/gpt52_fresh_detailed.csv \
  --performance-csv datasets/reports/gpt52_fresh_performance.csv \
  --task-performance-csv datasets/reports/gpt52_fresh_per_task_performance.csv \
  --mcp-calls-csv datasets/reports/gpt52_fresh_mcp_calls.csv \
  --mcp-tool-frequency-csv datasets/reports/gpt52_fresh_mcp_tool_frequency.csv \
  --plots-dir datasets/reports/gpt52_fresh_plots \
  --report datasets/reports/gpt52_fresh_scores.json
```

Use `--runs ...jsonl.progress.jsonl` for an unfinished pilot; only attempted
questions enter averages. Add `--replace` to regenerate existing destinations.
Input files and stored MCP traces are never overwritten by this command.

## CSV outputs

- **`--mcp-calls-csv`**: one row *per attempted MCP gateway call* in A or B,
  with question ID/text, archive, arm, call sequence index, MCP tool name,
  underlying module and function where supplied, success/rejected/error status,
  duration, response size/truncation and bounded redacted arguments. The
  original journal retains all the redacted call arguments and response evidence.
  This records unsuccessful calls as well as successful ones.
- **`--mcp-tool-frequency-csv`**: one row per distinct **tool/function
  signature**. Includes the actual MCP tool name and counts of attempts,
  successful calls, rejections and errors for A and B, as well as number of
  distinct questions in each arm that used that function.
- The **detailed answers** and **per-task performance** CSVs gain MCP tool
  names, counts and JSON summaries in *agent execution order*, including
  zero-call executions. Unattempted runs are left blank, not assigned zero.
- The three-arm **performance** CSV gains `total_mcp_tool_attempts`,
  `mean_mcp_tool_calls_per_attempt`,
  `mean_successful_mcp_calls_per_attempt`, and `distinct_mcp_tools`.
  Web-only C is excluded from the two MCP averages.

### Definitions

**Attempt** means the evaluated agent invoked the MCP gateway. The attempted
count includes requests later rejected by local safety/budget checks and
requests that returned a tool error. **Successful call** means trace
`status == "ok"` and any `response_success` field is not `false`.
The per-question average uses the count of *attempted questions in that arm*,
not the count of completed or correct answers. A response with no returned
archive rows can therefore still be an operationally successful tool call;
this is **not** a claim of scientific correctness.

The underlying MCP service often exposes the generic tool
`astroquery_execute`; the function signature distinguishes examples such as
`astroquery_execute (mast.query_region)` and
`astroquery_execute (simbad.query_object)`. The signature is reporting-only,
not a new MCP tool type.

## Additional PNG and SVG plots

Supplying `--plots-dir` now creates **five** figures (each PNG and SVG):

1. `match_rate` — A/B/C frozen reference matches (unchanged).
2. `mean_runtime` — A/B/C mean wall times (unchanged).
3. `total_tokens` — A/B/C recorded token totals (unchanged).
4. **`mean_mcp_tool_calls`** — per-question attempted and successful call means
   for **A and B only**.
5. **`mcp_tool_calls_by_name`** — grouped A/B attempted-call counts for every
   observed MCP tool/function signature.

If an arm has not yet attempted any questions, its mean is reported as
**N/A**, never 0. If the saved runs contain no MCP calls, the tool-frequency
CSV still has its header and the frequency plot identifies the lack of data.

The 0.6.7.7 code does **not change any agent prompts, MCP calls, model,
input dataset, answer oracle, run journals or resume-manifest conditions**.
The stored five-question GPT-5.2 pilot has six A calls and six B calls
(1.2 calls per question in each arm), with five successful and one rejected
call in each. The 50-question full-run statistics must be calculated from
its own completed journal rather than inferred from that pilot.
