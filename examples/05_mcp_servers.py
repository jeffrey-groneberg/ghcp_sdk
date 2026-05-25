"""
Example 05 — MCP servers (remote GitHub MCP server)

The [Model Context Protocol](https://modelcontextprotocol.io) is the
standard plug-in format for LLM tools. Hundreds of community servers
already exist; in this demo we talk to the *official* remote GitHub MCP
server hosted by GitHub itself:

    https://api.githubcopilot.com/mcp/

No install, no Docker, no `npx` — just an HTTPS endpoint. The agent
gains access to GitHub-aware tools (`list_issues`, `get_pull_request`,
`search_code`, ...) which we use to ask about live issues in the
`github/copilot-sdk` repo. Because the issues are newer than the model's
training cutoff, the answer can only come from a real MCP tool call.

Concepts covered:
  * Configuring an `http` MCP server (vs the `local` / stdio flavour)
  * Authenticating remote MCP servers with a `Authorization: Bearer`
    header
  * Narrowing exposure with an explicit `tools` allowlist
  * Discovering tokens with `gh auth token` as a sensible fallback

Run:
    python examples/05_mcp_servers.py
"""

import asyncio
import os
import subprocess

from copilot import CopilotClient
from copilot.session import PermissionHandler


# The famous public repo we will ask about. Swap for anything you like.
TARGET_REPO_OWNER = "github"
TARGET_REPO_NAME = "copilot-sdk"


def github_token() -> str:
    """Return a GitHub token from env or fall back to `gh auth token`.

    Order:
      1. `GITHUB_TOKEN` env var (CI-friendly)
      2. `GH_TOKEN` env var (gh CLI convention)
      3. `gh auth token` (uses the user's keyring login)
    """
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        return subprocess.check_output(
            ["gh", "auth", "token"], text=True
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN or run `gh auth login`."
        ) from exc


# MCP server configuration.
#
#   type     'http'  — talk to a remote MCP server over HTTPS
#                     ('local' / 'stdio' = spawn a subprocess instead)
#   url      the official remote GitHub MCP server
#   headers  bearer token auth (PAT or `gh auth token` output works)
#   tools    explicit allowlist — *only* these tools are exposed to the
#            agent. Use ['*'] to expose everything the server offers.
MCP_SERVERS = {
    "github": {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": f"Bearer {github_token()}"},
        "tools": ["list_issues", "get_issue", "search_issues"],
    },
}


async def main() -> None:
    async with CopilotClient() as client:
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            mcp_servers=MCP_SERVERS,
        ) as session:
            # The MCP server is the only way the agent can see real GitHub
            # data — without it, the model would have to guess (and likely
            # hallucinate) recent issue titles.
            reply = await session.send_and_wait(
                "Use the GitHub MCP server to list the 3 most recently "
                f"opened issues on {TARGET_REPO_OWNER}/{TARGET_REPO_NAME}. "
                "For each issue, give me the number, title, and author.",
                timeout=180,
            )
            if reply:
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
