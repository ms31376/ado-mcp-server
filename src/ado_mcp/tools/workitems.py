"""Work items: search, WIQL, details, history, comments."""

from __future__ import annotations

from typing import Any

from ..app import tool
from ..client import AdoError, get, project_path, send
from ..utils import html_to_text, person, wiql_str

MAX_TOP = 1000

FIELD_MAP = {
    "System.WorkItemType": "type",
    "System.Title": "title",
    "System.State": "state",
    "System.AssignedTo": "assigned_to",
    "System.TeamProject": "project",
    "System.IterationPath": "iteration",
    "System.AreaPath": "area",
    "System.Tags": "tags",
    "System.ChangedDate": "changed",
    "Microsoft.VSTS.Common.Priority": "priority",
}

SCHEDULE_MAP = {
    "Microsoft.VSTS.Scheduling.StartDate": "start_date",
    "Microsoft.VSTS.Scheduling.TargetDate": "target_date",
    "Microsoft.VSTS.Scheduling.DueDate": "due_date",
    "Microsoft.VSTS.Scheduling.OriginalEstimate": "original_estimate",
    "Microsoft.VSTS.Scheduling.RemainingWork": "remaining_work",
    "Microsoft.VSTS.Scheduling.CompletedWork": "completed_work",
}

IDENTITY_FIELDS = {"System.AssignedTo", "System.CreatedBy", "System.ChangedBy"}

# Fields that change on every save and add only noise to history.
NOISY_FIELDS = {"System.Rev", "System.ChangedDate", "System.RevisedDate", "System.Watermark",
                "System.AuthorizedDate", "System.AuthorizedAs", "System.ChangedBy",
                "System.PersonId", "System.CommentCount"}


def summarize(wi: dict, extra: dict[str, str] | None = None) -> dict:
    fields = wi.get("fields", {})
    out: dict[str, Any] = {"id": wi.get("id")}
    for ref, key in {**FIELD_MAP, **(extra or {})}.items():
        if ref in fields:
            out[key] = person(fields[ref]) if ref in IDENTITY_FIELDS else fields[ref]
    return out


async def run_wiql(query: str, top: int, project: str | None) -> list[int]:
    data = await send("POST", f"{project_path(project)}/_apis/wit/wiql", {"query": query},
                      params={"$top": max(1, min(top, MAX_TOP))})
    if data.get("workItems") is not None:
        return [w["id"] for w in data["workItems"]]
    ids: list[int] = []
    for rel in data.get("workItemRelations") or []:
        target = (rel.get("target") or {}).get("id")
        if target and target not in ids:
            ids.append(target)
    return ids


async def fetch_items(ids: list[int], expand: str | None = None) -> list[dict]:
    """Fetch work items (all fields) in batches of 200, keeping the input order."""
    found: dict[int, dict] = {}
    for i in range(0, len(ids), 200):
        params = {"ids": ",".join(map(str, ids[i:i + 200])), "errorPolicy": "omit"}
        if expand:
            params["$expand"] = expand
        data = await get("_apis/wit/workitems", params)
        for wi in data.get("value", []):
            if wi:
                found[wi["id"]] = wi
    return [found[i] for i in ids if i in found]


def _person_clause(field: str, value: str) -> str:
    if value.strip().lower() == "@me":
        return f"[{field}] = @me"
    return f"[{field}] CONTAINS '{wiql_str(value)}'"


def build_where(text: str = "", types: list[str] | None = None, state: str | None = None,
                assigned_to: str | None = None, created_by: str | None = None,
                tags: str | None = None, iteration_path: str | None = None,
                area_path: str | None = None, priority: int | None = None,
                changed_in_last_days: int | None = None,
                exclude_states: tuple[str, ...] = ()) -> str:
    clauses = ["[System.TeamProject] = @project"]
    if text:
        if text.strip().isdigit():
            clauses.append(f"([System.Id] = {int(text)} OR [System.Title] CONTAINS '{wiql_str(text)}')")
        else:
            clauses.append(f"[System.Title] CONTAINS '{wiql_str(text)}'")
    if types:
        clauses.append("[System.WorkItemType] IN (" + ", ".join(f"'{wiql_str(t)}'" for t in types) + ")")
    if state:
        clauses.append(f"[System.State] = '{wiql_str(state)}'")
    if exclude_states:
        clauses.append("[System.State] NOT IN (" + ", ".join(f"'{s}'" for s in exclude_states) + ")")
    if assigned_to:
        clauses.append(_person_clause("System.AssignedTo", assigned_to))
    if created_by:
        clauses.append(_person_clause("System.CreatedBy", created_by))
    if tags:
        for tag in (t.strip() for t in tags.split(";")):
            if tag:
                clauses.append(f"[System.Tags] CONTAINS '{wiql_str(tag)}'")
    if iteration_path:
        clauses.append(f"[System.IterationPath] UNDER '{wiql_str(iteration_path)}'")
    if area_path:
        clauses.append(f"[System.AreaPath] UNDER '{wiql_str(area_path)}'")
    if priority is not None:
        clauses.append(f"[Microsoft.VSTS.Common.Priority] = {int(priority)}")
    if changed_in_last_days:
        clauses.append(f"[System.ChangedDate] >= @today - {int(changed_in_last_days)}")
    return " AND ".join(clauses)


def split_types(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [t.strip() for t in value.split(",") if t.strip()]


@tool()
async def list_work_item_types(project: str | None = None) -> list[dict]:
    """Work item types of a project (Bug, Task, User Story, Feature, Test Case, ...)."""
    data = await get(f"{project_path(project)}/_apis/wit/workitemtypes")
    return [{"name": t.get("name"), "description": t.get("description")}
            for t in data.get("value", []) if not t.get("isDisabled")]


@tool()
async def search_work_items(text: str = "", work_item_type: str | None = None,
                            state: str | None = None, assigned_to: str | None = None,
                            created_by: str | None = None, tags: str | None = None,
                            iteration_path: str | None = None, area_path: str | None = None,
                            priority: int | None = None, changed_in_last_days: int | None = None,
                            project: str | None = None, top: int = 100) -> list[dict]:
    """Search work items of any type.

    text: matches the title, or the ID if numeric.
    work_item_type: one type or several separated by commas, e.g. "Bug, Task".
    assigned_to / created_by: part of a name, or "@me".
    tags: one tag or several separated by ";" (all must match).
    iteration_path / area_path: includes children, e.g. "MyProject\\Sprint 12".
    """
    where = build_where(text, split_types(work_item_type), state, assigned_to, created_by, tags,
                        iteration_path, area_path, priority, changed_in_last_days)
    ids = await run_wiql(f"SELECT [System.Id] FROM WorkItems WHERE {where} "
                         "ORDER BY [System.ChangedDate] DESC", top, project)
    return [summarize(wi) for wi in await fetch_items(ids)]


@tool()
async def query_wiql(wiql: str, project: str | None = None, top: int = 200) -> list[dict]:
    """Run a read-only WIQL query (SELECT ... FROM WorkItems / WorkItemLinks ...)
    for searches the other tools cannot express. Returns work item summaries."""
    if not wiql.strip().lower().startswith("select"):
        raise AdoError("Only SELECT queries are allowed.")
    ids = await run_wiql(wiql, top, project)
    return [summarize(wi) for wi in await fetch_items(ids)]


@tool()
async def get_work_item(work_item_id: int) -> dict:
    """Full details of one work item: description, repro steps, acceptance criteria,
    scheduling fields and links (parent, children, related, tested by, commits, PRs)."""
    data = await get(f"_apis/wit/workitems/{work_item_id}", {"$expand": "relations"})
    fields = data.get("fields", {})
    out = summarize(data, SCHEDULE_MAP)
    for ref, key in (("System.Description", "description"),
                     ("Microsoft.VSTS.TCM.ReproSteps", "repro_steps"),
                     ("Microsoft.VSTS.Common.AcceptanceCriteria", "acceptance_criteria"),
                     ("Microsoft.VSTS.TCM.SystemInfo", "system_info")):
        if fields.get(ref):
            out[key] = html_to_text(fields[ref])
    out["created_by"] = person(fields.get("System.CreatedBy"))
    out["created"] = fields.get("System.CreatedDate")
    links = []
    for rel in data.get("relations") or []:
        name = (rel.get("attributes") or {}).get("name") or rel.get("rel")
        url = rel.get("url", "")
        if "/workItems/" in url:
            links.append({"relation": name, "work_item_id": int(url.rstrip("/").rsplit("/", 1)[-1])})
        elif rel.get("rel") == "ArtifactLink":
            links.append({"relation": name, "artifact": url})
        elif rel.get("rel") == "Hyperlink":
            links.append({"relation": "Hyperlink", "url": url})
    if links:
        out["links"] = links
    return out


@tool()
async def get_work_item_history(work_item_id: int, top: int = 50) -> list[dict]:
    """Change history of a work item: who changed which fields, from what to what."""
    data = await get(f"_apis/wit/workItems/{work_item_id}/updates", {"$top": top})
    out = []
    for upd in data.get("value", []):
        changes = {}
        for ref, change in (upd.get("fields") or {}).items():
            if ref in NOISY_FIELDS:
                continue
            old, new = change.get("oldValue"), change.get("newValue")
            if ref in IDENTITY_FIELDS:
                old, new = person(old), person(new)
            elif isinstance(new, str) and "<" in new:
                old, new = html_to_text(old) if isinstance(old, str) else old, html_to_text(new)
            changes[ref.split(".")[-1]] = {"from": old, "to": new}
        if changes or upd.get("relations"):
            entry = {"rev": upd.get("rev"), "by": person(upd.get("revisedBy")),
                     "date": (upd.get("fields") or {}).get("System.ChangedDate", {}).get("newValue")}
            if changes:
                entry["changes"] = changes
            if upd.get("relations"):
                entry["links_changed"] = True
            out.append(entry)
    return out


@tool()
async def get_comments(work_item_id: int, top: int = 50) -> list[dict]:
    """Comments (Discussion) of a work item."""
    project = (await get(f"_apis/wit/workitems/{work_item_id}",
                         {"fields": "System.TeamProject"}))["fields"]["System.TeamProject"]
    data = await get(f"{project_path(project)}/_apis/wit/workItems/{work_item_id}/comments",
                     {"$top": top}, api_version=_preview("3"))
    return [{"id": c.get("id"), "author": person(c.get("createdBy")),
             "date": c.get("createdDate"), "text": html_to_text(c.get("text"))}
            for c in data.get("comments", [])]


def _preview(n: str) -> str:
    from ..config import CONFIG
    return f"{CONFIG.api_version}-preview.{n}"
