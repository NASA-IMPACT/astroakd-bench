"""Sphinx site for the current AstroAKD-Bench release only."""
from pathlib import Path
import tomllib

project = 'AstroAKD-Bench'
author = 'AstroAKD-Bench contributors'
release = tomllib.loads((Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text())['project']['version']
version = release
root_doc = "index"
extensions = ["myst_parser", "sphinx_rtd_theme"]
source_suffix = {'.md': 'markdown'}
exclude_patterns = ['_build', '.DS_Store', 'Thumbs.db']
myst_heading_anchors = 3
html_theme = "sphinx_rtd_theme"
html_theme_options = {'collapse_navigation': True, 'navigation_depth': 2,
                      'sticky_navigation': True, 'titles_only': True}
html_title = f'AstroAKD-Bench {release}'
html_show_sourcelink = False
html_static_path = []
