# Build the current HTML documentation

The documentation describes the **current supported release** and does not include version-specific old installation or qualification guides in its navigation. Development history belongs in `CHANGELOG.md`; old Markdown sources and qualification notes are archived separately.

From the repository root:

```bash
make -C docs/sphinx html
```

Open `docs/_build/html/index.html`. To clean and rebuild:

```bash
make -C docs/sphinx clean
make -C docs/sphinx html
```

This uses Sphinx, MyST Markdown and the Read the Docs theme. The default Makefile uses `-n -W --keep-going` to treat missing local references and Sphinx warnings as build failures. For an installed Sphinx build, use `make -C docs/sphinx html SPHINXBUILD=sphinx-build`.

The current version number comes from `pyproject.toml`. Old rendered HTML is *not* a reliable copy of the current documentation: always clean and rebuild after changing the navigation or removing historical pages.
