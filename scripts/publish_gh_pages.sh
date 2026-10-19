#!/usr/bin/env bash
# Mirror a warning-clean Sphinx HTML build into the root of the gh-pages branch.
set -euo pipefail

if (( $# != 2 )); then
  echo "Usage: $0 <sphinx-html-directory> <temporary-worktree>" >&2
  exit 2
fi
source_dir="$1"
worktree="$2"
[[ -s "${source_dir}/index.html" ]] || { echo 'Sphinx build has no root index.html' >&2; exit 1; }
[[ -n "${GITHUB_REPOSITORY:-}" ]] || { echo 'GITHUB_REPOSITORY is required' >&2; exit 1; }

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
if git ls-remote --exit-code --heads origin gh-pages > /dev/null; then
  git fetch --no-tags --depth=1 origin gh-pages
  git worktree add --detach "${worktree}" FETCH_HEAD
else
  git worktree add --detach "${worktree}" HEAD
  git -C "${worktree}" checkout --orphan gh-pages
  git -C "${worktree}" rm --quiet -rf .
fi
rsync -a --checksum --delete --exclude='.git' "${source_dir}/" "${worktree}/"
touch "${worktree}/.nojekyll"
[[ -s "${worktree}/index.html" ]] || { echo 'gh-pages root index.html is missing' >&2; exit 1; }
git -C "${worktree}" add --all
if git -C "${worktree}" diff --cached --quiet; then
  echo 'gh-pages mirror already matches the HTML build'
else
  git -C "${worktree}" commit -m "docs: publish Sphinx HTML for ${GITHUB_SHA:-main}"
  git -C "${worktree}" push origin HEAD:gh-pages
fi
