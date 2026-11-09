"""Git repositories: repos, branches, files, commits, pull requests."""

from __future__ import annotations

from ..app import tool
from ..client import CONFIG, AdoError, get, get_all, project_path, q
from ..utils import branch_ref, person, short_ref

VOTES = {10: "approved", 5: "approved with suggestions", 0: "no vote",
         -5: "waiting for author", -10: "rejected"}


def _repo(repository: str, project: str | None) -> str:
    return f"{project_path(project)}/_apis/git/repositories/{q(repository)}"


@tool()
async def list_repositories(project: str | None = None) -> list[dict]:
    """Git repositories (of one project, or of all visible projects if no project is set)."""
    path = f"{q(project or CONFIG.project)}/_apis/git/repositories" if (project or CONFIG.project) \
        else "_apis/git/repositories"
    data = await get(path)
    return [{"name": r.get("name"), "id": r.get("id"), "project": (r.get("project") or {}).get("name"),
             "default_branch": short_ref(r.get("defaultBranch")), "size": r.get("size"),
             "web_url": r.get("webUrl")} for r in data.get("value", [])]


@tool()
async def list_branches(repository: str, name_filter: str | None = None,
                        project: str | None = None) -> list[dict]:
    """Branches of a repository; name_filter matches the start of the branch name."""
    params = {"filter": f"heads/{name_filter or ''}"}
    refs = await get_all(f"{_repo(repository, project)}/refs", params)
    return [{"name": short_ref(r.get("name")), "commit": r.get("objectId"),
             "creator": person(r.get("creator"))} for r in refs]


@tool()
async def browse_repository(repository: str, path: str = "/", branch: str | None = None,
                            project: str | None = None) -> list[dict]:
    """List files and folders in a repository folder (one level)."""
    params = {"scopePath": path, "recursionLevel": "OneLevel"}
    if branch:
        params.update({"versionDescriptor.version": branch, "versionDescriptor.versionType": "branch"})
    data = await get(f"{_repo(repository, project)}/items", params)
    return [{"path": i.get("path"), "folder": i.get("isFolder", False)}
            for i in data.get("value", []) if i.get("path") != path]


@tool()
async def get_file_content(repository: str, path: str, branch: str | None = None,
                           project: str | None = None, max_chars: int = 60000) -> dict:
    """Content of a text file in a repository (truncated to max_chars)."""
    params = {"path": path, "includeContent": "true", "$format": "json"}
    if branch:
        params.update({"versionDescriptor.version": branch, "versionDescriptor.versionType": "branch"})
    data = await get(f"{_repo(repository, project)}/items", params)
    if data.get("isFolder"):
        raise AdoError(f"{path} is a folder; use browse_repository.")
    content = data.get("content") or ""
    return {"path": data.get("path"), "commit": data.get("commitId"),
            "truncated": len(content) > max_chars, "content": content[:max_chars]}


@tool()
async def list_commits(repository: str, branch: str | None = None, author: str | None = None,
                       path: str | None = None, top: int = 30, project: str | None = None) -> list[dict]:
    """Recent commits of a repository, optionally for a branch, author or file/folder path."""
    params: dict = {"searchCriteria.$top": top}
    if branch:
        params.update({"searchCriteria.itemVersion.version": branch,
                       "searchCriteria.itemVersion.versionType": "branch"})
    if author:
        params["searchCriteria.author"] = author
    if path:
        params["searchCriteria.itemPath"] = path
    data = await get(f"{_repo(repository, project)}/commits", params)
    return [{"commit": c.get("commitId", "")[:8], "author": (c.get("author") or {}).get("name"),
             "date": (c.get("author") or {}).get("date"),
             "message": (c.get("comment") or "").strip()} for c in data.get("value", [])]


def _pr_summary(pr: dict) -> dict:
    return {"id": pr.get("pullRequestId"), "title": pr.get("title"), "status": pr.get("status"),
            "draft": pr.get("isDraft", False),
            "repository": (pr.get("repository") or {}).get("name"),
            "created_by": person(pr.get("createdBy")), "created": pr.get("creationDate"),
            "source": short_ref(pr.get("sourceRefName")), "target": short_ref(pr.get("targetRefName")),
            "reviewers": [{"name": person(r), "vote": VOTES.get(r.get("vote", 0), r.get("vote"))}
                          for r in pr.get("reviewers") or []]}


@tool()
async def list_pull_requests(repository: str | None = None, status: str = "active",
                             created_by: str | None = None, target_branch: str | None = None,
                             project: str | None = None, top: int = 50) -> list[dict]:
    """Pull requests of a project (or one repository).
    status: active, completed, abandoned or all. created_by: part of a name."""
    params = {"searchCriteria.status": status, "$top": top}
    if target_branch:
        params["searchCriteria.targetRefName"] = branch_ref(target_branch)
    path = (f"{_repo(repository, project)}/pullrequests" if repository
            else f"{project_path(project)}/_apis/git/pullrequests")
    data = await get(path, params)
    prs = [_pr_summary(pr) for pr in data.get("value", [])]
    if created_by:
        prs = [p for p in prs if created_by.lower() in (p["created_by"] or "").lower()]
    return prs


@tool()
async def get_pull_request(pull_request_id: int, project: str | None = None) -> dict:
    """Details of a pull request: description, reviewers and votes, linked work items."""
    pr = await get(f"{project_path(project)}/_apis/git/pullrequests/{pull_request_id}")
    out = _pr_summary(pr)
    out["description"] = pr.get("description")
    out["merge_status"] = pr.get("mergeStatus")
    repo_id = (pr.get("repository") or {}).get("id")
    if repo_id:
        try:
            refs = await get(f"{project_path(project)}/_apis/git/repositories/{repo_id}"
                             f"/pullRequests/{pull_request_id}/workitems")
            out["work_items"] = [int(w["id"]) for w in refs.get("value", [])]
        except AdoError:
            pass
    return out
