"""The FastMCP app and the access-level aware @tool decorator."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import CONFIG

mcp = FastMCP("azure-devops")

_RANK = {"read": 0, "write": 1, "full": 2}
REGISTERED: dict[str, str] = {}


def tool(level: str = "read"):
    """Register a tool only if the configured access level allows it.

    read  -> always registered, marked read-only
    write -> creates / changes data (needs access level "write" or "full")
    full  -> permanent or destructive actions (needs access level "full")
    Tools above the access level are never registered, so the model cannot see or call them.
    """
    def decorator(fn):
        if _RANK[level] <= _RANK[CONFIG.access_level]:
            annotations = ToolAnnotations(
                readOnlyHint=(level == "read"),
                destructiveHint=(level == "full"),
            )
            mcp.tool(annotations=annotations)(fn)
            REGISTERED[fn.__name__] = level
        return fn
    return decorator
