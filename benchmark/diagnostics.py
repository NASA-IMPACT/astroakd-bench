"""Structured, reproducible connection qualification for the local MCP server."""

from __future__ import annotations
from .mcp_config import resolve_mcp_url

from datetime import datetime, timezone
from typing import Any, Callable

from . import __version__, DEFAULT_MCP_URL
from .client import AstroqueryMCPClient, CORE_TOOLS


def _check(name: str, ok: bool, *, details: Any = None, error: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "status": "PASS" if ok else "FAIL"}
    if details is not None:
        entry["details"] = details
    if error is not None:
        entry["error"] = error
    return entry


async def doctor(
    url: str | None = None,
    *,
    timeout: float = 180.0,
    fast: bool = False,
    smoke: bool = False,
    object_name: str = "M31",
    session_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Qualify transport, MCP tools, module discovery, and optional SIMBAD execution.

    The slow function-introspection check can be skipped with ``fast=True``.
    The upstream archive smoke check runs only with ``smoke=True``.
    """
    url = resolve_mcp_url(url)
    report: dict[str, Any] = {
        "milestone": "0.1.0 — LOCAL_MCP_CONNECTION",
        "benchmark_version": __version__,
        "endpoint": url,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {"timeout_seconds": timeout, "fast": fast, "smoke": smoke},
        "checks": [],
    }
    checks = report["checks"]
    try:
        async with AstroqueryMCPClient(
            url, timeout=timeout, session_factory=session_factory
        ) as client:
            checks.append(_check("connection_and_ping", True))
            try:
                tools = await client.list_tools()
                available = {tool["name"] for tool in tools}
                missing = sorted(CORE_TOOLS - available)
                checks.append(_check("mcp_tool_catalog", not missing, details={
                    "count": len(tools), "names": sorted(available), "missing": missing
                }))
                if missing:
                    raise RuntimeError(f"Missing required MCP tools: {', '.join(missing)}")
            except Exception as exc:
                if not any(item["name"] == "mcp_tool_catalog" for item in checks):
                    checks.append(_check("mcp_tool_catalog", False, error=str(exc)))
                raise

            modules = await client.list_modules()
            simbad = next((m for m in modules["modules"] if m.get("name") == "simbad"), None)
            ok = simbad is not None and simbad.get("available") is True
            checks.append(_check("simbad_module", ok, details={
                "reported_count": modules.get("module_count"),
                "actual_count": len(modules["modules"]),
                "simbad": simbad,
            }))
            if not ok:
                raise RuntimeError("SIMBAD is missing or unavailable on the server")

            if not fast:
                functions = await client.list_functions("simbad")
                query_object = next((f for f in functions["functions"]
                    if f.get("method") == "query_object"), None)
                checks.append(_check("simbad_function_discovery", query_object is not None,
                    details={"function_count": len(functions["functions"]),
                             "query_object": query_object is not None}))
                if query_object is None:
                    raise RuntimeError("SIMBAD query_object missing from discovered functions")
                info = await client.function_info("simbad", "query_object")
                parameter_names = [p.get("name") for p in info["parameters"]]
                ok = "object_name" in parameter_names
                checks.append(_check("simbad_signature", ok,
                    details={"method": info.get("method"), "parameters": parameter_names}))
                if not ok:
                    raise RuntimeError("SIMBAD query_object does not advertise object_name")
            else:
                checks.append({"name": "simbad_introspection", "status": "SKIP",
                               "details": "--fast requested"})

            if smoke:
                result = await client.simbad_object(object_name)
                payload = result["result"]
                if isinstance(payload, dict):
                    row_count = payload.get("row_count")
                    if row_count is None and isinstance(payload.get("data"), list):
                        row_count = len(payload["data"])
                else:
                    row_count = len(payload) if isinstance(payload, list) else None
                checks.append(_check("live_simbad_query", True, details={
                    "object_name": object_name,
                    "result_type": type(payload).__name__,
                    "row_count": row_count,
                }))
            else:
                checks.append({"name": "live_simbad_query", "status": "SKIP",
                               "details": "--smoke was not requested"})
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if not checks or checks[-1]["status"] != "FAIL":
            checks.append(_check("interrupted_at", False, error=str(exc)))

    report["status"] = "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS"
    return report
