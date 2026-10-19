#!/usr/bin/env bash
# Publish only managed Wiki pages. Requires the repository Wiki to be initialized.
set -euo pipefail

if (( $# != 2 )); then
  echo "Usage: $0 <wiki-export-directory> <temporary-clone-directory>" >&2
  exit 2
fi
source_dir="$1"
clone_dir="$2"
[[ -f "${source_dir}/Home.md" ]] || { echo 'Wiki export lacks Home.md' >&2; exit 1; }
[[ -n "${GITHUB_REPOSITORY:-}" ]] || { echo 'GITHUB_REPOSITORY is required' >&2; exit 1; }
token="${WIKI_TOKEN:-${GITHUB_TOKEN:-}}"
[[ -n "$token" ]] || { echo 'No wiki token available' >&2; exit 1; }

# Pass authentication using environment-only Git configuration; do not print tokens.
encoded="$(printf 'x-access-token:%s' "$token" | base64 -w0)"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0='http.https://github.com/.extraheader'
export GIT_CONFIG_VALUE_0="AUTHORIZATION: basic ${encoded}"
wiki_url="https://github.com/${GITHUB_REPOSITORY}.wiki.git"
if ! git clone --quiet "$wiki_url" "$clone_dir"; then
  echo 'Cannot clone Wiki: enable Wikis and create the first Wiki page, or configure WIKI_TOKEN with wiki write access.' >&2
  exit 1
fi
python scripts/sync_wiki.py --source "$source_dir" --target "$clone_dir"
git -C "$clone_dir" config user.name 'github-actions[bot]'
git -C "$clone_dir" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git -C "$clone_dir" add --all
if git -C "$clone_dir" diff --cached --quiet; then
  echo 'Wiki already matches the generated Markdown'
else
  git -C "$clone_dir" commit -m "docs: sync wiki from ${GITHUB_SHA:-main}"
  git -C "$clone_dir" push origin HEAD
fi
