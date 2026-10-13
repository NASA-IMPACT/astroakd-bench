# AstroAKD-Bench 0.2.0 HEASARC variadic-signature qualification fix

## Root cause

`astroquery-mcp` introspects Python functions and sets `required = not has_default` without transmitting the parameter kind. Consequently, HEASARC `query_region(..., **kwargs)` is advertised as an unsupported required argument called `kwargs`. The generator correctly refused to invent such an argument but could not produce the full five-service candidate dataset.

## Change

`benchmark/generator.py` now identifies the *documented* variadic `kwargs` for **only** `heasarc.query_region` and ignores it during the unexpected-required and unknown-optionality gates. It still preserves the original metadata in the schema fingerprint and rejects any other required unsupported parameter. The fix leaves the MCP server and all existing discovery and candidate generation semantics unchanged. No OpenAI or other LLM API is used.

## Local acceptance

From the repository root with the MCP server running on `127.0.0.1:8000`:

```bash
uv run python -m unittest discover -s benchmark/tests -v
uv run python -m benchmark generate --count 50 --seed 42 \
  --modules simbad,mast,heasarc,gaia,vizier --timeout 180 \
  --output benchmark/datasets/generated/synthetic_queries.jsonl \
  --report benchmark/datasets/generated/generation_report.json
```

The dataset was not published during the prior failed generation, so `--replace` should not be necessary. If a successful dataset already exists, explicitly use `--replace`.

Expect `status: PASS`, 50 generated tasks, 10 per service, `archive_queries_executed: 0`, and `validation_status: candidate_unvalidated`. Rerun the same generation with `--replace` and compare `dataset_sha256` to establish same-host repeatability. Live laptop qualification is still required.
