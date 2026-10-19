#!/usr/bin/env python3
"""Replace only the AstroAKD-Bench-owned wiki pages, retaining other pages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MANIFEST = ".astroakd-bench-managed-pages.json"


def names(folder: Path) -> set[str]:
    return {item.name for item in folder.iterdir() if item.is_file() and item.suffix == ".md"}


def sync(source: Path, destination: Path) -> None:
    if not (destination / ".git").exists():
        raise ValueError("Destination must be the checked-out Wiki Git repository")
    active = names(source)
    if not {"Home.md", "_Sidebar.md"}.issubset(active):
        raise ValueError("Wiki export is incomplete; refusing to publish")
    manifest = destination / MANIFEST
    old: set[str] = set()
    if manifest.exists():
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("managed_pages"), list):
            raise ValueError("Malformed managed-page manifest")
        old = set(raw["managed_pages"])
        if not all(isinstance(name, str) and name.endswith(".md") and name == Path(name).name for name in old):
            raise ValueError("Unsafe managed-page manifest")
    for name in sorted(old - active):
        (destination / name).unlink(missing_ok=True)
    for name in sorted(active):
        (destination / name).write_bytes((source / name).read_bytes())
    manifest.write_text(json.dumps({"managed_pages": sorted(active)}, indent=2) + "\n", encoding="utf-8")
    print(f"Wiki sync: {len(active)} managed Markdown files; unrelated files retained")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--target", required=True, type=Path)
    a = p.parse_args()
    sync(a.source, a.target)


if __name__ == "__main__":
    main()
