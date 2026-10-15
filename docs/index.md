# AstroAKD-Bench documentation

Documentation explains **how to use, interpret and reproduce AstroAKD-Bench**.
Historical machine-readable audit evidence is shipped in a separate versioned dataset archive, not inside the source release or `docs/`. The active `datasets/` directory is a generated-output workspace.
Executable instructions are under the repository `instructions/` directory,
not under `docs/`.

Start with the repository `README.md` for an overview, or the
[current quick-start](benchmark/quickstart.md) for tested commands.

## Current guides (0.6.7.11.3)

| Topic | Guide |
| --- | --- |
| 0.6.7.11.3 mixed generation, optional single-call references and offline plots | [Easy mixed 100 — 0.6.7.11.3](benchmark/easy_mixed_100_workflow_0_6_7_11.md) |
| Dataset archive layout, SHA-256, reproducibility | [Historical dataset archive — 0.6.7.11.3](benchmark/dataset_layout_historical_archive_0_6_7_11_3.md) |
| 0.6.7.10 archive budgets, consolidated answers and gold review | [Scientific review — 0.6.7.10](benchmark/archive_policy_scientific_review_0_6_7_10.md) |
| Installation, configuration, three-arm run and scoring | [Current quick-start](benchmark/quickstart.md) |
| Clone and run local MCP; generate/validate/evaluate 100 new questions | [New 100-query workflow](benchmark/new_100_query_workflow.md) |
| Scope of experiment and what scores mean | [Experimental methods and interpretation](benchmark/experimental_methods.md) |
| MCP endpoint precedence, bearer authentication, connectivity | [MCP configuration — 0.6.7.3](benchmark/mcp_endpoint_auth_0_6_7_3.md) |
| Generate 50 single-value reference-anchored tasks | [Scorable dataset — 0.6.7](benchmark/reference_anchored_scorable_0_6_7.md) |
| Detailed A/B/C CSV, timing, token summaries and plots | [Reporting — 0.6.7.1](benchmark/three_arm_detailed_reporting_0_6_7_1.md) |
| Paired 50-query efficiency, mismatch review and combined A/B/C CSV exports | [Paired analysis — 0.6.7.8](benchmark/paired_analysis_0_6_7_8.md) |
| Individual MCP calls, per-function A/B frequencies and two extra plots | [MCP tool-call reporting — 0.6.7.7](benchmark/mcp_tool_call_reporting_0_6_7_7.md) |
| Three-arm experiment and human gold workflow | [Gold review and evaluation — 0.6.6](benchmark/gold_reference_and_three_arm_0_6_6.md) |
| Generate synthetic questions with OpenAI, MCP and web | [Question-generation overview](benchmark/llm_generation_0_6_4.md) |
| Validate references against archives | [Reference validation](benchmark/reference_validation.md) |
| Python interface | [Python API](benchmark/python_api.md) |
| Build HTML with Sphinx/MyST | [HTML documentation build](benchmark/documentation_build.md) |

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
the repository `CHANGELOG.md`.

## Documentation versus instructions

- `instructions/astroakd/AstroAKD_Instruction.md` is the **evaluated AstroAKD agent's** specialist prompt, used only by arm B.
- `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` guides **synthetic question generation**. It is never supplied to the evaluated agent.
- The 50-task reference answer oracle in `benchmark/tests/fixtures/legacy/gold/` (and the external historical archive) is **hidden from the agent** and only read by offline scoring.
- Both instruction contents are preserved byte-for-byte from 0.6.7.3 so frozen benchmark hashes remain valid.

## Browse the HTML documentation

```{toctree}
:maxdepth: 2
:caption: Current guides

benchmark/easy_mixed_100_workflow_0_6_7_11
benchmark/dataset_layout_historical_archive_0_6_7_11_3
benchmark/quickstart
benchmark/new_100_query_workflow
benchmark/archive_policy_scientific_review_0_6_7_10
benchmark/experimental_methods
benchmark/mcp_endpoint_auth_0_6_7_3
benchmark/reference_anchored_scorable_0_6_7
benchmark/three_arm_detailed_reporting_0_6_7_1
benchmark/mcp_tool_call_reporting_0_6_7_7
benchmark/paired_analysis_0_6_7_8
benchmark/python_api
benchmark/documentation_build
```

```{toctree}
:maxdepth: 1
:caption: Reference and history

benchmark/gold_reference_and_three_arm_0_6_6
benchmark/llm_generation_0_6_4
benchmark/reference_validation
benchmark/agent_execution
benchmark/answer_inspection_and_success_rates_0_6_6_1
benchmark/astroakd_bench
benchmark/evaluation_and_scoring
benchmark/gold_benchmark_dataset_and_ads
benchmark/local_mcp_connection
benchmark/native_gold_mixed_generation_0_6_5
benchmark/query_diversity_0_6_3
benchmark/replay_and_release
benchmark/synthetic_query_generation
history/README_0_6_7_3
```

When browsing HTML, use these navigation trees. Documentation files that
mention earlier versions describe historical behavior; the current quick-start
is the authority for supported commands.
