"""
Example 05 — Remote GitHub MCP with GitHub Copilot SDK 1.0.13.

Run: python examples/05_mcp_servers.py
SDK: https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/mcp.md
Tools: https://github.com/github/github-mcp-server/blob/v1.12.1/pkg/github/issues.go

Copilot model authentication and remote MCP authentication are separate.
The token is resolved at run time and never printed.
"""

import asyncio
import os
import subprocess

from copilot import CopilotClient, ToolSet
from copilot.session import PermissionHandler
from copilot.session_events import ToolExecutionStartData


TARGET_REPO_OWNER = "github"
TARGET_REPO_NAME = "copilot-sdk"
GITHUB_TOOLS = ["list_issues", "issue_read", "search_issues"]


def github_token() -> str:
    """Resolve a GitHub token for the remote MCP server without logging it."""
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
    token = github_token()
    available_tools = ToolSet()
    for name in GITHUB_TOOLS:
        available_tools.add_mcp(f"github-{name}")
    mcp_servers = {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-MCP-Readonly": "true",
            },
            "tools": GITHUB_TOOLS,
        },
    }

    async with asyncio.timeout(300):
        async with CopilotClient() as client:
            async with await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                mcp_servers=mcp_servers,
                available_tools=available_tools,
            ) as session:
                saw_mcp_call = False

                def on_event(event) -> None:
                    nonlocal saw_mcp_call
                    match event.data:
                        case ToolExecutionStartData(
                            mcp_server_name="github", mcp_tool_name=name,
                        ):
                            saw_mcp_call = True
                            print(f"[mcp] github/{name}")

                unsubscribe = session.on(on_event)
                try:
                    reply = await session.send_and_wait(
                        f"List 3 recent open issues on {TARGET_REPO_OWNER}/{TARGET_REPO_NAME}.",
                        timeout=180,
                    )
                    if reply is None:
                        raise RuntimeError("Session became idle without an assistant message.")
                    if not saw_mcp_call:
                        raise RuntimeError(
                            "The assistant answered without invoking the GitHub MCP server."
                        )
                    print(reply.data.content)
                finally:
                    unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
