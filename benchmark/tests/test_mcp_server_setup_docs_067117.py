"""Guard the first-time external MCP setup in current user-facing docs."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGES = (
    'README.md',
    'INSTALL.md',
    'docs/benchmark/quickstart.md',
    'docs/benchmark/ads_and_mcp.md',
)
COMMANDS = (
    'git clone https://github.com/NASA-IMPACT/astroquery-mcp.git',
    'cd astroquery-mcp',
    'uv sync',
    'uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000',
)


class MCPServerSetupDocs(unittest.TestCase):
    def test_all_user_setup_pages_include_complete_server_install(self):
        for name in PAGES:
            with self.subTest(page=name):
                contents = (ROOT / name).read_text(encoding='utf-8')
                server_start = contents.index(COMMANDS[0])
                locations = [contents.index(command, server_start) for command in COMMANDS]
                self.assertEqual(locations, sorted(locations))
                self.assertIn('http://127.0.0.1:8000/mcp', contents)

    def test_credentials_distinguish_server_and_benchmark(self):
        for name in PAGES:
            with self.subTest(page=name):
                contents = (ROOT / name).read_text(encoding='utf-8')
                self.assertIn('OPENAI_API_KEY', contents)
                self.assertIn('API_DEV_KEY', contents)
                self.assertIn('server', contents.lower())

    def test_current_version(self):
        import tomllib
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual(project['project']['version'], '0.6.7.11.7')
