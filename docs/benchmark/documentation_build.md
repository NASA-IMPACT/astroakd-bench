# Build AstroAKD-Bench HTML documentation

AstroAKD-Bench uses **Sphinx**, **MyST-Parser**, and the official **Read the Docs
theme** (`sphinx_rtd_theme`), matching the navigation and sidebar style of
[XSTAR-Tools documentation](https://xstar-tools.readthedocs.io/en/latest/).
Documentation sources remain under `docs/`; agent and generation prompts remain
under `instructions/`. The `Makefile` is deliberately located at `docs/sphinx/`.

## Build the HTML documentation

From the repository root, with Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
make -C docs/sphinx html
```

Alternatively, from inside the builder folder:

```bash
cd docs/sphinx
make html
```

Both forms run `uv run --project <repository-root> --extra docs sphinx-build`
and use `docs/conf.py`. Optional dependencies are declared in `pyproject.toml`:
Sphinx, MyST-Parser and `sphinx-rtd-theme`.

Output: `docs/_build/html/index.html`. Open this in a browser to view the
sidebar, built-in site search, responsive layout, and linked current/historical
guides. The old Sphinx Alabaster output is replaced when the HTML files are rebuilt.

To clean generated pages and doctrees:

```bash
make -C docs/sphinx clean
```

To use a system-provided Sphinx installation instead of uv:

```bash
make -C docs/sphinx html SPHINXBUILD=sphinx-build
```

To check remote links (requires network access):

```bash
make -C docs/sphinx linkcheck
```

## Build validation

The standard HTML build is strict: `-n -W --keep-going` enables nitpicky
mode, promotes warnings to errors, and continues collecting diagnostics.
It is acceptable to disable this temporarily for local debugging, but not
for a qualified publication build:

```bash
make -C docs/sphinx html SPHINXOPTS='-n -W --keep-going'
```

The Read the Docs theme is configured in `docs/conf.py` by
`html_theme = "sphinx_rtd_theme"`; it is also registered as an extension to
ensure its JavaScript dependencies are initialized.

## Clock skew warning on file timestamps

Your 0.6.7.5 build **succeeded**, even though Make reported the root
Makefile as having a modification time in the future. Clock-skew warnings
can occur after transferring files or from unsynchronized host clocks.
They are not Sphinx errors. Verify host time and, if the extracted tree
has future timestamps, refresh source file modification times before
rebuilding, for example:

```bash
# Only after confirming that local source timestamps can safely be changed.
touch docs/sphinx/Makefile
make -C docs/sphinx html
```

If many files have future timestamps, synchronize the system clock first;
rebuilding will then refresh the generated outputs. Avoid modifying the
saved benchmark journals, reference/oracle files, or instruction contents
solely to suppress timestamp warnings.

## Known historical Markdown links

Earlier archived documentation once linked to paths that were subsequently
moved or renamed. Active documentation uses valid Sphinx-local links; older
paths appear as literal historical text to preserve their meaning, not as
invalid hyperlinks. The agent instruction remains frozen by content hash.
