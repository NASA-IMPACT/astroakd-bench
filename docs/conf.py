"""Sphinx configuration for AstroAKD-Bench documentation."""
from __future__ import annotations

project = "AstroAKD-Bench"
author = "AstroAKD-Bench contributors"
release = "0.6.7.9"
version = release
root_doc = "index"
extensions = ["myst_parser", "sphinx_rtd_theme"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", ".DS_Store", "Thumbs.db"]
myst_heading_anchors = 3
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
    "sticky_navigation": True,
    "titles_only": False,
}
html_logo = None
html_title = f"AstroAKD-Bench {release} documentation"
html_show_sourcelink = True
html_static_path = []

# Historical guides link to files in the repository root and to pre-migration
# file paths. Current local links are separately checked by unit tests.
suppress_warnings = ["myst.xref_missing"]
