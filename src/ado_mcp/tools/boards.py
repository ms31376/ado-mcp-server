"""Boards: iterations and task scheduling."""

from __future__ import annotations

from datetime import datetime, timezone

from ..app import tool
from ..client import AdoError, get, team_path
from ..utils import parse_date
from .workitems import SCHEDULE_MAP, build_where, fetch_items, run_wiql, summarize, split_types

CLOSED_STATES = ("Closed", "Done", "Removed", "Resolved")


async def _iterations(project: str | None, team: str | None) -> list[dict]:
    data = await get(f"{team_path(project, team)}/_apis/work/teamsettings/iterations")
    out = []
    for it in data.get("value", []):
        attrs = it.get("attributes") or {}
        out.append({"id": it.get("id"), "name": it.get("name"), "path": it.get("path"),
                    "start_date": attrs.get("startDate"), "finish_date": attrs.get("finishDate"),
                    "timeframe": attrs.get("timeFrame")})
    return out


@tool()
async def list_iterations(timeframe: str | None = None, project: str | None = None,
                          team: str | None = None) -> list[dict]:
    """Team iterations (sprints) with start/finish dates.
    timeframe: optional filter "past", "current" or "future"."""
    its = await _iterations(project, team)
    if timeframe:
        its = [i for i in its if str(i["timeframe"]).lower() == timeframe.lower()]
    return its


@tool()
async def get_task_schedule(iteration_path: str | None = None, current_iteration: bool = False,
                            assigned_to: str | None = None, include_closed: bool = False,
                            work_item_type: str = "Task", project: str | None = None,
                            team: str | None = None, top: int = 300) -> dict:
    """Scheduling view: start/target dates, estimates, remaining work, overdue flags
    and remaining work per person.

    current_iteration=True uses the team's current sprint.
    work_item_type: one or several separated by commas, e.g. "Task, Bug".
    """
    if current_iteration:
        current = [i for i in await _iterations(project, team)
                   if str(i["timeframe"]).lower() == "current"]
        if not current:
            raise AdoError("The team has no current iteration.")
        iteration_path = current[0]["path"]
    where = build_where(types=split_types(work_item_type), assigned_to=assigned_to,
                        iteration_path=iteration_path,
                        exclude_states=() if include_closed else CLOSED_STATES)
    ids = await run_wiql(f"SELECT [System.Id] FROM WorkItems WHERE {where}", top, project)
    items = [summarize(wi, SCHEDULE_MAP) for wi in await fetch_items(ids)]

    now = datetime.now(timezone.utc)
    per_person: dict[str, float] = {}
    without_dates = 0
    for it in items:
        deadline = parse_date(it.get("target_date") or it.get("due_date"))
        if not deadline:
            without_dates += 1
        it["overdue"] = bool(deadline and deadline < now and it.get("state") not in CLOSED_STATES)
        who = it.get("assigned_to") or "Unassigned"
        per_person[who] = per_person.get(who, 0) + float(it.get("remaining_work") or 0)

    far = datetime.max.replace(tzinfo=timezone.utc)
    items.sort(key=lambda x: parse_date(x.get("target_date") or x.get("due_date")) or far)
    return {"iteration": iteration_path, "count": len(items),
            "overdue_count": sum(1 for i in items if i["overdue"]),
            "without_target_date": without_dates,
            "remaining_work_by_person": per_person, "items": items}
