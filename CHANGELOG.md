# Changelog

## 0.2.0
- Write tools with a two-step preview: `create_work_item`, `create_bug`, `update_work_item`,
  `link_work_items`, `add_comment`, `create_test_case`, `add_test_cases_to_suite`,
  `add_pull_request_comment`, `run_pipeline`.
- `update_work_item` shows every change as from -> to and supports `expected_revision`
  to refuse the update if the item changed after the preview.
- Destructive tools (`full` level): `delete_work_item` (Recycle Bin), `delete_test_case` (permanent).
- `whoami` works with scoped PATs that cannot read connectionData.

## 0.1.0
- 28 read-only tools: work items, WIQL, history, comments, test plans/suites/results,
  iterations and task schedule, repos, branches, files, commits, pull requests,
  pipelines, runs and logs.
- Access levels `read` / `write` / `full`; tools above the level are not registered.
- Azure DevOps Server 2019/2020/2022 and Azure DevOps Services.
