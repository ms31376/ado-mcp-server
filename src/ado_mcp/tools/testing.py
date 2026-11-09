"""Test management: test cases, plans, suites, results."""

from __future__ import annotations

from ..app import tool
from ..client import AdoError, get_all, project_path
from ..utils import html_to_text, parse_steps, person
from .workitems import build_where, fetch_items, run_wiql, summarize

TC_EXTRA = {"Microsoft.VSTS.TCM.AutomationStatus": "automation_status"}


@tool()
async def search_test_cases(text: str = "", state: str | None = None,
                            assigned_to: str | None = None, tags: str | None = None,
                            area_path: str | None = None, iteration_path: str | None = None,
                            project: str | None = None, top: int = 100) -> list[dict]:
    """Search Test Case work items by title text, state, owner ("@me"), tags, area or iteration."""
    where = build_where(text, ["Test Case"], state, assigned_to, None, tags, iteration_path, area_path)
    ids = await run_wiql(f"SELECT [System.Id] FROM WorkItems WHERE {where} ORDER BY [System.Id] DESC",
                         top, project)
    return [summarize(wi, TC_EXTRA) for wi in await fetch_items(ids)]


@tool()
async def get_test_case(test_case_id: int) -> dict:
    """One test case with its parsed steps (action / expected result)."""
    items = await fetch_items([test_case_id])
    if not items:
        raise AdoError(f"Test case {test_case_id} not found.")
    fields = items[0].get("fields", {})
    out = summarize(items[0], TC_EXTRA)
    out["description"] = html_to_text(fields.get("System.Description"))
    out["steps"] = parse_steps(fields.get("Microsoft.VSTS.TCM.Steps"))
    return out


@tool()
async def list_test_plans(active_only: bool = True, project: str | None = None) -> list[dict]:
    """Test plans of a project."""
    plans = await get_all(f"{project_path(project)}/_apis/testplan/plans",
                          {"filterActivePlans": str(active_only).lower()})
    return [{"id": p.get("id"), "name": p.get("name"), "state": p.get("state"),
             "iteration": p.get("iteration"), "start_date": p.get("startDate"),
             "end_date": p.get("endDate"), "owner": person(p.get("owner"))} for p in plans]


@tool()
async def list_test_suites(plan_id: int, project: str | None = None) -> list[dict]:
    """Suites of a test plan, with parent suite ids to rebuild the tree."""
    suites = await get_all(f"{project_path(project)}/_apis/testplan/Plans/{plan_id}/suites")
    return [{"id": s.get("id"), "name": s.get("name"), "type": s.get("suiteType"),
             "parent_id": (s.get("parentSuite") or {}).get("id")} for s in suites]


@tool()
async def get_suite_test_results(plan_id: int, suite_id: int, project: str | None = None) -> dict:
    """Test points of a suite: each test case per configuration with tester and last outcome
    (Passed / Failed / Blocked / NotApplicable / NotRun), plus a summary count."""
    points = await get_all(
        f"{project_path(project)}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestPoint")
    rows, summary = [], {}
    for p in points:
        results = p.get("results") or {}
        outcome = results.get("outcome") or "NotRun"
        if outcome.lower() == "unspecified":
            outcome = "NotRun"
        summary[outcome] = summary.get(outcome, 0) + 1
        last = results.get("lastResultDetails") or {}
        ref = p.get("testCaseReference") or {}
        rows.append({"test_case_id": ref.get("id"), "test_case": ref.get("name"),
                     "configuration": (p.get("configuration") or {}).get("name"),
                     "tester": person(p.get("tester")), "outcome": outcome,
                     "last_run": last.get("dateCompleted"), "run_by": person(last.get("runBy"))})
    return {"summary": summary, "points": rows}
