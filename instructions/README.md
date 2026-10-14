# Instructions consumed by AstroAKD and AstroAKD-Bench

The files under `instructions/` are **runtime prompts/policies**, not how-to guides.

| Directory | Project | What it controls | Used by |
| --- | --- | --- | --- |
| [`astroakd/`](astroakd/AstroAKD_Instruction.md) | **AstroAKD** (agent under test) | Specialist astronomy/archival agent behavior | Three-arm **B** (`mcp_instruction`), passed explicitly to `--agent-instruction` |
| [`astroakd_bench/`](astroakd_bench/AstroAKD-Bench_Instruction.md) | **AstroAKD-Bench** | How to author synthetic evaluation questions | `generate` OpenAI/hybrid paths when `--instructions` is enabled (default) |

**Never** feed question-generation instructions to the agent being evaluated, and
never feed the hidden reference oracle or gold answers to any agent. Arms A and C
must not receive the specialist AstroAKD instruction.

Paths used from the repository root:

```bash
uv run --with openai python -m benchmark run-three-arm \
  --tasks datasets/generated/scorable_50.jsonl \
  --agent-instruction instructions/astroakd/AstroAKD_Instruction.md \
  --model gpt-5.2 --output datasets/agent/scorable_50_gpt52_runs.jsonl \
  --report datasets/agent/scorable_50_gpt52_report.json

uv run --with openai python -m benchmark generate --backend openai \
  --instructions-file instructions/astroakd_bench/AstroAKD-Bench_Instruction.md \
  --count 50 --output datasets/generated/llm_candidates.jsonl \
  --report datasets/generated/llm_candidates_report.json
```

The AstroAKD agent instruction is **byte-identical** to the file in 0.6.7.3
(SHA-256 `c7e9b4b8ffb608f2b380418a2df2d98c98bb6a807b065fff61757c2f1253e4ab`).
Moving it does not change the experiment's instruction content hash; however,
**do not change an active experiment or its endpoint/budgets mid-run**. An existing
resume manifest records hashes and effective MCP URL, not the instruction file path.

The generation instructions are also byte-identical to 0.6.7.3 (SHA-256
`d430cf4d2508f124abee4deb23da44b3aca1618707f6c052fea8ee9deda47acf`).

**Migration from 0.6.7.4:** rename the generation file
`instructions/astroakd_bench/llm_generation_instructions_v1.md` to
`instructions/astroakd_bench/AstroAKD-Bench_Instruction.md`.

**Earlier migration from 0.6.7.3:** replace
`docs/agent/AstroAKD_Instruction.md` with
`instructions/astroakd/AstroAKD_Instruction.md` and
`docs/benchmark/llm_generation_instructions_v1.md` with
`instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` in scripts.
Old paths are intentionally no longer maintained under `docs/`.

See [documentation index](../docs/index.md) for human-facing guidance.
