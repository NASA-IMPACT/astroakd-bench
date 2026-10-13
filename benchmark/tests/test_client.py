"""Offline regression tests for MCP transport and server response contracts."""

import asyncio
from dataclasses import dataclass
import json
from types import SimpleNamespace
import unittest

from benchmark.client import AstroqueryMCPClient, CORE_TOOLS, _extract_result
from benchmark.diagnostics import doctor
from benchmark.errors import (
    MCPConnectionError, MCPResponseError, MCPToolError, MCPTransportError,
)


def response(payload=None, *, protocol_error=False, fallback=False):
    if fallback:
        return SimpleNamespace(data=None, structured_content=None,
            content=[SimpleNamespace(text=json.dumps(payload))], is_error=protocol_error)
    return SimpleNamespace(data=payload, structured_content=None,
        content=[], is_error=protocol_error)


@dataclass
class MockTool:
    name: str
    description: str = "fake"
    inputSchema: dict | None = None


class FakeSession:
    def __init__(self, url, *, failures=None, fallback=False, protocol_error=False):
        self.url = url
        self.failures = failures or {}
        self.fallback = fallback
        self.protocol_error = protocol_error
        self.calls = []
        self.closed = False

    async def __aenter__(self):
        if self.failures.get("connect"):
            raise RuntimeError("connection refused")
        return self

    async def __aexit__(self, typ, value, tb):
        self.closed = True

    async def ping(self):
        if self.failures.get("ping"):
            raise RuntimeError("ping failed")

    async def list_tools(self):
        if self.failures.get("list_tools"):
            raise RuntimeError("catalog failed")
        names = CORE_TOOLS - set(self.failures.get("missing_tools", []))
        return [MockTool(name=n, inputSchema={"type": "object"}) for n in sorted(names)]

    async def call_tool(self, name, args, *, timeout=None):
        self.calls.append((name, args))
        if self.failures.get("tool_transport"):
            raise RuntimeError("broken transport")
        if self.protocol_error:
            return response({"message": "protocol tool problem", "code": "PROTO"}, protocol_error=True)
        if self.failures.get("application_error"):
            return response({"error": True, "code": "SERVICE_ERROR", "message": "archive unavailable"})
        if self.failures.get("string_error"):
            return response({"error": "Module not found: invalid", "functions": []})
        if name == "astroquery_list_modules":
            result = {"module_count": 1,
                      "modules": [{"name": "simbad", "class_path": "astroquery.simbad.Simbad", "available": True}]}
        elif name == "astroquery_list_functions":
            result = {"function_count": 1,
                      "functions": [{"name": "simbad.query_object", "method": "query_object"}]}
        elif name == "astroquery_get_function_info":
            result = {"name": "simbad.query_object", "method": "query_object",
                      "parameters": [{"name": "object_name", "required": True}]}
        elif name == "astroquery_execute":
            result = {"success": True, "module": "simbad", "function": "query_object",
                      "result": {"columns": ["main_id", "ra", "dec"],
                                 "row_count": 1, "data": [["M 31", 10.68, 41.26]]}}
        else:
            raise AssertionError(f"Unexpected tool: {name}")
        if self.failures.get("empty_simbad") and name == "astroquery_execute":
            result["result"]["data"] = []
        return response(result, fallback=self.fallback)


class ClientTests(unittest.TestCase):
    def test_doctor_full_pass_and_live_smoke(self):
        instances = []
        def factory(url):
            session = FakeSession(url)
            instances.append(session)
            return session
        report = asyncio.run(doctor(smoke=True, session_factory=factory))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual([item["status"] for item in report["checks"]],
                         ["PASS", "PASS", "PASS", "PASS", "PASS", "PASS"])
        self.assertTrue(instances[0].closed)
        self.assertIn(("astroquery_execute", {"module_name": "simbad",
                          "function_name": "query_object", "params": {"object_name": "M31"}}),
                      instances[0].calls)

    def test_fast_mode_skips_slow_discovery_and_archive(self):
        session = FakeSession("http://127.0.0.1:8000/mcp")
        report = asyncio.run(doctor(fast=True, session_factory=lambda _: session))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual([x["status"] for x in report["checks"][-2:]], ["SKIP", "SKIP"])
        self.assertEqual([x[0] for x in session.calls], ["astroquery_list_modules"])

    def test_text_content_fallback(self):
        session = FakeSession("http://localhost:8000/mcp", fallback=True)
        async def action():
            async with AstroqueryMCPClient(session.url, session_factory=lambda _: session) as client:
                return await client.list_modules()
        self.assertEqual(asyncio.run(action())["module_count"], 1)

    def test_structured_envelope(self):
        self.assertEqual(_extract_result(response({"result": 3})), {"result": 3})

    def test_application_error_dictionary(self):
        session = FakeSession("http://localhost/mcp", failures={"application_error": True})
        async def action():
            async with AstroqueryMCPClient(session.url, session_factory=lambda _: session) as client:
                await client.list_modules()
        with self.assertRaises(MCPToolError) as cm:
            asyncio.run(action())
        self.assertEqual(cm.exception.code, "SERVICE_ERROR")
        self.assertFalse(cm.exception.protocol_error)

    def test_string_application_error_dictionary(self):
        session = FakeSession("http://localhost/mcp", failures={"string_error": True})
        async def action():
            async with AstroqueryMCPClient(session.url, session_factory=lambda _: session) as client:
                await client.list_functions("invalid")
        with self.assertRaises(MCPToolError):
            asyncio.run(action())

    def test_protocol_tool_error(self):
        session = FakeSession("http://localhost/mcp", protocol_error=True)
        async def action():
            async with AstroqueryMCPClient(session.url, session_factory=lambda _: session) as client:
                await client.list_modules()
        with self.assertRaises(MCPToolError) as cm:
            asyncio.run(action())
        self.assertTrue(cm.exception.protocol_error)
        self.assertEqual(cm.exception.code, "PROTO")

    def test_disconnected_server(self):
        session = FakeSession("http://localhost/mcp", failures={"connect": True})
        report = asyncio.run(doctor(session_factory=lambda _: session))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["error"]["type"], "MCPConnectionError")

    def test_ping_failure_closes_session(self):
        session = FakeSession("http://localhost/mcp", failures={"ping": True})
        report = asyncio.run(doctor(session_factory=lambda _: session))
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(session.closed)

    def test_missing_required_tool(self):
        session = FakeSession("http://localhost/mcp",
                              failures={"missing_tools": ["astroquery_execute"]})
        report = asyncio.run(doctor(session_factory=lambda _: session))
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("astroquery_execute", report["checks"][1]["details"]["missing"])

    def test_failed_transport_not_a_tool_error(self):
        session = FakeSession("http://localhost/mcp", failures={"tool_transport": True})
        async def action():
            async with AstroqueryMCPClient(session.url, session_factory=lambda _: session) as client:
                await client.list_modules()
        with self.assertRaises(MCPTransportError):
            asyncio.run(action())

    def test_empty_simbad_is_rejected(self):
        session = FakeSession("http://localhost/mcp", failures={"empty_simbad": True})
        report = asyncio.run(doctor(smoke=True, session_factory=lambda _: session))
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("empty", report["error"]["message"].lower())

    def test_parameter_validation(self):
        with self.assertRaises(ValueError):
            AstroqueryMCPClient("localhost:8000/mcp")
        with self.assertRaises(ValueError):
            AstroqueryMCPClient("http://localhost/mcp", timeout=0)


if __name__ == "__main__":
    unittest.main()
