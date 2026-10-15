# Create synthetic astronomical questions

The short command is `create-queries`:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers
```

`--name` is the filename prefix; `--count` controls the number of questions (1–100 with the built-in curated target pool); `--output-dir` is the **study root**, not a JSONL filename. Default seed is `20261018`; you can override it with `--seed 42`.

The balanced 100-question set has 60 single-archive, 20 coordinate-driven, 8 literature/ADS, and 12 multi-archive questions. For other counts, the mixture scales. For custom quotas use `--mix archive_driven=60,coordinate_driven=20,literature_driven=8,multi_archive=12` with matching `--count`.

`--require-ads` first performs a real MCP ADS preflight query; if it fails, generation stops **before OpenAI question authoring**. Without `--require-ads`, literature research can use the explicitly labeled web fallback. For server configuration see [ADS and MCP](ads_and_mcp.md).

`--with-reference-answers` collects unreviewed archive observations for the 80 single-call questions **after questions are generated**. Literature and multi-archive questions remain pending multi-step reference collection, not automatically solved. For a bounded pilot add `--reference-limit 5`, then finish with `collect-references --name astroakd_100 --output-dir datasets --resume` without regenerating.

You may omit `--with-reference-answers` to generate questions only. Outputs are created under `datasets/generated/`: `astroakd_100.jsonl`, `.csv`, `_single_call.jsonl`, `_multistep.jsonl`, and `_generation_report.json`. Reference observations, if requested, are under `datasets/validated/`.

Do **not** use `--replace` on a frozen experiment. Use a fresh name or directory for a new independent dataset.
