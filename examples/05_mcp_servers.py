"""
Example 05: MCP servers plug in with an exact tool allow-list (deck slide 20).

GitHub's remote MCP server, read-only, with exactly two tools. MCP tools are
named <server>-<tool>: github-list_issues and github-issue_read. The MCP server
needs its own GitHub token; this reads the GitHub CLI's and never prints it.

Run: python examples/05_mcp_servers.py
"""

import asyncio
import subprocess

from copilot import CopilotClient, ToolSet
from copilot.session import PermissionHandler
from copilot.session_events import ToolExecutionStartData


def on_event(event):
    match event.data:
        case ToolExecutionStartData(mcp_server_name="github", mcp_tool_name=name):
            print(f"[mcp] github/{name}")


async def main() -> None:
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    github = {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
              "headers": {"Authorization": f"Bearer {token}",
                          "X-MCP-Readonly": "true"},
              "tools": ["list_issues", "issue_read"]}
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            permissions={"on_request": PermissionHandler.approve_all},  # read-only
            mcp={"servers": {"github": github}},
            tools={"available_tools": ToolSet().add_mcp("github-list_issues")
                                               .add_mcp("github-issue_read")},
            events={"on_event": on_event})
        reply = await session.send_and_wait(
            'List the 3 newest open issues labeled "enhancement" in microsoft/copilot-sdk: '
            "number and title only.", timeout=180)
        print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
