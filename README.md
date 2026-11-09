# Azure DevOps MCP Server (Server & Services)

An [MCP](https://modelcontextprotocol.io) server that connects Claude (and other MCP clients) to
**Azure DevOps Server (on-premises: 2019, 2020, 2022)** and **Azure DevOps Services (cloud)**.

- Uses **your own Personal Access Token**: you see exactly what your account can see.
- **Read-only by default.** Write and delete tools are only loaded when you choose a higher access level.
- Covers work items, test plans, repos, pull requests and pipelines.

## Access levels

| Level | What is enabled |
|---|---|
| `read` (default) | All search and read tools |
| `write` | + create/update work items and bugs, links, comments, test cases, suites, PR comments, run pipelines |
| `full` | + deletes (`delete_work_item` to the Recycle Bin, `delete_test_case` permanently) |

Tools above your level are **not registered at all**, so the model cannot see or call them.

## How changes are approved

Every write tool works in two steps:

1. Called with `preview=True` (the default) it **changes nothing** and returns exactly what would
   happen, e.g. `State: New -> Active`, `Priority: 2 -> 1`.
2. Only after you approve, it is called again with `preview=False`.

`update_work_item` also returns the current revision; passing it back as `expected_revision`
makes the update fail if someone else changed the item in between.

On top of that, write tools are annotated `readOnlyHint: false` and delete tools
`destructiveHint: true`, so your MCP client asks for permission before each call.
**Do not choose "Always allow" for write or delete tools.**

## Tools

| Area | Read | Write (`write`) | Delete (`full`) |
|---|---|---|---|
| Connection | `whoami`, `list_projects`, `list_teams`, `list_team_members` | | |
| Work items | `search_work_items`, `query_wiql`, `get_work_item`, `get_work_item_history`, `get_comments`, `list_work_item_types` | `create_work_item`, `create_bug`, `update_work_item`, `link_work_items`, `add_comment` | `delete_work_item` |
| Test | `search_test_cases`, `get_test_case`, `list_test_plans`, `list_test_suites`, `get_suite_test_results` | `create_test_case`, `add_test_cases_to_suite` | `delete_test_case` |
| Boards | `list_iterations`, `get_task_schedule` | | |
| Repos | `list_repositories`, `list_branches`, `browse_repository`, `get_file_content`, `list_commits`, `list_pull_requests`, `get_pull_request` | `add_pull_request_comment` | |
| Pipelines | `list_pipelines`, `list_pipeline_runs`, `get_pipeline_run`, `get_pipeline_log` | `run_pipeline` | |

## Create a Personal Access Token

User settings → Personal access tokens → New token. Suggested scopes:

| Scope | read | write / full |
|---|---|---|
| Work Items | Read | Read & Write |
| Test Management | Read | Read & Write |
| Code | Read | Read & Write (PR comments) |
| Build | Read | Read & Execute (run pipelines) |
| Project and Team | Read | Read |

Use a short expiry and never share your PAT. Everything you do through this server is recorded
in Azure DevOps under your name.

## Install

### Claude Desktop (.mcpb, one click)

Double-click `ado-mcp-server.mcpb` (or drag it into Claude Desktop) and fill in the form.

### Any MCP client (Claude Code, VS Code, Cursor, ...)

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "uvx",
      "args": ["ado-mcp-server"],
      "env": {
        "ADO_URL": "https://dev.azure.com/YourOrg",
        "ADO_PAT": "...",
        "ADO_PROJECT": "MyProject",
        "ADO_ACCESS_LEVEL": "read"
      }
    }
  }
}
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ADO_URL` | (required) | `https://server/Collection` or `https://dev.azure.com/Org` |
| `ADO_PAT` | (required) | Personal Access Token |
| `ADO_PROJECT` | | Default project |
| `ADO_TEAM` | `<project> Team` | Default team for iteration tools |
| `ADO_ACCESS_LEVEL` | `read` | `read`, `write` or `full` |
| `ADO_API_VERSION` | `7.0` | `7.0` Server 2022 / cloud, `6.0` Server 2020, `5.0` Server 2019 |
| `ADO_IGNORE_PROXY` | `false` | Ignore `HTTP(S)_PROXY` (useful for internal servers) |
| `ADO_VERIFY_SSL` | `true` | SSL verification |
| `ADO_CA_BUNDLE` | | Path to a company CA certificate (.pem) |

## Development

```bash
uv run --group dev pytest -q             # tests
uv run mcp dev src/ado_mcp/server.py     # MCP Inspector
npx @anthropic-ai/mcpb pack . ado-mcp-server.mcpb
```

## License

MIT
