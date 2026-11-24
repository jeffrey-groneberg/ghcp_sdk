# 05 · MCP servers

Deck slide 20 · [Source](05_mcp_servers.py) · [MCP](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/mcp.md)

GitHub's remote MCP server, read-only, with exactly two of its tools.

## Run it

```bash
python examples/05_mcp_servers.py                            # microsoft/copilot-sdk, as on the slide
python examples/05_mcp_servers.py github/github-mcp-server   # or another repository
```

## How it works

```python
token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
github = {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
          "headers": {"Authorization": f"Bearer {token}",
                      "X-MCP-Readonly": "true"},
          "tools": ["list_issues", "issue_read"]}
session = await client.create_session(
    permissions={"on_request": PermissionHandler.approve_all},  # read-only
    mcp={"servers": {"github": github}},
    tools={"available_tools": ToolSet().add_mcp("github-list_issues")
                                       .add_mcp("github-issue_read")}, ...)
```

- An MCP server gets only the headers you give it. The example passes the
  GitHub CLI's token, read at run time and never printed.
- `X-MCP-Readonly: true` asks the server for read-only tools, and `tools`
  loads only two of them.
- In the session's catalog, MCP tools are named `<server>-<tool>`, so the
  allow-list names `github-list_issues` and `github-issue_read`.
- `approve_all` is acceptable here because both tools only read.

## Output from a live run

```text
[mcp] github/list_issues
- microsoft/copilot-sdk#2842 — Powershell ShellId falls through to "Microsoft.PowerShell", resulting in default profile loading
- microsoft/copilot-sdk#2827 — Allow Rust callers to omit the automatic post-resume skill reload
- microsoft/copilot-sdk#2816 — Preserve MCP embedded text resources and resource_link blocks in tool results
```

## Watch out

- If your account belongs to an organization that enforces SAML single
  sign-on, such as microsoft, the token must be authorized for it, or the
  server can't read that organization's repositories, public ones included.
  The Codespace's token isn't authorized: run
  `gh issue list -R microsoft/copilot-sdk` and open the link it prints, or
  pass another repository.
