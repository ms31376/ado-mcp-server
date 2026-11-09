"""Configuration from environment variables (set by the .mcpb install form or your MCP client)."""

from __future__ import annotations

import os
from dataclasses import dataclass

ACCESS_LEVELS = ("read", "write", "full")


def _str(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    # Hosts may pass an unresolved placeholder such as "${user_config.x}" for empty optional fields.
    if not value or value.startswith("${"):
        return default
    return value


def _bool(name: str, default: bool) -> bool:
    value = _str(name).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    url: str
    pat: str
    project: str
    team: str
    api_version: str
    access_level: str
    ca_bundle: str
    verify_ssl: bool
    ignore_proxy: bool
    timeout: float


def load() -> Config:
    level = _str("ADO_ACCESS_LEVEL", "read").lower()
    if level not in ACCESS_LEVELS:
        level = "read"
    try:
        timeout = float(_str("ADO_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0
    return Config(
        url=(_str("ADO_URL") or _str("ADO_COLLECTION_URL")).rstrip("/"),
        pat=_str("ADO_PAT"),
        project=_str("ADO_PROJECT"),
        team=_str("ADO_TEAM"),
        api_version=_str("ADO_API_VERSION", "7.0"),
        access_level=level,
        ca_bundle=_str("ADO_CA_BUNDLE"),
        verify_ssl=_bool("ADO_VERIFY_SSL", True),
        ignore_proxy=_bool("ADO_IGNORE_PROXY", False),
        timeout=timeout,
    )


CONFIG = load()
