#!/usr/bin/env python3
"""Convert the current Sphinx MyST sources to GitHub Wiki Markdown.

Purely local: reads source Markdown from this checkout; does not use an API.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Home.md": "docs/index.md",
    "AstroAKD-Getting-Started.md": "docs/benchmark/quickstart.md",
    "AstroAKD-Create-Queries.md": "docs/benchmark/create_queries.md",
    "AstroAKD-ADS-and-MCP.md": "docs/benchmark/ads_and_mcp.md",
    "AstroAKD-References-and-Review.md": "docs/benchmark/references_and_review.md",
    "AstroAKD-Evaluation-and-Plots.md": "docs/benchmark/evaluation_and_plots.md",
    "AstroAKD-Python-API.md": "docs/benchmark/python_api.md",
    "AstroAKD-Documentation-Build.md": "docs/benchmark/documentation_build.md",
    "AstroAKD-README.md": "README.md",
    "AstroAKD-Changelog.md": "CHANGELOG.md",
}
LOOKUP = {(ROOT / source).resolve(): Path(page).stem for page, source in SOURCES.items()}
LINK = re.compile(r"(?<!!)\[([^]]+)\]\(([^)]+)\)")


def convert(source_path: Path, text: str) -> str:
    """Keep fenced code unchanged; translate internal cross-document links."""
    lines = []
    in_fence = False
    fence_mark = ""
    in_toctree = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if in_toctree:
            if stripped.startswith("```"):
                in_toctree = False
            continue
        if stripped.startswith("```{toctree}") and not in_fence:
            in_toctree = True
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            mark = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_mark = mark
            elif mark == fence_mark:
                in_fence = False
            lines.append(line)
            continue
        if in_fence:
            lines.append(line)
            continue

        def replace(match: re.Match[str]) -> str:
            label, uri = match.groups()
            target, separator, fragment = uri.partition("#")
            if not target or ":" in target or target.startswith("/"):
                return match.group(0)
            candidate = (source_path.parent / target).resolve()
            if candidate not in LOOKUP:
                return match.group(0)
            slug = LOOKUP[candidate]
            return f"[{label}]({slug}{'#' + fragment if separator else ''})"

        lines.append(LINK.sub(replace, line))
    return "".join(lines)


def export(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        source_path = ROOT / source
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing Wiki source: {source}")
        body = convert(source_path, source_path.read_text(encoding="utf-8"))
        notice = ("<!-- GENERATED from main/" + source + ". Do not edit this wiki page directly. -->\n\n")
        if name == "Home.md":
            body += "\n## Wiki guide\n\n"
            for page, src in SOURCES.items():
                if page != "Home.md":
                    title = src.rsplit("/", 1)[-1].replace(".md", "").replace("_", " ").title()
                    body += f"- [{title}]({Path(page).stem})\n"
        (output / name).write_text(notice + body.rstrip() + "\n", encoding="utf-8")
    sidebar = "<!-- GENERATED navigation from main. -->\n\n**AstroAKD-Bench**\n\n"
    sidebar += "- [Home](Home)\n"
    for page, src in SOURCES.items():
        if page == "Home.md":
            continue
        title = src.rsplit("/", 1)[-1].replace(".md", "").replace("_", " ").title()
        sidebar += f"- [{title}]({Path(page).stem})\n"
    (output / "_Sidebar.md").write_text(sidebar, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    export(args.output)
    print(f"Wiki export: {len(SOURCES) + 1} managed pages at {args.output}")


if __name__ == "__main__":
    main()
