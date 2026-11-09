"""Write tools. Every one of them works in two steps:

1. preview=True (default): nothing is changed; the tool returns exactly what would happen.
2. preview=False: the change is made. Call this only after the user approved the preview.

Tools are registered only when the access level allows it (see app.tool).
"""

from __future__ import annotations

from typing import Any

from ..app import tool
from ..client import CONFIG, AdoError, get, project_path, q, raw, resolve_project, send
from ..utils import branch_ref, build_steps, person, text_to_html
from .workitems import IDENTITY_FIELDS, fetch_items

NEXT_STEP = ("Nothing was changed. Show this preview to the user and call again with "
             "preview=False only after they explicitly approve it.")

# Friendly names accepted in `fields`, mapped to reference names.
FIELD_ALIASES = {
    "title": "System.Title",
    "description": "System.Description",
    "state": "System.State",
    "reason": "System.Reason",
    "assigned_to": "System.AssignedTo",
    "area_path": "System.AreaPath",
    "iteration_path": "System.IterationPath",
    "tags": "System.Tags",
    "priority": "Microsoft.VSTS.Common.Priority",
    "severity": "Microsoft.VSTS.Common.Severity",
    "repro_steps": "Microsoft.VSTS.TCM.ReproSteps",
    "system_info": "Microsoft.VSTS.TCM.SystemInfo",
    "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
    "story_points": "Microsoft.VSTS.Scheduling.StoryPoints",
    "effort": "Microsoft.VSTS.Scheduling.Effort",
    "original_estimate": "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "remaining_work": "Microsoft.VSTS.Scheduling.RemainingWork",
    "completed_work": "Microsoft.VSTS.Scheduling.CompletedWork",
    "start_date": "Microsoft.VSTS.Scheduling.StartDate",
    "target_date": "Microsoft.VSTS.Scheduling.TargetDate",
    "due_date": "Microsoft.VSTS.Scheduling.DueDate",
}

HTML_FIELDS = {"System.Description", "Microsoft.VSTS.TCM.ReproSteps",
               "Microsoft.VSTS.TCM.SystemInfo", "Microsoft.VSTS.Common.AcceptanceCriteria"}

LINK_TYPES = {
    "parent": "System.LinkTypes.Hierarchy-Reverse",
    "child": "System.LinkTypes.Hierarchy-Forward",
    "related": "System.LinkTypes.Related",
    "tested_by": "Microsoft.VSTS.Common.TestedBy-Forward",
    "tests": "Microsoft.VSTS.Common.TestedBy-Reverse",
    "duplicate": "System.LinkTypes.Duplicate-Forward",
    "duplicate_of": "System.LinkTypes.Duplicate-Reverse",
    "successor": "System.LinkTypes.Dependency-Forward",
    "predecessor": "System.LinkTypes.Dependency-Reverse",
}

PATCH = "application/json-patch+json"


def _ref(name: str) -> str:
    if name in FIELD_ALIASES:
        return FIELD_ALIASES[name]
    if "." in name:
        return name
    raise AdoError(f"Unknown field '{name}'. Use one of {sorted(FIELD_ALIASES)} "
                   "or a reference name such as 'Custom.MyField'.")


def _normalize(fields: dict[str, Any] | None) -> dict[str, Any]:
    return {_ref(k): v for k, v in (fields or {}).items() if v is not None}


def _wire_value(ref: str, value: Any) -> Any:
    if ref in HTML_FIELDS and isinstance(value, str):
        return text_to_html(value)
    return value


def _field_ops(fields: dict[str, Any]) -> list[dict]:
    return [{"op": "add", "path": f"/fields/{ref}", "value": _wire_value(ref, v)}
            for ref, v in fields.items()]


def _link_op(link_type: str, target_id: int, comment: str | None = None) -> dict:
    if link_type not in LINK_TYPES:
        raise AdoError(f"Unknown link type '{link_type}'. Use one of {sorted(LINK_TYPES)}.")
    value: dict[str, Any] = {"rel": LINK_TYPES[link_type],
                             "url": f"{CONFIG.url}/_apis/wit/workItems/{target_id}"}
    if comment:
        value["attributes"] = {"comment": comment}
    return {"op": "add", "path": "/relations/-", "value": value}


def _web_url(project: str, work_item_id: int) -> str:
    return f"{CONFIG.url}/{q(project)}/_workitems/edit/{work_item_id}"


async def _get_item(work_item_id: int) -> dict:
    items = await fetch_items([work_item_id])
    if not items:
        raise AdoError(f"Work item {work_item_id} not found.")
    return items[0]


async def _patch(work_item_id: int, ops: list[dict]) -> dict:
    resp = await raw("PATCH", f"_apis/wit/workitems/{work_item_id}", body=ops, content_type=PATCH)
    return resp.json()


async def _create(project: str | None, work_item_type: str, ops: list[dict]) -> dict:
    resp = await raw("POST", f"{project_path(project)}/_apis/wit/workitems/${q(work_item_type)}",
                     body=ops, content_type=PATCH)
    return resp.json()


def _display(ref: str, value: Any) -> Any:
    return person(value) if ref in IDENTITY_FIELDS else value


# ----------------------------------------------------------------- work items


@tool("write")
async def create_work_item(work_item_type: str, title: str, fields: dict[str, Any] | None = None,
                           parent_id: int | None = None, project: str | None = None,
                           preview: bool = True) -> dict:
    """WRITE: create a work item of any type (Bug, Task, User Story, Feature, ...).

    fields: friendly names (description, assigned_to, area_path, iteration_path, tags, priority,
    severity, repro_steps, acceptance_criteria, remaining_work, target_date, ...) or reference
    names. Plain text is converted to HTML where needed.
    parent_id: link the new item under this parent.
    preview=True (default) changes nothing and shows what would be created.
    """
    values = {"System.Title": title, **_normalize(fields)}
    name = resolve_project(project)
    if preview:
        return {"preview": True, "action": "create work item", "project": name,
                "type": work_item_type, "fields": values, "parent_id": parent_id,
                "next_step": NEXT_STEP}
    ops = _field_ops(values)
    if parent_id:
        ops.append(_link_op("parent", parent_id))
    wi = await _create(name, work_item_type, ops)
    return {"created": wi["id"], "type": work_item_type, "title": title,
            "url": _web_url(name, wi["id"])}


@tool("write")
async def create_bug(title: str, repro_steps: str, expected_result: str | None = None,
                     actual_result: str | None = None, severity: str | None = None,
                     priority: int | None = None, assigned_to: str | None = None,
                     tags: str | None = None, iteration_path: str | None = None,
                     found_by_test_case_id: int | None = None, project: str | None = None,
                     preview: bool = True) -> dict:
    """WRITE: create a Bug, optionally linked to the test case that found it (Tested By).

    severity: e.g. "1 - Critical", "2 - High", "3 - Medium", "4 - Low".
    preview=True (default) changes nothing and shows what would be created.
    """
    body = repro_steps
    if expected_result:
        body += f"\n\nExpected result:\n{expected_result}"
    if actual_result:
        body += f"\n\nActual result:\n{actual_result}"
    values = _normalize({"title": title, "repro_steps": body, "severity": severity,
                         "priority": priority, "assigned_to": assigned_to, "tags": tags,
                         "iteration_path": iteration_path})
    name = resolve_project(project)
    if preview:
        return {"preview": True, "action": "create bug", "project": name, "fields": values,
                "linked_test_case": found_by_test_case_id, "next_step": NEXT_STEP}
    ops = _field_ops(values)
    if found_by_test_case_id:
        ops.append(_link_op("tested_by", found_by_test_case_id))
    wi = await _create(name, "Bug", ops)
    return {"created": wi["id"], "type": "Bug", "title": title, "url": _web_url(name, wi["id"])}


@tool("write")
async def update_work_item(work_item_id: int, fields: dict[str, Any] | None = None,
                           tags_add: str | None = None, tags_remove: str | None = None,
                           expected_revision: int | None = None, preview: bool = True) -> dict:
    """WRITE: change fields of a work item (state, assigned_to, priority, title, any field...).

    fields: friendly or reference names, e.g. {"state": "Active", "assigned_to": "Ali Rezaei"}.
    tags_add / tags_remove: tags separated by ";".
    The preview shows every field as from -> to and the current revision; pass that revision
    as expected_revision when applying, so the update fails if someone changed the item meanwhile.
    """
    wi = await _get_item(work_item_id)
    current = wi.get("fields", {})
    target = _normalize(fields)
    if tags_add or tags_remove:
        tags = [t.strip() for t in (current.get("System.Tags") or "").split(";") if t.strip()]
        for t in (x.strip() for x in (tags_add or "").split(";")):
            if t and t.lower() not in (x.lower() for x in tags):
                tags.append(t)
        removed = {x.strip().lower() for x in (tags_remove or "").split(";") if x.strip()}
        target["System.Tags"] = "; ".join(t for t in tags if t.lower() not in removed)

    changes = []
    for ref, new in target.items():
        old = _display(ref, current.get(ref))
        if str(old or "") != str(new or ""):
            changes.append({"field": ref, "from": old, "to": new})
    summary = {"work_item": work_item_id, "type": current.get("System.WorkItemType"),
               "title": current.get("System.Title"), "revision": wi.get("rev"), "changes": changes}
    if not changes:
        return {**summary, "message": "Nothing to change; the values are already set."}
    if preview:
        return {"preview": True, "action": "update work item", **summary, "next_step": NEXT_STEP}

    ops: list[dict] = []
    if expected_revision is not None:
        ops.append({"op": "test", "path": "/rev", "value": expected_revision})
    ops += _field_ops({c["field"]: target[c["field"]] for c in changes})
    try:
        updated = await _patch(work_item_id, ops)
    except AdoError as exc:
        if expected_revision is not None and ("409" in str(exc) or "412" in str(exc)
                                              or "test" in str(exc).lower()):
            raise AdoError("The work item changed since the preview. Preview again.") from exc
        raise
    return {"updated": work_item_id, "revision": updated.get("rev"), "changes": changes}


@tool("write")
async def link_work_items(source_id: int, target_id: int, link_type: str,
                          comment: str | None = None, preview: bool = True) -> dict:
    """WRITE: link two work items. link_type is seen from the source:
    parent, child, related, tested_by, tests, duplicate, duplicate_of, predecessor, successor.
    Example: link a bug to the test case that found it -> source=bug, target=test case, tested_by.
    """
    src, dst = await _get_item(source_id), await _get_item(target_id)
    op = _link_op(link_type, target_id, comment)
    summary = {"source": {"id": source_id, "title": src["fields"].get("System.Title")},
               "link_type": link_type,
               "target": {"id": target_id, "title": dst["fields"].get("System.Title")}}
    if preview:
        return {"preview": True, "action": "link work items", **summary, "next_step": NEXT_STEP}
    await _patch(source_id, [op])
    return {"linked": True, **summary}


@tool("write")
async def add_comment(work_item_id: int, text: str, preview: bool = True) -> dict:
    """WRITE: add a comment (Discussion) to any work item: test case, bug, task, ..."""
    wi = await _get_item(work_item_id)
    if preview:
        return {"preview": True, "action": "add comment", "work_item": work_item_id,
                "title": wi["fields"].get("System.Title"), "comment": text, "next_step": NEXT_STEP}
    updated = await _patch(work_item_id, [
        {"op": "add", "path": "/fields/System.History", "value": text_to_html(text)}])
    return {"commented": work_item_id, "revision": updated.get("rev"), "comment": text}

# ----------------------------------------------------------------- test management


@tool("write")
async def create_test_case(title: str, steps: list[dict], description: str = "",
                           area_path: str | None = None, iteration_path: str | None = None,
                           assigned_to: str | None = None, priority: int = 2,
                           tags: str | None = None, plan_id: int | None = None,
                           suite_id: int | None = None, project: str | None = None,
                           preview: bool = True) -> dict:
    """WRITE: create a Test Case.

    steps: list of {"action": "...", "expected": "..."}.
    tags: separated by ";". plan_id + suite_id: also add it to that suite.
    """
    values = _normalize({"title": title, "description": description or None,
                         "area_path": area_path, "iteration_path": iteration_path,
                         "assigned_to": assigned_to, "priority": priority, "tags": tags})
    name = resolve_project(project)
    if preview:
        return {"preview": True, "action": "create test case", "project": name, "fields": values,
                "steps": steps, "suite": {"plan_id": plan_id, "suite_id": suite_id} if suite_id else None,
                "next_step": NEXT_STEP}
    ops = _field_ops(values)
    ops.append({"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": build_steps(steps)})
    wi = await _create(name, "Test Case", ops)
    result = {"created": wi["id"], "title": title, "url": _web_url(name, wi["id"])}
    if plan_id and suite_id:
        await send("POST", f"{project_path(name)}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase",
                   [{"workItem": {"id": wi["id"]}}])
        result["added_to_suite"] = suite_id
    return result


@tool("write")
async def add_test_cases_to_suite(plan_id: int, suite_id: int, test_case_ids: list[int],
                                  project: str | None = None, preview: bool = True) -> dict:
    """WRITE: add existing test cases to a test suite."""
    items = await fetch_items(test_case_ids)
    found = [{"id": i["id"], "title": i["fields"].get("System.Title")} for i in items
             if i["fields"].get("System.WorkItemType") == "Test Case"]
    missing = sorted(set(test_case_ids) - {f["id"] for f in found})
    if preview:
        return {"preview": True, "action": "add test cases to suite", "plan_id": plan_id,
                "suite_id": suite_id, "test_cases": found, "not_test_cases_or_missing": missing,
                "next_step": NEXT_STEP}
    if not found:
        raise AdoError("None of the given IDs is a test case.")
    await send("POST", f"{project_path(project)}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase",
               [{"workItem": {"id": f["id"]}} for f in found])
    return {"added": [f["id"] for f in found], "skipped": missing, "suite_id": suite_id}

# ----------------------------------------------------------------- repos & pipelines


@tool("write")
async def add_pull_request_comment(repository: str, pull_request_id: int, text: str,
                                   project: str | None = None, preview: bool = True) -> dict:
    """WRITE: start a new comment thread on a pull request."""
    pr = await get(f"{project_path(project)}/_apis/git/pullrequests/{pull_request_id}")
    if preview:
        return {"preview": True, "action": "comment on pull request", "pull_request": pull_request_id,
                "title": pr.get("title"), "comment": text, "next_step": NEXT_STEP}
    body = {"comments": [{"parentCommentId": 0, "content": text, "commentType": 1}], "status": 1}
    thread = await send("POST", f"{project_path(project)}/_apis/git/repositories/{q(repository)}"
                                f"/pullRequests/{pull_request_id}/threads", body)
    return {"commented": pull_request_id, "thread_id": (thread or {}).get("id")}


@tool("write")
async def run_pipeline(pipeline_id: int, branch: str | None = None, project: str | None = None,
                       preview: bool = True) -> dict:
    """WRITE: queue a run of a pipeline (build definition), optionally on a branch."""
    definition = await get(f"{project_path(project)}/_apis/build/definitions/{pipeline_id}")
    ref = branch_ref(branch) or (definition.get("repository") or {}).get("defaultBranch")
    if preview:
        return {"preview": True, "action": "run pipeline", "pipeline": definition.get("name"),
                "pipeline_id": pipeline_id, "branch": ref, "next_step": NEXT_STEP}
    body: dict[str, Any] = {"definition": {"id": pipeline_id}}
    if ref:
        body["sourceBranch"] = ref
    build = await send("POST", f"{project_path(project)}/_apis/build/builds", body)
    return {"queued": build.get("id"), "number": build.get("buildNumber"),
            "pipeline": definition.get("name"), "branch": ref,
            "url": ((build.get("_links") or {}).get("web") or {}).get("href")}

# ----------------------------------------------------------------- destructive (access level "full")


@tool("full")
async def delete_work_item(work_item_id: int, preview: bool = True) -> dict:
    """DESTRUCTIVE: move a work item to the Recycle Bin (it can be restored from there).
    Test cases cannot be deleted this way; use delete_test_case."""
    wi = await _get_item(work_item_id)
    fields = wi["fields"]
    if fields.get("System.WorkItemType") == "Test Case":
        raise AdoError("This is a Test Case; use delete_test_case.")
    summary = {"work_item": work_item_id, "type": fields.get("System.WorkItemType"),
               "title": fields.get("System.Title"), "state": fields.get("System.State")}
    if preview:
        return {"preview": True, "action": "move to Recycle Bin", **summary, "next_step": NEXT_STEP}
    await raw("DELETE", f"{project_path(fields.get('System.TeamProject'))}/_apis/wit/workitems/{work_item_id}")
    return {"deleted": True, "recycle_bin": True, **summary}


@tool("full")
async def delete_test_case(test_case_id: int, preview: bool = True) -> dict:
    """DESTRUCTIVE / PERMANENT: delete a Test Case together with its test results.
    Test cases do NOT go to the Recycle Bin; this cannot be undone."""
    wi = await _get_item(test_case_id)
    fields = wi["fields"]
    if fields.get("System.WorkItemType") != "Test Case":
        raise AdoError(f"Work item {test_case_id} is not a Test Case.")
    summary = {"test_case": test_case_id, "title": fields.get("System.Title")}
    if preview:
        return {"preview": True, "action": "PERMANENTLY delete test case (no Recycle Bin)",
                **summary, "next_step": NEXT_STEP}
    project = fields.get("System.TeamProject")
    try:
        await raw("DELETE", f"{project_path(project)}/_apis/testplan/testcases/{test_case_id}")
    except AdoError as exc:
        if "HTTP 404" not in str(exc):
            raise
        await raw("DELETE", f"{project_path(project)}/_apis/test/testcases/{test_case_id}")
    return {"deleted": True, "permanent": True, **summary}
