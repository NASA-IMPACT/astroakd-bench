# 0.6.6 — Gold references and three-arm AstroAKD evaluation

**Projects are distinct:** AstroAKD-Bench creates and scores tests. **AstroAKD** is the data-search agent being evaluated. `instructions/astroakd/AstroAKD_Instruction.md` is an **AstroAKD agent instruction**, not the benchmark's synthetic-question generator prompt (`instructions/astroakd_bench/llm_generation_instructions_v1.md`).

## Source data and acceptance state

The supplied 0.6.5 `gold_mixed_065.jsonl` has **50** tasks (32 archive, 10 coordinate, 8 literature). The archive/coordinate subset contains **42** executable MCP calls. The uploaded reference validation journal contains **5 accepted_nonempty** tasks; the rest have not yet been queried. These five are *structural reference observations*, not verified scientific answers.

Preserved checksums (do not recompute by reformatting JSONL):

| Dataset | SHA-256 |
|---|---|
| Mixed 50 | `139e895c63a0c0834f282fe4bf0622470f3a5ff7760343384f690ae567ded9eb` |
| Single-call 42 | `f348f14a23a0ae2975894954503fa1d86db11a00d9058ee0f694e7d537c5d08e` |
| Literature 8 | `dc23191bf95157069618a041860a45741f9681d77fce4dd59b274f621d593d2a` |

### Continue validation without discarding the five successes

From repository root with Astroquery MCP server running:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --resume --attempts 1 --timeout 180 --delay 2 \
  --output datasets/validated/gold_mixed_065_ref_42.jsonl \
  --report datasets/validated/gold_mixed_065_ref_42_report.json \
  --json-format pretty
```

Use the exact **same** input/output/report names and keep the `.progress.jsonl` and `.manifest.json`. The journal cannot be safely resumed against a different dataset hash. The original five-task pilot used no CSV/pretty exports; optional exports can be requested separately when generating new views.

### Build a gold-review worksheet (works immediately with the partial journal)

```bash
uv run python -m benchmark gold-draft \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --references datasets/validated/gold_mixed_065_ref_42.jsonl.progress.jsonl \
  --reference-tasks datasets/generated/gold_mixed_065_single_call_42.jsonl \
  --output datasets/gold/gold_mixed_review.jsonl \
  --report datasets/gold/gold_mixed_review_report.json \
  --json-format pretty
```

After validation completes, change `--references` to the finalized `gold_mixed_065_ref_42.jsonl` and use new gold-draft output paths or `--replace`. **Never** promote raw `response` rows, OpenAI web citations, or structural acceptance to approved gold automatically. Every generated review entry starts with `gold_status=pending`, `question_review=pending`, `gold=null`.

## Human review and freeze

Each review entry contains the original question, task type, target, frozen task SHA-256, validation disposition/counts and `truncated` flag. After checking a question for ambiguity and verifying its scientific answer independently, edit these fields:

```json
{
  "question_review": "approved",
  "gold_status": "verified",
  "gold": {
    "kind": "set",
    "values": ["EXAMPLE-OBS-ID-1", "EXAMPLE-OBS-ID-2"],
    "complete_scope_review": true
  },
  "sources": [
    {"uri": "https://archive.example.org/obs", "description": "Observation catalogue and query constraints checked"},
    {"uri": "https://publisher.example.net/paper", "description": "Independent paper or instrument observation log"}
  ],
  "reviewer": "reviewer-id",
  "review_notes": "Compared the complete requested scope, not just a truncated preview."
}
```

*Example identifiers and domains above are placeholders; never enter them as real evidence.*

Gold kinds: `set` (IDs/sets; exact normalized string match and F1), `text` (complete normalized answer tokens; exact), `numeric` (exact unit, one scalar and `absolute_tolerance`). For numerical answers, also specify `unit`, for example `{"kind":"numeric","values":[12.345],"unit":"deg","absolute_tolerance":0.001}`. Compound astrometry (RA+Dec) may need an explicit agreed scalar-per-coordinate rubric or a list of identifiers; do not improvise concatenated numeric fields. Literature answers need paper identity/bibcode PLUS observation evidence as required by each question. If evidence is ambiguous or the task asks for impossible completeness, use `question_review=rejected`, do not invent a value. A truncated table requires independently established completeness and explicit review notes to approve a set.

The acceptance contract requires an attributed human reviewer and at least two cited **distinct hosts**. This is an audit check, not proof of scientifically independent sources. An astronomer must assess actual independence, coordinate frames, observation filters, and unit conventions. A textual source or LLM web snippet alone is insufficient to verify archive observation IDs.

```bash
uv run python -m benchmark gold-finalize \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --reviewed datasets/gold/gold_mixed_review.jsonl \
  --output datasets/gold/gold_mixed_frozen.jsonl \
  --report datasets/gold/gold_mixed_frozen_report.json
```

By default this fails if fewer than all 50 tasks are approved. `--allow-partial` creates a **PARTIAL** gold snapshot; unapproved tasks remain **unscorable**, never wrong. Keep source files immutable after freezing, record output SHA-256 in papers/results.

## Three comparable AstroAKD agent modes

Same **input questions** and selected OpenAI model; different tools and system instructions:

| Arm | Name | MCP tools | AstroAKD agent instruction | OpenAI web search |
|---|---|---|---|---|
| A | `mcp_only` | Yes, bounded read-only | No; minimal operational/safety formatting only | No |
| B | `mcp_instruction` | Same as A | **Yes**, contents of `instructions/astroakd/AstroAKD_Instruction.md` | No |
| C | `web_only` | None | No; minimal operational/safety formatting only | Yes, hosted `web_search` |

**Do not** give benchmark synthetic generation instructions to any arm. **Do not** give the reference journal or approved gold values to agents. A and B get function discovery, allowed `astroquery_execute`, plus read-only ADS `ads_query_compact`, `ads_get_paper` and `simbad_query_bibobj` when advertised by MCP. The server must already see `API_DEV_KEY` to use authenticated ADS; the runner will not disclose or bypass this. Web arm has **no MCP connection** and a required web-search tool call. If the MCP server cannot serve ADS, the MCP arms must handle that limitation without silently switching to web search; changing tool access would invalidate the A/B/C comparison.

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-4.1-mini --limit 5 \
  --max-turns 8 --max-calls 12 --task-timeout 600 \
  --output datasets/agent/astroakd_three_arm_runs.jsonl \
  --report datasets/agent/astroakd_three_arm_report.json
```

For full evaluation, repeat exactly the command without `--limit`, adding `--resume`. Each `(task_id,arm)` is journaled and resumed independently. Do **not** use `--replace` when resuming. Completion yields 150 run records (50 tasks × 3 arms); a pilot of five yields 15 journal records. Keep output, model, instruction file, and budgets constant across runs. Each run includes answer text, structured extracted answer values when parseable, citations, tool traces, duration, and token counts.

### Offline scientific scoring

Only after human gold review:

```bash
uv run python -m benchmark score-three-arm \
  --tasks datasets/generated/gold_mixed_065.jsonl \
  --gold datasets/gold/gold_mixed_frozen.jsonl \
  --runs datasets/agent/astroakd_three_arm_runs.jsonl \
  --output datasets/evaluation/astroakd_three_arm_scores.jsonl \
  --report datasets/evaluation/astroakd_three_arm_report.json --json-format pretty
```

For a partial pilot, `--runs` can point to the `.progress.jsonl` file. `gold_status=pending/rejected` yields `UNSCORABLE_NO_GOLD`. Plain-text/unparseable answers yield `REVIEW_UNSTRUCTURED`, not a numeric wrong score. Numeric units must agree; sets receive F1; text answers use strict normalized equality. Report both per-arm coverage and **paired** scores on the same questions. Failures and abstentions are separate from unsupported claims. A single answer-level F1 is not a complete astrophysical quality metric; inspect claims, citations, truncation, and tool traces. Usage data are recorded, but financial API costs are not fabricated from stale model price tables.

## Remaining scientific qualification work

1. Complete the **37 remaining single-call** archive requests with resume. Inspect `returned_rows`, `total_rows` and truncation; MAST only truncates at MCP level for `max_rows`.
2. Independently verify the **8 literature-driven** tasks: ADS paper metadata, SIMBAD bibcode object resolution, actual archive observation IDs and instrument settings. The old 0.6.5 single-call validator deliberately excludes them.
3. Review ambiguous generated prompts, such as the unspecified tidal disruption transient (`ASTROAKD-MIX-00008`), catalog typo `chanmastar` (`ASTROAKD-MIX-00020`), and any question asking for a complete set when only a bounded catalog page was returned. Fix questionable tasks via a **new versioned dataset**, rerun affected references, and re-freeze hashes; never edit a frozen candidate silently.
4. Qualify live A/B/C on a five-task pilot, then all 50. For literature tasks, verify that the server actually advertises and successfully executes ADS methods. Confirm backend tool parity for A and B and absence of MCP calls in C.
5. Human-verify machine-scored outcomes before reporting scientific accuracy, including synonymous names, coordinate precision, observation time filtering and bibliographic citations.

**Disposition:** 0.6.6 source tests and offline gold/runner scaffolding passed. Real complete gold verification and three-arm science evaluation are **not yet accepted**.
