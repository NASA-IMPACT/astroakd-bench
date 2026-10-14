# AstroAKD-Bench documentation

Documentation explains **how to use, interpret and reproduce AstroAKD-Bench**.
Historical machine-readable audit evidence lives under `datasets/evaluation/`, not in `docs/`.
Executable instructions are under [`../instructions/`](../instructions/README.md),
not under `docs/`.

Start with [the repository README](../README.md) for an overview, or the
[current quick-start](benchmark/quickstart.md) for tested commands.

## Current guides (0.6.7.4)

| Topic | Guide |
| --- | --- |
| Installation, configuration, three-arm run and scoring | [Current quick-start](benchmark/quickstart.md) |
| Scope of experiment and what scores mean | [Experimental methods and interpretation](benchmark/experimental_methods.md) |
| MCP endpoint precedence, bearer authentication, connectivity | [MCP configuration — 0.6.7.3](benchmark/mcp_endpoint_auth_0_6_7_3.md) |
| Generate 50 single-value reference-anchored tasks | [Scorable dataset — 0.6.7](benchmark/reference_anchored_scorable_0_6_7.md) |
| Detailed A/B/C CSV, timing, token summaries and plots | [Reporting — 0.6.7.1](benchmark/three_arm_detailed_reporting_0_6_7_1.md) |
| Three-arm experiment and human gold workflow | [Gold review and evaluation — 0.6.6](benchmark/gold_reference_and_three_arm_0_6_6.md) |
| Generate synthetic questions with OpenAI, MCP and web | [Question-generation overview](benchmark/llm_generation_0_6_4.md) |
| Validate references against archives | [Reference validation](benchmark/reference_validation.md) |
| Python interface | [Python API](benchmark/python_api.md) |

## Older implementation / background guides

Versioned guides such as 0.1–0.6.6 document the feature as it was implemented,
not necessarily the **current** CLI defaults, paths or science qualifications.
Use the quick-start above as the authority for current commands. These include:
[local MCP connection](benchmark/local_mcp_connection.md),
[synthetic query generation](benchmark/synthetic_query_generation.md),
[diversity auditing](benchmark/query_diversity_0_6_3.md),
[offline record/replay](benchmark/replay_and_release.md),
[legacy technical scoring](benchmark/evaluation_and_scoring.md),
[ADS and Gold task families](benchmark/gold_benchmark_dataset_and_ads.md), and
[historical README snapshot](history/README_0_6_7_3.md).

For release-by-release changes and migration decisions, use
[CHANGELOG.md](../CHANGELOG.md).

## Documentation versus instructions

- [`instructions/astroakd/AstroAKD_Instruction.md`](../instructions/astroakd/AstroAKD_Instruction.md) is the **evaluated AstroAKD agent's** specialist prompt, used only by arm B.
- [`instructions/astroakd_bench/llm_generation_instructions_v1.md`](../instructions/astroakd_bench/llm_generation_instructions_v1.md) guides **synthetic question generation**. It is never supplied to the evaluated agent.
- The 50-task reference answer oracle under `datasets/gold/` is **hidden from the agent** and only read by offline scoring.
- Both instruction contents are preserved byte-for-byte from 0.6.7.3 so frozen benchmark hashes remain valid.
