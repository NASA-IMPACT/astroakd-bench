# Installing AstroAKD-Bench 0.4.0 in astroquery-mcp

**Preferred: apply the single Git upgrade patch** from the repository root:

```bash
git apply --check astroakd_bench_0_3_0_to_0_4_0.patch
git apply astroakd_bench_0_3_0_to_0_4_0.patch
uv run python -m unittest discover -s benchmark/tests -v
```

The patch assumes the accepted 0.3.0 benchmark and its previous documentation
update have been applied. It includes a small **additive section** to the
pre-existing root `README.md`, and creates the root `CHANGELOG.md`. It does not
replace or delete the existing MCP README content.

**ZIP alternative:** The ZIP contains the new `benchmark/` and `docs/benchmark/`
files, root `CHANGELOG.md`, and `root_readme_addition.patch`. Extract into the
repository, then apply the README section patch from the repository root:

```bash
git apply --check root_readme_addition.patch
git apply root_readme_addition.patch
```

Use either the **full upgrade patch** OR the **ZIP extraction plus README patch**,
not both. The package intentionally does not include a replacement root
`README.md`, because overwriting it would destroy pre-existing MCP server
documentation.

Do NOT replace your completed validated dataset, generated candidate dataset,
`server.py`, `executor.py`, `pyproject.toml`, or `uv.lock`.

Run a no-LLM local connectivity/harness check first:

```bash
uv run python -m benchmark run --agent echo --strict-accepted-020 --limit 5
```

This writes to `benchmark/datasets/agent/` and requires your running local HTTP
MCP server. It does not test a real agent. See
`docs/benchmark/agent_execution.md` for OpenAI and external AstroAKD adapter
examples, traces, resume behavior, and limits.
