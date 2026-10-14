# 0.6.5 — Generate a native Gold-inspired mixed dataset

**AstroAKD-Bench generates every task.** The earlier `astroakd_gold50_release/tools/build_gold50.py` was an offline external builder, not native live generation. Do not use it for benchmark-scored new generation. This implementation uses the repository's existing `generate` entrypoint, OpenAI, Astroquery MCP signature discovery, MCP ADS research when available, and web-search fallback otherwise.

## Run 50 new questions (default MCP + Gold-derived instructions)

Start the separate Astroquery MCP server with `API_DEV_KEY` in the *server launch environment* if ADS is desired. Set `OPENAI_API_KEY` in the benchmark client's environment. The bench never reads, prints, or sends `API_DEV_KEY` to OpenAI. Verify with `literature-auth` if desired.

```bash
uv run --with openai python -m benchmark generate \
  --backend openai --instructions --mcp --model gpt-4.1-mini \
  --count 50 --seed 123 --task-mix gold50 \
  --modules simbad,mast,heasarc,gaia,vizier \
  --uniqueness archive-target --question-style answer-oriented \
  --output datasets/generated/gold_mixed_065.jsonl \
  --csv-output datasets/generated/gold_mixed_065.csv \
  --pretty-output datasets/generated/gold_mixed_065_pretty.json \
  --single-call-output datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --literature-output datasets/generated/gold_mixed_065_literature_8.jsonl \
  --report datasets/generated/gold_mixed_065_report.json \
  --json-format pretty
```

The configured mix is **32 archive-driven, 10 coordinate-driven, 8 literature-driven**. Ordinary 42 tasks retain prebound executable MCP calls, while the eight literature research tasks have `reference_call: null` and require multistep agent/answer validation. The mixed JSONL has 50 compact records; pretty JSON and CSV are inspection views. Replacing `--task-mix gold50` with `--task-mix archive_driven=30,coordinate_driven=12,literature_driven=8` is supported; the three counts must sum to `--count`. At most eight built-in literature research anchors are supplied; extending this requires deliberate new research anchors.

Each literature candidate is generated *now*, not loaded from a prior offline file. `research_literature` checks MCP server ADS auth and attempts `ads_query_compact`; if ADS fails or is unauthenticated, it uses OpenAI Responses `web_search`, and then OpenAI authors the question conditioned on evidence. The report includes `research_provider_counts`, literature question-authorship fallback counts, and source metadata; bibliography is unverified. One OpenAI authoring request per literature task is expected; extra web search calls occur when ADS is unavailable.

## Without MCP or without instructions

Use `--no-mcp` to route **all research** through OpenAI web search. The non-literature questions then have no executable MCP reference calls; `--single-call-output` should be treated as an *unverified non-literature subset*, not input to `validate`. Use `--no-instructions` to run a controlled prompt ablation; `--instructions-file PATH` selects a custom instruction Markdown file instead. `--backend hybrid` is also supported. The native mixed track requires OpenAI/hybrid rather than template-only mode because literature authoring requires the model.

## Qualification gates and expectations

1. Verify 50 records and reported 32/10/8 mix; no repeated question text, exact MCP call, or archive-target pair.
2. Inspect the eight literature records and their `research_evidence.research_provider`. ADS success is not implied by `ads_authenticated=true` alone.
3. Inspect source links and any `literature_question_author: template_fallback_after_model_error` cases.
4. Validate only the 42 MCP-bound tasks with `benchmark validate` and its journal/resume contract. Never feed the full mixed JSONL to that one-call validator.
5. Evaluate literature questions only after a multistep gold-creation/evidence checking workflow is implemented.

No source has a verified expected answer at generation time. OpenAI question wording is nondeterministic despite a fixed seed; input task selection, output quotas, schema binding, and duplicate checks are deterministic.
