"""HTTP client for the Azure DevOps REST API (PAT authentication)."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote

import httpx

from .config import CONFIG


class AdoError(RuntimeError):
    """An error with a message meant to be shown to the user."""


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        missing = [n for n, v in (("ADO_URL", CONFIG.url), ("ADO_PAT", CONFIG.pat)) if not v]
        if missing:
            raise AdoError(f"Missing configuration: {', '.join(missing)}")
        token = base64.b64encode(f":{CONFIG.pat}".encode()).decode()
        _client = httpx.AsyncClient(
            base_url=CONFIG.url + "/",
            headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
            verify=CONFIG.ca_bundle or CONFIG.verify_ssl,
            timeout=CONFIG.timeout,
            trust_env=not CONFIG.ignore_proxy,
        )
    return _client


def q(value: str) -> str:
    """URL-encode one path segment."""
    return quote(value, safe="")


def resolve_project(project: str | None) -> str:
    name = project or CONFIG.project
    if not name:
        raise AdoError("No project given and no default project configured. "
                       "Call list_projects and pass `project`.")
    return name


def project_path(project: str | None) -> str:
    return q(resolve_project(project))


def team_path(project: str | None, team: str | None) -> str:
    name = resolve_project(project)
    team_name = team or CONFIG.team or f"{name} Team"
    return f"{q(name)}/{q(team_name)}"


async def raw(method: str, path: str, *, params: dict | None = None, body: Any = None,
              content_type: str | None = None, api_version: str | None = None) -> httpx.Response:
    params = dict(params or {})
    version = CONFIG.api_version if api_version is None else api_version
    if version:
        params.setdefault("api-version", version)
    kwargs: dict[str, Any] = {}
    if body is not None:
        if content_type:
            kwargs["content"] = json.dumps(body).encode("utf-8")
            kwargs["headers"] = {"Content-Type": content_type}
        else:
            kwargs["json"] = body
    try:
        resp = await get_client().request(method, path, params=params, **kwargs)
    except httpx.TimeoutException as exc:
        raise AdoError(f"Timed out talking to {CONFIG.url}. Check network/VPN; if a system proxy "
                       "is in the way, enable 'Ignore system proxy'.") from exc
    except httpx.ConnectError as exc:
        raise AdoError(f"Cannot connect to {CONFIG.url}: {exc}") from exc

    if resp.status_code == 401:
        raise AdoError("401 Unauthorized: the PAT is invalid, expired, or lacks a required scope.")
    if resp.status_code == 403:
        raise AdoError("403 Forbidden: your account or PAT has no permission for this.")
    if resp.status_code == 203 or "text/html" in resp.headers.get("content-type", ""):
        raise AdoError("The server returned an HTML page (usually a sign-in page). "
                       "Check the PAT and the server URL.")
    if resp.is_error:
        try:
            message = resp.json().get("message", resp.text)
        except ValueError:
            message = resp.text
        raise AdoError(f"HTTP {resp.status_code} on {path}: {str(message)[:500]}")
    return resp


async def get(path: str, params: dict | None = None, **kwargs: Any) -> Any:
    return (await raw("GET", path, params=params, **kwargs)).json()


async def send(method: str, path: str, body: Any = None, params: dict | None = None,
               **kwargs: Any) -> Any:
    resp = await raw(method, path, params=params, body=body, **kwargs)
    return resp.json() if resp.content else None


async def get_all(path: str, params: dict | None = None, limit: int = 1000, **kwargs: Any) -> list:
    """GET a list, following x-ms-continuationtoken paging."""
    params = dict(params or {})
    items: list = []
    while True:
        resp = await raw("GET", path, params=params, **kwargs)
        data = resp.json()
        items.extend(data.get("value", []) if isinstance(data, dict) else data)
        token = resp.headers.get("x-ms-continuationtoken")
        if not token or len(items) >= limit:
            return items[:limit]
        params["continuationToken"] = token
