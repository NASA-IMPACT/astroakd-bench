"""Sphinx configuration for AstroAKD-Bench documentation."""
from __future__ import annotations

project = "AstroAKD-Bench"
author = "AstroAKD-Bench contributors"
release = "0.6.7.5"
version = release
root_doc = "index"
extensions = ["myst_parser"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", ".DS_Store", "Thumbs.db"]
myst_heading_anchors = 3
html_theme = "alabaster"
html_title = f"AstroAKD-Bench {release} documentation"
html_show_sourcelink = True
html_static_path = []

# Historical guides link to files in the repository root and to pre-migration
# file paths. Current local links are separately checked by unit tests.
suppress_warnings = ["myst.xref_missing"]
