"""
Example 05 — Remote GitHub MCP with GitHub Copilot SDK 1.0.13.

Run: python examples/05_mcp_servers.py
SDK: https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/mcp.md
Tools: https://github.com/github/github-mcp-server/blob/v1.12.0/pkg/github/issues.go

The official HTTPS endpoint needs no Node, npx, Docker or local MCP server.
Model authentication and this MCP server's bearer credential are separate.
"""

import asyncio
import os
import subprocess

from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.session_events import ToolExecutionStartData


TARGET_REPO_OWNER = "github"
TARGET_REPO_NAME = "copilot-sdk"
GITHUB_TOOLS = ["list_issues", "issue_read", "search_issues"]


def github_token() -> str:
    """Resolve credentials only at run time; never print the value."""
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(var, "").strip()
        if token:
            return token
    try:
        token = subprocess.check_output(
            ["gh", "auth", "token", "--hostname", "github.com"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "Cannot obtain a GitHub MCP token. Set GITHUB_TOKEN or GH_TOKEN, "
            "or sign in with `gh auth login --hostname github.com`."
        ) from None
    if not token:
        raise RuntimeError("GitHub MCP authentication returned an empty token.")
    return token


async def main() -> None:
    # No credential lookup or subprocess runs when this module is imported.
    token = github_token()
    mcp_servers = {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-MCP-Readonly": "true",
            },
            # Raw server tool names here; get_issue is now issue_read.
            "tools": GITHUB_TOOLS,
        },
    }
    async with asyncio.timeout(300):
        async with CopilotClient() as client:
            async with await client.create_session(
                # Trusted demo only. Token permissions/server policy still matter.
                on_permission_request=PermissionHandler.approve_all,
                model="gpt-5-mini",
                mcp_servers=mcp_servers,
                # Full-catalog filters use source + server-qualified names.
                available_tools=[f"mcp:github-{name}" for name in GITHUB_TOOLS],
            ) as session:
                def on_event(event) -> None:
                    match event.data:
                        case ToolExecutionStartData(
                            mcp_server_name="github", mcp_tool_name=name,
                        ):
                            # Show tool evidence, not arguments, headers or tokens.
                            print(f"[mcp] github/{name}")

                unsubscribe = session.on(on_event)
                try:
                    reply = await session.send_and_wait(
                        "Use the GitHub MCP server to list the 3 most recently "
                        f"opened issues on {TARGET_REPO_OWNER}/{TARGET_REPO_NAME}. "
                        "For each issue, give its number, title, author and URL. "
                        "If the server fails, report the failure; do not invent data.",
                        timeout=180,
                    )
                    if reply is None:
                        raise RuntimeError("Session became idle without an assistant message.")
                    print(reply.data.content)
                finally:
                    unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
