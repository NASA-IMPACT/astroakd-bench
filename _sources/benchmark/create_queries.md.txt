# Create synthetic astronomical questions

The short command is `create-queries`:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 \
  --count 100 \
  --output-dir datasets \
  --require-ads \
  --with-reference-answers
```

`--name` is the filename prefix; `--count` controls the number of questions (1–100 with the built-in curated target pool); `--output-dir` is the **study root**, not a JSONL filename. Default seed is `20261018`; you can override it with `--seed 42`.

The balanced 100-question set has 60 single-archive, 20 coordinate-driven, 8 literature/ADS, and 12 multi-archive questions. For other counts, the mixture scales. For custom quotas use `--mix archive_driven=60,coordinate_driven=20,literature_driven=8,multi_archive=12` with matching `--count`.

`--require-ads` checks ADS authentication and probes **the actual planned literature queries**, not only a generic authentication bibcode. It tries conservative target-based query formulations with compact ADS requests and reports safe HTTP/transport failure categories. Diagnose a particular failure using `uv run python -m benchmark literature-auth --probe --query 'PG 1211+143'`. A generic ADS bibcode success alone cannot qualify general literature search. If ADS research remains unavailable, generation stops **before OpenAI question authoring**. Without `--require-ads`, literature research can use the explicitly labeled web fallback. For server configuration see [ADS and MCP](ads_and_mcp.md).

`--with-reference-answers` collects unreviewed archive observations for the 80 single-call questions **after questions are generated**. Literature and multi-archive questions remain pending multi-step reference collection, not automatically solved. For a bounded pilot add `--reference-limit 5`, then finish with `collect-references --name astroakd_100_v2 --output-dir datasets --resume` without regenerating.

You may omit `--with-reference-answers` to generate questions only. Outputs are created under `datasets/generated/`: `astroakd_100_v2.jsonl`, `.csv`, `_single_call.jsonl`, `_multistep.jsonl`, and `_generation_report.json`. Reference observations, if requested, are under `datasets/validated/`.

Do **not** use `--replace` on a frozen experiment. Use a fresh name or directory for a new independent dataset.

## Keep paid GPT batches after a failure

After every successful OpenAI batch, `create-queries` writes two recoverable artifacts:

- `datasets/generated/<name>.progress.jsonl`: checksum-verified progress journal with validated question batches and completed literature questions
- `datasets/generated/<name>_partial.jsonl`: inspectable but **unvalidated** questions; not a complete benchmark dataset, and never gold

If generation is interrupted, diagnose the failure and repeat your original command **with `--resume`**. The journal verifies your name, count, model, seed, mix, module list, batch size, ADS policy and MCP endpoint before reusing completed batches. A new run without `--resume` refuses to overwrite incomplete work. Do not use `--replace` to recover paid batches.

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 --count 100 --output-dir datasets \
  --require-ads --with-reference-answers --resume
```

The finished JSONL/CSV and generation report are published only after all question families pass their checks. Successful publication removes both checkpoint files. Archive-reference interruptions occur **after** candidate publication; resume those using `collect-references --resume` instead.

## Long reference timeouts in a single command

`create-queries --with-reference-answers` supports exactly the same per-archive timeout, retry, and total deadline policy as `collect-references`:

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 --count 100 --output-dir datasets \
  --require-ads --with-reference-answers \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

For the eight ADS-literature and 12 multi-archive questions (at count 100), standalone multi-step evidence is still pending separate collection; single-call reference observations are not gold.

### Collect references after generation has already completed

If `create-queries` published the question files but did not complete the
reference stage, **do not pay to generate the questions again**. Run:

```bash
uv run python -m benchmark collect-references \
  --name astroakd_100_v2 \
  --output-dir datasets \
  --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

On an interrupted collector, repeat with `--resume`; do not use `--replace`.
When all 80 single-call records already exist with `accepted_nonempty`, no
collection call is needed. Summarize them offline with:

```bash
uv run --with matplotlib python -m benchmark reference-report \
  --name astroakd_100_v2 \
  --output-dir datasets
```

The generated plots are in `datasets/reports/astroakd_100_v2/references/`.
The report's `REVIEW` status refers to outstanding scientific review and
20 multi-step questions, not an error in collecting the 80 single-call
references.

## Reference-aware synthetic questions (0.6.7.11.10)

For a *new* experiment named `astroakd_100_v2`, `create-queries --with-reference-answers` enables reference-aware preselection by default. Before any OpenAI question-authoring batch, the benchmark runs read-only MCP feasibility queries and admits only bounded, nonempty, untruncated candidate results with the requested fields and no null measurements. Gaia and MAST search radii can be narrowed as needed. This is a source-code policy, not merely a prompt request; the generator instruction file also documents it.

```bash
uv run --with openai python -m benchmark create-queries \
  --name astroakd_100_v2 --count 100 --output-dir datasets \
  --require-ads --with-reference-answers --timeout 900 \
  --archive-timeouts mast=900,simbad=180,heasarc=900,gaia=900,vizier=300 \
  --archive-attempts mast=2,simbad=1,heasarc=2,gaia=2,vizier=1 \
  --reference-deadline 2100
```

Default feasibility limits are `--max-reference-rows 20`, `--max-reference-bytes 65536`, and `--max-feasibility-probes 500`. The first two are *maximum complete result* thresholds, not hidden result truncation. If sufficient feasible candidates do not exist, generation fails with an archive-level rejection summary **before GPT calls**; it never changes expected answers to accommodate incomplete archive data. Broader quotas may require expanding curated candidates or adjusting the mix, and live feasibility cannot be promised offline.

After all slots pass, the checksum-protected `datasets/generated/astroakd_100_v2_feasibility_plan.json` records accepted MCP call parameters and precheck hashes and is reused by `--resume` with the same configuration. The actual reference collection is independent and occurs after task publication. Ordinary ADS-literature and multi-archive tasks remain on their distinct multi-step evidence track; neither this precheck nor `--with-reference-answers` establishes their final reference answers. To reproduce A/B/C results exactly, reuse the saved JSONL and do not modify the original `astroakd_100` study.

## Durable archive feasibility progress and fallback (0.6.7.11.10)

The precheck is now **checkpointed per MCP call** rather than written only
after 92 accepted slots. Accepted candidates, rejected attempts, and the
configurations are saved under
`datasets/generated/<name>_feasibility_progress.json`. If a module (especially
MAST) has only truncated or oversized answers, the selector can use another
archive, preserves the actual module balance, and never accepts incomplete
references. Smaller cone searches are prioritized; larger cones are skipped
when the smallest cone is already truncated or oversized.

After an interrupted or probe-budget-limited run, rerun the same
`create-queries` command with `--resume` to reuse prior probe outcomes.
You may increase `--max-feasibility-probes` when resuming without losing
previously accepted or rejected calls. Other feasibility settings remain
checksum-protected. **Do not use `--replace` to recover an unfinished run.**
The final dataset and reference CSV are published only after all tasks pass.
For version 0.6.7.11.9 failures, previous unsaved archive probes are
not reconstructible from console logs.
