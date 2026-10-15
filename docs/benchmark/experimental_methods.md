# Experiment design and interpretation (current through 0.6.7.4)

## Scope

AstroAKD-Bench is an independent Python **benchmarking application**;
AstroAKD is the astronomy data-discovery **agent under test**; and
NASA IMPACT's `astroquery-mcp` is an **external MCP service**. The projects
have distinct responsibilities.

The current scorable benchmark has **50 one-field questions** based on a frozen
42-task structural MCP reference collection from SIMBAD, MAST, HEASARC, Gaia
and VizieR. Some questions draw different fields from the same archive response;
50 questions do **not** imply 50 statistically independent sky targets.
The earlier 50-question mixed benchmark (32 archive/10 coordinate/8 literature)
is preserved separately and is not interchangeable with the scorable set.

## Controlled three-arm comparison

| Arm | Short label | Allowed external tools | Specialist AstroAKD instruction |
| --- | --- | --- | --- |
| A | `mcp_only` | Compatible Astroquery MCP | No |
| B | `mcp_instruction` | Same MCP tools as A | **Yes**, `instructions/astroakd/AstroAKD_Instruction.md` |
| C | `web_only` | Hosted OpenAI web search only | No |

All use **GPT-5.2** and identical question text. The hidden source-derived
reference oracle is not provided to any arm. The generation-time question-authoring
prompt `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` is
**not** an agent instruction, and is **not** used in A, B or C.

Run completion, reference match, tool success, latency and token usage are
separate measurements. The scorer retains incorrect responses, abstentions,
SDK failures and free-form outputs verbatim in report columns.

## Scientific interpretation and limitations

- **Snapshot-reference match** compares a parsed answer with a frozen value and
  its field-specific tolerance. It is not a verified astronomical-truth metric.
- **Scientific gold** requires independent review of exact archive row,
  identifiers, units and provenance; currently the 50-field oracle is
  `reference_anchored_unreviewed`.
- **Completion rate** means an attempt was recorded as completed, not that it
  solved the question.
- **Coverage** is how many of 50 questions were attempted per arm. An attempted
  five-task match of 100% does not establish 100% over all 50.
- **Runtime** is the measured wall time of attempted runs. **Tokens** are
  provider-reported usage and may not map directly to compute cost or archive
  network traffic. Compare arms on the **same question set**.
- The agent system prompt, provider model and endpoint can change results.
  Keep the three-arm journal's manifest-bound settings consistent. Do not
  mix runs from different server URLs into a single resume journal.
- Live public archive results can evolve. Retain dataset/oracle/run hashes
  with any publication, together with source provenance and the frozen version.
- The initial 5-question GPT-5.2 pilot found snapshot matches **5/5** for A,
  **5/5** for B and **1/5** for C; this does **not** establish a statistically
  reliable benefit from adding specialist instructions, nor a general
  MCP-versus-web performance claim over all scientific tasks.

## Reports and implementation details

See [quick-start](quickstart.md),
[reference-anchored answer construction](reference_anchored_scorable_0_6_7.md),
[detailed CSV/plot scoring](three_arm_detailed_reporting_0_6_7_1.md),
[original scientific gold review process](gold_reference_and_three_arm_0_6_6.md),
and [release history](../../CHANGELOG.md).


### Live reference collection at generation time (0.6.7.9)

Use `generate --with-reference-answers` for new single-call MCP candidates to execute the real archive query immediately after question writing. The companion validation JSONL stores full returned tables and provenance; its CSV includes observed expected-column values marked unreviewed. For existing generated questions, use `validate` directly. Keep reference collection separate from scientific gold review. See [the 100-query workflow](new_100_query_workflow.md).
