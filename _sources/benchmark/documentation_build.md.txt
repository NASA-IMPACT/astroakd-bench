# Build and publish the current documentation

AstroAKD-Bench uses one maintained Sphinx/MyST documentation tree (`docs/`). It does not generate separate websites for historical releases. The version displayed by the site comes from `pyproject.toml`.

## Build locally

From the repository root:

```bash
make -C docs/sphinx clean
make -C docs/sphinx html
```

Open `docs/_build/html/index.html`. Sphinx, MyST and the Read the Docs theme are pinned in `docs/requirements.txt`. The build uses `-n -W --keep-going` to treat unresolved cross-references and warnings as failures. To use an installed Sphinx directly:

```bash
python -m pip install -r docs/requirements.txt
make -C docs/sphinx html SPHINXBUILD=sphinx-build
```

Link checking is an optional network-dependent step: `make -C docs/sphinx linkcheck`.

## Automatic publishing from main (0.6.7.11.13)

The GitHub Actions workflow **`.github/workflows/publish-docs.yml`** builds and publishes the site automatically when a push to `main` changes:

- `docs/**` (including this document, `docs/index.md`, Sphinx config, themes/dependencies and all guides);
- `README.md`, `INSTALL.md`, `CHANGELOG.md`, `pyproject.toml`, or `.readthedocs.yaml`;
- the publishing workflow or `scripts/export_wiki.py`, `scripts/sync_wiki.py`, `scripts/publish_gh_pages.sh`, `scripts/publish_wiki.sh`.

It is also available under **Actions → Publish documentation → Run workflow** (`workflow_dispatch`). Updates on other branches do not publish until merged to `main`.

The workflow:

1. Checks out `main`, installs pinned Sphinx dependencies and builds warning-clean HTML. It **fails** if HTML `index.html` is missing or empty.
2. Copies the generated Sphinx site to the **root of `gh-pages`**, so `gh-pages:index.html` exists; it also adds `.nojekyll`. It does not commit generated HTML to `main` and skips identical commits.
3. Uploads that same built HTML as a GitHub Pages Actions artifact and performs an explicit GitHub Pages deployment. This is necessary because a commit made with `GITHUB_TOKEN` to `gh-pages` **does not itself trigger GitHub Pages branch publishing**.
4. Exports current Markdown to GitHub wiki pages (`Home.md`, navigation sidebar, README, CHANGELOG, and individual guide pages). It clones the repository `.wiki.git`, updates **only** managed pages, and leaves unrelated human-authored wiki files intact. Identical wiki content is not committed twice.

The website and the Wiki are **generated outputs**. Make changes to the source Markdown on `main`; do not edit managed Wiki pages or `gh-pages` directly. Old pages managed by the exporter are removed through its stored manifest when a guide is retired; unrelated pages remain untouched.

## One-time repository configuration

1. Repository **Settings → Pages → Build and deployment → Source**: choose **GitHub Actions**. Do not choose `gh-pages` as the live publish source; the workflow already keeps it as a mirror and performs a separate Actions deployment. The `gh-pages` branch is created on the first successful publishing run. You can browse the built `index.html` in the branch root.
2. Repository **Settings → General → Features**: enable **Wikis**, then create/save the first wiki page in the browser. The `.wiki.git` remote does not exist until the wiki is initialized. The first automatic run will replace wiki `Home.md` with the generated home page and add the generated sidebar; preserve any content currently on the wiki home page elsewhere first.
3. Allow repository Actions to run. The workflow explicitly requests `contents: write` (mirror/wiki), `pages: write` and `id-token: write` (live Pages deployment). Organization or branch restrictions may additionally need configuration. Protect `main` as desired; the job does not push to `main`.
4. By default the Wiki sync uses GitHub's ephemeral `GITHUB_TOKEN`. **If that token cannot write the Wiki on your GitHub organization**, configure a repository Actions secret named **`WIKI_TOKEN`** containing a properly authorized repository-scoped token; only the Wiki sync uses it. Tokens are not embedded in URL strings or echoed. Do not add `OPENAI_API_KEY`, `ADS_API_KEY`, or `API_DEV_KEY`: none is required for building or publishing docs.

GitHub project Pages URL is usually `https://OWNER.github.io/REPO/`; account/org site repositories use `https://OWNER.github.io/`. The workflow prints the actual deployment URL in the GitHub Pages environment. The Wiki URL is `https://github.com/OWNER/REPO/wiki`.

## Troubleshooting

- **HTML build fails:** inspect the `Build the current Sphinx HTML site` step. Fix broken MyST syntax, doc links, or warning-producing changes on `main`. Re-run the workflow.
- **`gh-pages/index.html` exists but the web site is not live:** ensure Pages **Source = GitHub Actions** and that `Deploy live GitHub Pages site` passed. GitHub docs specify that `GITHUB_TOKEN` commits cannot trigger a Pages branch rebuild.
- **Wiki clone fails:** confirm Wikis are enabled and the first page exists. Check the repository's Actions token policy. If necessary use `WIKI_TOKEN` with wiki-write access.
- **Wiki sync succeeds but a page looks different from Sphinx:** the Wiki renders GitHub-Flavored Markdown, not Sphinx/MyST. The exporter removes navigation-only `{toctree}` directives and rewrites internal `.md` document links, while preserving fenced CLI examples. Prefer the Sphinx Pages site for the canonical formatting.
- **Manual wiki edits disappear:** managed files are re-synced from `main`; keep personal pages under other names. The manifest `.astroakd-bench-managed-pages.json` tracks generated pages only.
- **Unchanged docs:** the workflow avoids redundant commits. You can trigger a manual rebuild to redeploy identical content.

No benchmark dataset, agent-run journal, MCP queries, or scoring evidence is modified by documentation publishing.
