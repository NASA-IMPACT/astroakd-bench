"""MCP address and bearer-token selection. Credentials never enter reports or journals."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
import os
from urllib.parse import urlsplit

LOCAL_MCP_URL = "http://127.0.0.1:8000/mcp"
_TOKEN_UNSET = object()
_token_override: ContextVar[object] = ContextVar("astroakd_bench_mcp_token", default=_TOKEN_UNSET)


def resolve_mcp_url(explicit: str | None = None) -> str:
    """Priority: explicit CLI/API value > ASTROAKD_MCP_URL > local default.

    An empty explicit string is treated like absence; an empty environment
    ASTROAKD_MCP_URL is also treated as unset. Do not allow URL-embedded credentials.
    """
    url = (explicit or "").strip() or os.getenv("ASTROAKD_MCP_URL", "").strip() or LOCAL_MCP_URL
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("MCP endpoint must be a full http(s) URL without embedded credentials")
    return url


def resolve_mcp_token(explicit: str | None = None) -> str | None:
    """Empty strings disable bearer authentication, including when set in env."""
    if explicit is not None:
        value = explicit
    else:
        override = _token_override.get()
        value = os.getenv("ASTROAKD_MCP_TOKEN", "") if override is _TOKEN_UNSET else override
    if not isinstance(value, str):
        raise ValueError("MCP token must be a string")
    return value.strip() or None


@contextmanager
def mcp_token_scope(explicit: str | None):
    """Keep a CLI credential local to its async command; never mutate os.environ."""
    handle = _token_override.set(explicit if explicit is not None else _TOKEN_UNSET)
    try:
        yield
    finally:
        _token_override.reset(handle)


def sanitize_mcp_error(message: object, token: str | None = None) -> str:
    """Defensively scrub the configured secret from upstream exception text."""
    result = str(message)
    secret = resolve_mcp_token(token)
    return result.replace(secret, "[REDACTED]") if secret else result
