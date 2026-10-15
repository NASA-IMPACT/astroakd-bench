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

Outputs appear in `datasets/reports/astroakd_100/agents/`: per-arm and per-task CSV summaries and PNG/SVG plots of run completion, runtime, total tokens, MCP tool calls, and web searches. This command is offline; it can also summarize partial journals. Use `--replace` when intentionally regenerating report outputs.

**Interpretation:** Successful agent execution or agreement with an unreviewed reference snapshot is not scientific accuracy. Report verified correctness only with a separate reviewed gold oracle and transparent denominators. Keep paper claims about the historical 50-question result separate from any new 100-question run.
