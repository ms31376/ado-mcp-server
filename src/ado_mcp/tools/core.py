"""Connection, projects and teams."""

from __future__ import annotations

from .. import __version__
from ..app import REGISTERED, tool
from ..client import get, get_all, q, resolve_project
from ..config import CONFIG
from ..utils import person


@tool()
async def whoami() -> dict:
    """Check the connection: the signed-in user (owner of the PAT), server URL,
    access level of this extension and which tools are enabled."""
    try:
        data = await get("_apis/connectionData", api_version="")
        user = data.get("authenticatedUser") or {}
    except Exception:  # some scoped PATs cannot read connectionData
        user = {}
    return {
        "user": user.get("providerDisplayName") or user.get("customDisplayName"),
        "server": CONFIG.url,
        "default_project": CONFIG.project or None,
        "access_level": CONFIG.access_level,
        "extension_version": __version__,
        "enabled_tools": REGISTERED,
    }


@tool()
async def list_projects() -> list[dict]:
    """Projects the PAT can see."""
    projects = await get_all("_apis/projects", {"$top": 500})
    return [{"name": p.get("name"), "id": p.get("id"), "description": p.get("description"),
             "state": p.get("state"), "last_update": p.get("lastUpdateTime")} for p in projects]


@tool()
async def list_teams(project: str | None = None) -> list[dict]:
    """Teams of a project (team names are used by iteration and schedule tools)."""
    data = await get(f"_apis/projects/{q(resolve_project(project))}/teams", {"$top": 500})
    return [{"name": t.get("name"), "id": t.get("id"), "description": t.get("description")}
            for t in data.get("value", [])]


@tool()
async def list_team_members(team: str, project: str | None = None) -> list[dict]:
    """Members of a team."""
    data = await get(f"_apis/projects/{q(resolve_project(project))}/teams/{q(team)}/members")
    out = []
    for m in data.get("value", []):
        identity = m.get("identity", m)
        out.append({"name": person(identity), "unique_name": identity.get("uniqueName"),
                    "is_admin": m.get("isTeamAdmin", False)})
    return out
