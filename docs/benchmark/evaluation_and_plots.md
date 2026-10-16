# Run and report the A/B/C benchmark

Run the three-agent experiment on one saved question dataset. Reference evidence and gold answers are hidden from the evaluated agents.

```bash
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --limit 5

uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --resume
```

The run journal is under `datasets/agent/`. The three arms are **A: MCP only**, **B: MCP plus the frozen AstroAKD specialist instruction**, **C: Web only**. The complete 100-question experiment has up to 300 question/arm results. Resume the same configuration to preserve comparisons.

## Offline reports and figures

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100 --output-dir datasets
```

`run-benchmark` **does not create plots**; it writes the A/B/C run journal under `datasets/agent/`. Run **`agent-report` afterwards** (or during an unfinished experiment for provisional figures). It reads saved runs offline without new OpenAI or MCP calls. Use `--replace` to regenerate existing report files, not the run journal:

```bash
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100 --output-dir datasets --replace
```

The main A/B/C figures are saved in **`datasets/reports/astroakd_100/agents/`**:

| Figure | Meaning | Comparison with the earlier GPT-5.2 plots |
| --- | --- | --- |
| `mean_runtime.png` / `.svg` | Mean seconds per *recorded* agent run, by arm | Comparable to historical `mean_runtime.png`, subject to dataset/run-count differences |
| `total_tokens.png` / `.svg` | Sum of recorded token usage, by arm | Comparable to historical `total_tokens.png` only when run coverage is considered |
| `completed_runs.png` / `.svg` | Number of completed runs | Operational completion, **not** matching/science accuracy |
| `mean_mcp_events.png` / `.svg` | Mean MCP tool events per run | Additional operational comparison |
| `web_search_calls.png` / `.svg` | Total web searches by arm | Additional operational comparison |

CSV output includes `arm_operational_summary.csv`, `per_task_operational.csv`, and `abc_answers.csv` (retains answers). A partial run is summarized as partial; do not compare total tokens between arms without checking their recorded run counts.

**Why there is no `match_rate.png`:** the earlier 50-question figure used a frozen, single-field reference-snapshot comparison. The new 100-question mixed dataset contains multi-row archive responses and 20 literature/multi-archive questions without fully reviewed gold answers. `agent-report` intentionally does **not** compute accuracy or a match rate from unreviewed evidence. Producing a scientifically meaningful match-rate figure requires a separately reviewed oracle, documented comparison rules, and a scorable denominator. Do not rename `completed_runs.png` as match rate. For original frozen single-field experiments, the detailed `score-scorable` command can generate `match_rate.png` when provided its properly qualified oracle and agent runs.

For reference-side **archive completeness and response-time figures**, use the separate offline command documented in [Reference collection and scientific review](references_and_review.md).

**Interpretation:** Successful agent execution or agreement with an unreviewed reference snapshot is not scientific accuracy. Report verified correctness only with a separate reviewed gold oracle and transparent denominators. Keep paper claims about the historical 50-question result separate from any new 100-question run.
