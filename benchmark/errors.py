"""Stable client-side exceptions (separate from server.models.errors)."""

from __future__ import annotations

from typing import Any


class BenchmarkError(Exception):
    """Base exception for actionable benchmark failures."""


class MCPConnectionError(BenchmarkError):
    """Could not establish a session or reach the MCP server."""


class MCPTransportError(BenchmarkError):
    """An MCP request failed at the protocol or transport layer."""


class MCPResponseError(BenchmarkError):
    """MCP response could not be normalized or violated its expected shape."""


class MCPToolError(BenchmarkError):
    """MCP tool returned a failure (protocol or application-level)."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        *,
        code: str = "TOOL_ERROR",
        payload: Any = None,
        protocol_error: bool = False,
    ) -> None:
        super().__init__(f"{tool_name} [{code}]: {message}")
        self.tool_name = tool_name
        self.message = message
        self.code = code
        self.payload = payload
        self.protocol_error = protocol_error
