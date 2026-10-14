# Build HTML documentation with Sphinx

AstroAKD-Bench uses **Sphinx** and **MyST-Parser** to publish Markdown pages as HTML.
The main documentation source is `docs/index.md`. The `docs/` directory contains
reading material only; runtime agent/generator instructions remain under `instructions/`.

## Requirements and build

From the repository root, with Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) installed:

```bash
make html
```

This runs `uv run --extra docs sphinx-build` and installs the documentation
dependencies declared in `pyproject.toml`. The HTML homepage is
`docs/_build/html/index.html`. To rebuild after editing Markdown, repeat
`make html`. To remove generated output:

```bash
make clean
```

For a preinstalled Sphinx environment, use:

```bash
make html SPHINXBUILD=sphinx-build
```

`make html` enables Sphinx's nitpicky validation (`-n`) and treats warnings as
build failures (`-W --keep-going`). If you need a diagnostic build, override
`SPHINXOPTS`, but do not publish warnings as a qualified success.

The release keeps all current and historical `.md` guides discoverable via
Sphinx's navigation trees. Historical docs may show superseded commands.

## Directory boundaries

- `docs/` contains Markdown user/developer documentation and `docs/conf.py`.
- `instructions/astroakd/AstroAKD_Instruction.md` controls **arm B**.
- `instructions/astroakd_bench/AstroAKD-Bench_Instruction.md` controls synthetic question generation.
- `datasets/` contains reference records, gold candidates and run outputs.

The name of the generation instruction file changed in 0.6.7.5, but its
contents and hash remain identical. Do not pass the generation prompt to an
evaluated agent.
