# Getting started

AstroAKD-Bench evaluates astronomical archive-search agents. The benchmark **creates questions** and compares three agent configurations using a separately running [Astroquery MCP server](https://github.com/NASA-IMPACT/astroquery-mcp).

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- An `OPENAI_API_KEY` in the environment when generating or running the agents
- An Astroquery MCP server serving `http://127.0.0.1:8000/mcp` (or set `ASTROAKD_MCP_URL`)
- Working ADS credentials **on the MCP server** if using `--require-ads`

Install project dependencies in the source directory using `uv sync`. Start the external MCP service from its own repository, for example:

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

That command belongs to the **astroquery-mcp server directory**, not the benchmark directory.

## Recommended 100-question workflow

In the AstroAKD-Bench repository root:

```bash
# Check ADS authentication and a real small ADS query before spending OpenAI credits
uv run python -m benchmark literature-auth --probe

# Create a mixed 100-question experiment and collect eligible reference evidence
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers

# Offline reference quality report
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100 --output-dir datasets

# Test five questions before running all three agents on 100 questions
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --limit 5
uv run --with openai python -m benchmark run-benchmark \
  --name astroakd_100 --output-dir datasets --resume

# Offline A/B/C plots and CSVs
uv run --with matplotlib python -m benchmark agent-report \
  --name astroakd_100 --output-dir datasets
```

The five named commands create their needed output subdirectories automatically.
`--seed` is optional, defaulting to `20261018`, and does not guarantee identical responses from GPT-5.2. Preserve the generated JSONL for reproducibility.

## What is measured?

A is MCP only, B is MCP with the AstroAKD specialist instruction, and C is Web only. One hundred questions create up to 300 agent runs. **Completion, time and tool metrics are not scientific correctness.** Scientific accuracy requires independently verified gold answers.

Continue with [question generation](create_queries.md), [references](references_and_review.md), and [evaluation](evaluation_and_plots.md).

Frozen prompts: `instructions/astroakd/AstroAKD_Instruction.md` (arm B) and `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` (generation only).

To build the HTML documentation from the repository root: `make -C docs/sphinx html`.
