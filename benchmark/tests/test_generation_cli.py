"""Generation CLI contract: argument parsing, JSONL output, overwrite policy."""

import asyncio
import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from benchmark.cli import build_parser, main
from benchmark.tests.test_generator import run_fixture


class CLITests(unittest.TestCase):
    def test_generate_options_are_parsed(self):
        args = build_parser().parse_args([
            "generate", "--count", "50", "--seed", "42", "--modules", "simbad,mast",
            "--output", "out.jsonl", "--report", "summary.json"])
        self.assertEqual(args.command, "generate")
        self.assertEqual(args.count, 50)
        self.assertEqual(args.seed, 42)
        self.assertEqual(args.modules, "simbad,mast")
        self.assertEqual(args.output, Path("out.jsonl"))
        self.assertEqual(args.report, Path("summary.json"))

    def test_main_writes_candidates_not_only_report(self):
        tasks, report = run_fixture(count=50)[0]
        async def mocked_generate(*args, **kwargs):
            return tasks, dict(report)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "cases.jsonl"
            metadata = Path(temp) / "report.json"
            argv = ["generate", "--backend", "template", "--count", "50", "--seed", "42",
                    "--output", str(path), "--report", str(metadata)]
            with patch("benchmark.cli.generate", mocked_generate):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(main(argv), 0)
                    self.assertEqual(len(path.read_text().splitlines()), 50)
                    self.assertEqual(json.loads(metadata.read_text())["status"], "PASS")
                    initial = path.read_bytes()
                    self.assertEqual(main(argv), 1)  # refuse overwrite
                    self.assertEqual(initial, path.read_bytes())
                    self.assertEqual(main(argv + ["--replace"]), 0)
                    self.assertEqual(initial, path.read_bytes())

    def test_invalid_module_does_not_write_dataset(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "cases.jsonl"
            with contextlib.redirect_stdout(io.StringIO()) as out:
                status = main(["generate", "--modules", "simbad,delete",
                               "--output", str(path)])
            self.assertEqual(status, 1)
            self.assertFalse(path.exists())
            self.assertEqual(json.loads(out.getvalue())["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
