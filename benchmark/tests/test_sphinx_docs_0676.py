"""0.6.7.6: moved Makefile and Read the Docs theme contract."""
from __future__ import annotations
import ast
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class ReadTheDocsBuildTests(unittest.TestCase):
    def test_build_location(self):
        self.assertFalse((ROOT / 'Makefile').exists())
        self.assertTrue((ROOT / 'docs/sphinx/Makefile').is_file())
        for operation in ('html','clean','linkcheck'):
            output=subprocess.run(['make','-n','-C','docs/sphinx',operation],
                cwd=ROOT,check=True,capture_output=True,text=True)
            self.assertTrue(output.stdout)
        output=subprocess.run(['make','-n','-f','docs/sphinx/Makefile','html'],
            cwd=ROOT,check=True,capture_output=True,text=True)
        self.assertIn('/docs/_build/html',output.stdout)

    def test_rtd_theme_and_deps(self):
        source=(ROOT/'docs/conf.py').read_text()
        ast.parse(source)
        self.assertIn('html_theme = "sphinx_rtd_theme"',source)
        self.assertIn('"sphinx_rtd_theme"',source)
        deps=(ROOT/'pyproject.toml').read_text()
        self.assertIn('"sphinx-rtd-theme>=3.1,<4"',deps)
        self.assertIn(__import__('benchmark').__version__,deps)

    def test_current_doc_commands(self):
        for path in ('README.md','docs/benchmark/quickstart.md',
                     'docs/benchmark/documentation_build.md',
                     'INSTALL_ASTROAKD_BENCH_0_6_7_6.md'):
            self.assertIn('make -C docs/sphinx html',(ROOT/path).read_text(),path)
        self.assertIn('make -C docs/sphinx clean',(ROOT/'README.md').read_text())

    def test_docs_index_no_external_sphinx_unresolved_refs(self):
        text=(ROOT/'docs/index.md').read_text()
        self.assertNotIn('](../README.md)',text)
        self.assertNotIn('](../CHANGELOG.md)',text)
        self.assertNotIn('](../instructions/',text)

    def test_preserved_benchmark_inputs(self):
        import hashlib
        hashes={
          'instructions/astroakd/AstroAKD_Instruction.md':'c7e9b4b8ffb608f2b380418a2df2d98c98bb6a807b065fff61757c2f1253e4ab',
          'instructions/astroakd_bench/AstroAKD-Bench_Instruction.md':'d430cf4d2508f124abee4deb23da44b3aca1618707f6c052fea8ee9deda47acf',
        }
        for name,expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected)

if __name__=='__main__':unittest.main()
