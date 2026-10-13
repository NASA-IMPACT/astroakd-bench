"""0.5.0 root layout, safe migration, and readable CLI checks."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/migrate_datasets_0_5_0.py'

class RootLayout050Tests(unittest.TestCase):
    def test_prevent_overwrite_existing_root(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            (p/'datasets').mkdir()
            (p/'benchmark/datasets').mkdir(parents=True)
            output=subprocess.run([sys.executable,str(SCRIPT)],cwd=p,text=True,capture_output=True)
            self.assertNotEqual(output.returncode,0)
            self.assertTrue((p/'benchmark/datasets').exists())

    def test_preserve_noncanonical_local_files(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/'benchmark/datasets/generated'
            src.mkdir(parents=True)
            (src/'my_queries.jsonl').write_text('{"example":true}\n')
            output=subprocess.run([sys.executable,str(SCRIPT)],cwd=p,text=True,capture_output=True)
            self.assertEqual(output.returncode,0,output.stderr)
            self.assertEqual((p/'datasets/generated/my_queries.jsonl').read_text(),'{"example":true}\n')
            self.assertFalse((p/'benchmark/datasets').exists())

    def test_refuses_corrupt_accepted_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/'benchmark/datasets/generated'
            src.mkdir(parents=True)
            (src/'synthetic_queries.jsonl').write_text('{"wrong":true}\n')
            output=subprocess.run([sys.executable,str(SCRIPT)],cwd=p,text=True,capture_output=True)
            self.assertNotEqual(output.returncode,0)
            self.assertFalse((p/'datasets').exists())

    def test_pretty_cli_inspection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/'data.jsonl'; target=p/'preview.json'
            src.write_text('{"x":1}\n{"x":2}\n')
            before=hashlib.sha256(src.read_bytes()).hexdigest()
            cmd=[sys.executable,'-m','benchmark','inspect','--input',str(src),
                 '--limit','1','--json-format','pretty','--output',str(target)]
            r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['records_shown'],1)
            self.assertEqual(json.loads(target.read_text())['records_shown'],1)
            self.assertIn('\n  "records"',target.read_text())
            self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
