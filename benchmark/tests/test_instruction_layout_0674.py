"""0.6.7.4: prompt separation, unchanged hashes and default generation path."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
import unittest

from benchmark.llm_generation import INSTRUCTIONS_PATH, instruction_text


ROOT = Path(__file__).resolve().parents[2]
ASTROAKD_PATH = ROOT / 'instructions' / 'astroakd' / 'AstroAKD_Instruction.md'
GEN_PATH = ROOT / 'instructions' / 'astroakd_bench' / 'AstroAKD-Bench_Instruction.md'


class InstructionLayoutTests(unittest.TestCase):
    def test_astrokd_instruction_same_bytes_as_0673(self):
        self.assertTrue(ASTROAKD_PATH.is_file())
        self.assertEqual(hashlib.sha256(ASTROAKD_PATH.read_bytes()).hexdigest(),
                         'c7e9b4b8ffb608f2b380418a2df2d98c98bb6a807b065fff61757c2f1253e4ab')

    def test_bench_generation_prompt_current_policy(self):
        self.assertEqual(GEN_PATH, INSTRUCTIONS_PATH)
        self.assertEqual(hashlib.sha256(GEN_PATH.read_bytes()).hexdigest(),
                         '949420a46865a253b31d41dea96d5d307e112a6dbc8c9138b71cc41b8f1fcc71')
        self.assertEqual(instruction_text(enabled=True),GEN_PATH.read_text(encoding='utf-8'))

    def test_docs_do_not_contain_operational_instruction_files(self):
        self.assertFalse((ROOT/'docs/agent/AstroAKD_Instruction.md').exists())
        self.assertFalse((ROOT/'docs/benchmark/llm_generation_instructions_v1.md').exists())
        self.assertTrue((ROOT/'docs/index.md').is_file())
        self.assertTrue((ROOT/'instructions/README.md').is_file())
        self.assertTrue(all(
            p.suffix == '.md' or p in (ROOT/'docs/conf.py', ROOT/'docs/sphinx/Makefile', ROOT/'docs/requirements.txt')
            for p in (ROOT/'docs').rglob('*')
            if p.is_file() and '_build' not in p.parts
            and '__pycache__' not in p.parts
        ))

    def test_active_markdown_local_links_resolve(self):
        paths=[ROOT/'README.md',ROOT/'instructions/README.md',ROOT/'docs/index.md',
               *(ROOT/'docs/benchmark').glob('*.md')]
        for file in paths:
            for destination in re.findall(r'\[[^\]]*\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
                if '://' in destination or destination.startswith(('#','mailto:','sandbox:')):
                    continue
                relative=destination.split('#',1)[0]
                if relative:
                    self.assertTrue((file.parent/relative).exists(),f'{file}: missing {relative}')

    def test_current_readme_and_guides_link_to_new_paths(self):
        for path in (ROOT/'README.md', ROOT/'docs/index.md', ROOT/'docs/benchmark/quickstart.md'):
            content=path.read_text(encoding='utf-8')
            self.assertIn('instructions/astroakd/AstroAKD_Instruction.md',content)
            self.assertIn('instructions/astroakd_bench/AstroAKD-Bench_Instruction.md',content)
        self.assertIn(__import__('benchmark').__version__,(ROOT/'pyproject.toml').read_text())


if __name__=='__main__':
    unittest.main()
