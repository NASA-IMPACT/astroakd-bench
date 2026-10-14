"""0.6.7.5: verify prompt migration and offline documentation build contracts."""
from __future__ import annotations

import ast
import hashlib
import subprocess
import unittest
from pathlib import Path

from benchmark.llm_generation import INSTRUCTIONS_PATH, instruction_text

ROOT = Path(__file__).resolve().parents[2]


class SphinxDocumentationTests(unittest.TestCase):
    def test_prompt_rename_does_not_change_contents(self):
        target = ROOT / "instructions/astroakd_bench/AstroAKD-Bench_Instruction.md"
        self.assertEqual(INSTRUCTIONS_PATH, target)
        self.assertTrue(target.is_file())
        self.assertFalse((target.parent / "llm_generation_instructions_v1.md").exists())
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                         "d430cf4d2508f124abee4deb23da44b3aca1618707f6c052fea8ee9deda47acf")
        self.assertEqual(instruction_text(enabled=True), target.read_text(encoding="utf-8"))

    def test_sphinx_configuration_parseable(self):
        conf = ROOT / "docs/conf.py"
        ast.parse(conf.read_text(encoding="utf-8"))
        self.assertIn('"myst_parser"', conf.read_text())
        self.assertIn('root_doc = "index"', conf.read_text())
        self.assertTrue((ROOT / "docs/benchmark/documentation_build.md").is_file())
        self.assertIn("sphinx>=8.2", (ROOT / "pyproject.toml").read_text())

    def test_makefile_html_command(self):
        result = subprocess.run(["make", "-n", "html"], cwd=ROOT / "docs/sphinx",
                                text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=True)
        self.assertIn("--extra docs sphinx-build -b html", result.stdout)
        self.assertIn("docs/_build/html", result.stdout)
        self.assertIn("make -C docs/sphinx clean", (ROOT / "README.md").read_text())

    def test_sphinx_toc_targets_exist(self):
        index = ROOT / "docs/index.md"
        source = index.read_text()
        self.assertIn("{toctree}", source)
        inside = False
        entries = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped == "```{toctree}":
                inside = True
            elif inside and stripped == "```":
                inside = False
            elif inside and stripped and not stripped.startswith(":"):
                entries.append(stripped)
        self.assertGreaterEqual(len(entries), 20)
        for item in entries:
            self.assertTrue((ROOT / "docs" / f"{item}.md").is_file(), item)

    def test_readme_documents_all_user_workflows(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("Run all 50 questions (new experiment; no `--resume`)", text)
        self.assertIn("Pilot run (`--limit 5`)", text)
        self.assertIn("Resume a partial pilot (`--resume`)", text)
        self.assertIn("Score and generate CSV reports / plots", text)
        self.assertIn("make -C docs/sphinx html", text)
        self.assertIn("AstroAKD-Bench_Instruction.md", text)
        self.assertNotIn("Re-score and regenerate CSV reports / plots", text)

    def test_qualification_records_no_live_build(self):
        self.assertIn("HTML", (ROOT / "CHANGELOG.md").read_text())
        self.assertIn(__import__('benchmark').__version__, (ROOT / 'benchmark/__init__.py').read_text())

if __name__ == "__main__":
    unittest.main()
