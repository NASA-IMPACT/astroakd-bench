"""Opt-in real local HTTP integration, run with ASTROAKD_TEST_LIVE=1.

Requires local Astroquery MCP on 127.0.0.1:8000 and external SIMBAD access.
"""

import asyncio
import os
import unittest

from benchmark.diagnostics import doctor


@unittest.skipUnless(os.getenv("ASTROAKD_TEST_LIVE") == "1",
                     "Run with ASTROAKD_TEST_LIVE=1 to test the real local MCP server")
class LiveMCPTests(unittest.TestCase):
    def test_real_http_and_simbad(self):
        report = asyncio.run(doctor(smoke=True))
        self.assertEqual(report["status"], "PASS", report)
