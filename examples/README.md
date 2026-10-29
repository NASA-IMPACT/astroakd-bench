# AstroAKD-Bench examples

This directory contains **real, frozen example outputs** from the [`astroakd_100_v2`](astroakd_100_v2/) study. It illustrates question generation, independent archive-reference collection, and comparisons of three GPT-5.2 agent configurations using the same 100 questions.

The published example is a **curated subset**, not the full raw benchmark archive. You can inspect its 100 questions and reference answers without configuring OpenAI or running the MCP server.

## Start with the question and reference CSV

| Example file | Contents |
| --- | --- |
| [`astroakd_100_v2_questions_and_references.csv`](astroakd_100_v2/astroakd_100_v2_questions_and_references.csv) | **Recommended:** all 100 questions, their query specifications, available structured reference answers, and explicit reference status in one table. |
| [`astroakd_100_v2.csv`](astroakd_100_v2/astroakd_100_v2.csv) | Original 100 generated questions; **does not** contain the retrieved answers. |
| [`astroakd_100_v2_references.csv`](astroakd_100_v2/astroakd_100_v2_references.csv) | Independently collected single-call reference evidence for 80 questions. |
| [`astroakd_100_v2_multistep_references.csv`](astroakd_100_v2/astroakd_100_v2_multistep_references.csv) | Multi-step reference status for 20 questions: 12 complete multi-archive and 8 pending literature-driven cases. |
| [`automated_scores_per_question.csv`](astroakd_100_v2/automated_scores_per_question.csv) | Per-question A/B/C classifications and exclusion reasons. |
| [`automated_scoring_summary.json`](astroakd_100_v2/automated_scoring_summary.json) | Exact scoring denominators, policy, source fingerprints, and breakdowns. |
| [`operational_summary.csv`](astroakd_100_v2/operational_summary.csv) | Original baseline execution completion, timing, and tokens. |

Use `task_id` to associate rows across files. Structured fields are represented as JSON text in CSV cells. The joined table has **92 populated reference answers**, while the eight literature tasks are clearly marked as not independently established. Do not interpret those eight as incorrect agent answers.

Additional examples (a ten-question sample, 30 A/B/C answers, one complete two-archive reference, supporting SVG figures and checksums) are described in the [study-specific README](astroakd_100_v2/README.md).

## Results of the saved benchmark

The strict matching denominator is **92/100 questions**: 80 single-call references plus 12 completed multi-archive references. The remaining 8 literature tasks are excluded pending independent paper–observation evidence.

| Metric | A: MCP only | B: MCP + AstroAKD | C: Web only |
| --- | ---: | ---: | ---: |
| Strict reference matches | 87 / 92 | 88 / 92 | 13 / 92 |
| Automatic archive-reference agreement | **94.57%** | **95.65%** | **14.13%** |
| Partially correct | 4 | 4 | 2 |
| Original run completion | 98 / 100 | 100 / 100 | 100 / 100 |

![Strict archive-reference agreement for 92 evaluable questions](astroakd_100_v2/figures/match_rate.png)

*Only fully correct matches count in the strict agreement percentage. This is automatic agreement with saved Astroquery MCP reference data, **not independently adjudicated scientific accuracy**. The one-question A–B difference should not be interpreted as proof of better performance; some answer-format classifications are under review.*

### Agreement by question type

![Reference agreement by question type](astroakd_100_v2/figures/accuracy_by_question_type.png)

### Original execution time

![Original mean execution time by configuration](astroakd_100_v2/figures/mean_runtime.png)

Timing and token plots come from the **original common-budget runs**, not from later increased-budget diagnostic retries. The figures correspond to the saved scoring reports; they are not recalculated or improved here.

For the executable benchmark and instructions, see the [repository README](../README.md), [online documentation](https://danehkar.github.io/astroakd-bench/) and the [full file list](astroakd_100_v2/README.md).
