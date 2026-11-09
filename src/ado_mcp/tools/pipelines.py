"""Pipelines (build definitions) and their runs."""

from __future__ import annotations

from ..app import tool
from ..client import get, project_path, raw
from ..utils import branch_ref, person, short_ref, tail


def _build_summary(b: dict) -> dict:
    return {"id": b.get("id"), "number": b.get("buildNumber"),
            "pipeline": (b.get("definition") or {}).get("name"),
            "status": b.get("status"), "result": b.get("result"),
            "branch": short_ref(b.get("sourceBranch")), "requested_for": person(b.get("requestedFor")),
            "queued": b.get("queueTime"), "started": b.get("startTime"), "finished": b.get("finishTime"),
            "url": ((b.get("_links") or {}).get("web") or {}).get("href")}


@tool()
async def list_pipelines(name_filter: str | None = None, project: str | None = None) -> list[dict]:
    """Pipelines (build definitions) of a project; name_filter supports * wildcards."""
    params = {"name": name_filter} if name_filter else {}
    data = await get(f"{project_path(project)}/_apis/build/definitions", params)
    return [{"id": d.get("id"), "name": d.get("name"), "folder": d.get("path"),
             "queue_status": d.get("queueStatus")} for d in data.get("value", [])]


@tool()
async def list_pipeline_runs(pipeline_id: int | None = None, branch: str | None = None,
                             status: str | None = None, result: str | None = None,
                             project: str | None = None, top: int = 30) -> list[dict]:
    """Recent runs (builds), newest first.
    status: inProgress, completed, notStarted, ... result: succeeded, failed, canceled, partiallySucceeded."""
    params: dict = {"$top": top, "queryOrder": "queueTimeDescending"}
    if pipeline_id:
        params["definitions"] = pipeline_id
    if branch:
        params["branchName"] = branch_ref(branch)
    if status:
        params["statusFilter"] = status
    if result:
        params["resultFilter"] = result
    data = await get(f"{project_path(project)}/_apis/build/builds", params)
    return [_build_summary(b) for b in data.get("value", [])]


async def _timeline(build_id: int, project: str | None) -> list[dict]:
    data = await get(f"{project_path(project)}/_apis/build/builds/{build_id}/timeline")
    return data.get("records", []) if data else []


@tool()
async def get_pipeline_run(build_id: int, project: str | None = None) -> dict:
    """Details of one run, including failed or warning steps with their error messages."""
    out = _build_summary(await get(f"{project_path(project)}/_apis/build/builds/{build_id}"))
    problems = []
    for rec in await _timeline(build_id, project):
        issues = [i.get("message") for i in rec.get("issues") or [] if i.get("message")]
        if rec.get("result") in ("failed", "canceled") or issues:
            problems.append({"type": rec.get("type"), "name": rec.get("name"),
                             "result": rec.get("result"), "issues": issues[:10],
                             "log_id": (rec.get("log") or {}).get("id")})
    out["problems"] = problems
    return out


@tool()
async def get_pipeline_log(build_id: int, log_id: int | None = None, tail_lines: int = 150,
                           project: str | None = None) -> list[dict]:
    """Log of a run. Without log_id, returns the last lines of every failed step.
    (log_id values come from get_pipeline_run.)"""
    if log_id is None:
        targets = [(r.get("name"), (r.get("log") or {}).get("id"))
                   for r in await _timeline(build_id, project)
                   if r.get("result") == "failed" and r.get("type") == "Task" and r.get("log")]
    else:
        targets = [(f"log {log_id}", log_id)]
    out = []
    for name, lid in targets[:5]:
        resp = await raw("GET", f"{project_path(project)}/_apis/build/builds/{build_id}/logs/{lid}")
        try:
            lines = resp.json().get("value", [])
        except ValueError:
            lines = resp.text.splitlines()
        out.append({"step": name, "log_id": lid, "lines": tail(lines, tail_lines)})
    return out
