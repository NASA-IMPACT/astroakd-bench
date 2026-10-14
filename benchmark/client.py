"""Async Streamable-HTTP client for the existing Astroquery FastMCP server.

No server-side imports. FastMCP is imported lazily so tests can inject a fake
session without requiring astronomy packages or a running service.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from typing import Any, Callable
from urllib.parse import urlsplit

from . import DEFAULT_MCP_URL
from .mcp_config import resolve_mcp_url, resolve_mcp_token, sanitize_mcp_error
from .errors import (
    MCPConnectionError,
    MCPResponseError,
    MCPToolError,
    MCPTransportError,
)


CORE_TOOLS = frozenset(
    {
        "astroquery_list_modules",
        "astroquery_list_functions",
        "astroquery_get_function_info",
        "astroquery_execute",
    }
)


def normalize(value: Any) -> Any:
    """Convert common FastMCP/Pydantic outputs into JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize(dataclasses.asdict(value))
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return normalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise MCPResponseError(f"Non-JSON-compatible tool response: {type(value).__name__}")


def _extract_result(result: Any) -> Any:
    """Prefer hydrated data, then structured content, then text JSON blocks."""
    data = getattr(result, "data", None)
    if data is not None:
        return normalize(data)
    data = getattr(result, "structured_content", None)
    if data is not None:
        return normalize(data)
    blocks = getattr(result, "content", None) or []
    texts = [block.text for block in blocks if isinstance(getattr(block, "text", None), str)]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return texts[0]
    if texts:
        return texts
    raise MCPResponseError("Tool returned no structured data or text content")


def _unwrap_result_envelope(value: Any) -> Any:
    # Some FastMCP versions wrap non-object results in {"result": value}.
    if isinstance(value, dict) and set(value) == {"result"}:
        return value["result"]
    return value


def _raise_application_error(tool_name: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    error = payload.get("error")
    success = payload.get("success")
    if error is True or (isinstance(error, str) and error.strip()) or success is False:
        message = payload.get("message") or (error if isinstance(error, str) else "Application-level tool failure")
        raise MCPToolError(
            tool_name,
            str(message),
            code=str(payload.get("code", "APPLICATION_ERROR")),
            payload=payload,
        )


def _make_fastmcp_client(url: str, token: str | None = None) -> Any:
    try:
        from fastmcp import Client
    except ImportError as exc:
        raise MCPConnectionError(
            "fastmcp is not installed. In the astroquery-mcp checkout run 'uv sync'."
        ) from exc
    if token:
        from fastmcp.client.auth import BearerAuth
        return Client(url, auth=BearerAuth(token))
    return Client(url)


class AstroqueryMCPClient:
    """Managed independent MCP session for one benchmark/client operation.

    Parameters
    ----------
    url: Streamable HTTP endpoint, by default localhost:8000/mcp.
    timeout: Per-operation limit in seconds; slow first-time introspection may
        require up to several minutes.
    session_factory: Dependency injection point for offline tests.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        token: str | None = None,
        timeout: float = 180.0,
        session_factory: Callable[[str], Any] | None = None,
    ) -> None:
        url = resolve_mcp_url(url)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("--mcp-url must be a full http(s) URL")
        if timeout <= 0:
            raise ValueError("--timeout must be positive")
        self.url = url
        self._token = resolve_mcp_token(token)
        self.timeout = timeout
        self._factory = session_factory
        self._session: Any = None
        self._connected = False

    async def __aenter__(self) -> "AstroqueryMCPClient":
        try:
            self._session = (self._factory(self.url) if self._factory is not None
                             else _make_fastmcp_client(self.url, self._token))
            async with asyncio.timeout(self.timeout):
                await self._session.__aenter__()
                self._connected = True
                await self._session.ping()
        except Exception as exc:
            if self._connected:
                try:
                    await self._session.__aexit__(type(exc), exc, exc.__traceback__)
                except Exception:
                    pass  # Preserve the original connection or ping failure.
            self._connected = False
            raise MCPConnectionError(
                f"Cannot connect to MCP server at {self.url}: {sanitize_mcp_error(exc, self._token)}"
            ) from exc
        return self

    async def __aexit__(self, typ: Any, value: Any, tb: Any) -> None:
        try:
            if self._connected:
                await self._session.__aexit__(typ, value, tb)
        finally:
            self._connected = False

    def _require_connection(self) -> Any:
        if not self._connected:
            raise MCPConnectionError("MCP session is not connected; use 'async with'")
        return self._session

    async def list_tools(self) -> list[dict[str, Any]]:
        session = self._require_connection()
        try:
            async with asyncio.timeout(self.timeout):
                tools = await session.list_tools()
        except Exception as exc:
            raise MCPTransportError(f"MCP tools/list failed at {self.url}: {sanitize_mcp_error(exc, self._token)}") from exc
        if not isinstance(tools, list):
            raise MCPResponseError("MCP tools/list did not return a list")
        result: list[dict[str, Any]] = []
        for tool in tools:
            name = getattr(tool, "name", None)
            if not isinstance(name, str) or not name:
                raise MCPResponseError("A discovered MCP tool has no valid name")
            schema = getattr(tool, "inputSchema", None)
            if schema is None:
                schema = getattr(tool, "input_schema", {})
            result.append({
                "name": name,
                "description": getattr(tool, "description", None) or "",
                "input_schema": normalize(schema),
            })
        return result

    async def call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        session = self._require_connection()
        arguments = arguments or {}
        try:
            async with asyncio.timeout(self.timeout):
                # Compatible with FastMCP 2.14+ and the existing server.
                result = await session.call_tool(tool_name, arguments, timeout=self.timeout)
        except Exception as exc:
            raise MCPTransportError(f"MCP tools/call '{tool_name}' failed at {self.url}: {sanitize_mcp_error(exc, self._token)}") from exc
        if getattr(result, "is_error", getattr(result, "isError", False)):
            try:
                payload = _unwrap_result_envelope(_extract_result(result))
            except MCPResponseError:
                payload = "MCP protocol tool failure"
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("error") or "MCP protocol tool failure")
                code = str(payload.get("code", "MCP_TOOL_ERROR"))
            else:
                message, code = str(payload), "MCP_TOOL_ERROR"
            raise MCPToolError(tool_name, message, code=code, payload=payload, protocol_error=True)
        payload = _unwrap_result_envelope(_extract_result(result))
        _raise_application_error(tool_name, payload)
        return payload

    async def list_modules(self) -> dict[str, Any]:
        result = await self.call("astroquery_list_modules")
        if not isinstance(result, dict) or not isinstance(result.get("modules"), list):
            raise MCPResponseError("astroquery_list_modules response is missing 'modules' list")
        return result

    async def list_functions(self, module_name: str = "simbad") -> dict[str, Any]:
        result = await self.call("astroquery_list_functions", {"module_name": module_name})
        if not isinstance(result, dict) or not isinstance(result.get("functions"), list):
            raise MCPResponseError("astroquery_list_functions response is missing 'functions' list")
        return result

    async def function_info(self, module_name: str, function_name: str) -> dict[str, Any]:
        result = await self.call(
            "astroquery_get_function_info",
            {"module_name": module_name, "function_name": function_name},
        )
        if not isinstance(result, dict) or not isinstance(result.get("parameters"), list):
            raise MCPResponseError("astroquery_get_function_info response missing 'parameters'")
        return result

    async def simbad_object(self, object_name: str = "M31") -> dict[str, Any]:
        """Narrow read-only live smoke check, not a general command executor."""
        if not object_name.strip():
            raise ValueError("SIMBAD object_name must not be empty")
        result = await self.call("astroquery_execute", {
            "module_name": "simbad",
            "function_name": "query_object",
            "params": {"object_name": object_name},
        })
        if not isinstance(result, dict) or result.get("success") is not True:
            raise MCPResponseError("SIMBAD query did not return success=true")
        data = result.get("result")
        if data is None or data == [] or data == {}:
            raise MCPResponseError("SIMBAD returned no object for the requested identifier")
        if isinstance(data, dict) and "data" in data and not data["data"]:
            raise MCPResponseError("SIMBAD returned an empty object table")
        return result
