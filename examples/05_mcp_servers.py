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
from copilot.session_events import ToolExecutionCompleteData, ToolExecutionStartData

from _tool_trace import ToolTrace


TARGET_REPO_OWNER = "jeffrey-groneberg"
TARGET_REPO_NAME = "ghcp_sdk"
GITHUB_TOOLS = ["list_issues"]


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


def build_mcp_servers(token: str) -> dict:
    return {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": "Bearer " + token,
                "X-MCP-Readonly": "true",
            },
            "tools": GITHUB_TOOLS,
        },
    }


def is_issue_query(start: ToolExecutionStartData) -> bool:
    return (
        start.mcp_server_name == "github"
        and start.mcp_tool_name == "list_issues"
        and isinstance(start.arguments, dict)
        and start.arguments.get("owner") == TARGET_REPO_OWNER
        and start.arguments.get("repo") == TARGET_REPO_NAME
    )


async def main() -> None:
    token = github_token()
    available_tools = ToolSet().add_mcp("github-list_issues")
    async with asyncio.timeout(300):
        async with CopilotClient() as client:
            async with await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                mcp_servers=build_mcp_servers(token),
                available_tools=available_tools,
            ) as session:
                trace = ToolTrace()

                def on_event(event) -> None:
                    trace.record(event.data)
                    match event.data:
                        case ToolExecutionStartData(tool_call_id=call_id) as start:
                            if is_issue_query(start):
                                print(f"[mcp] github/list_issues started id={call_id}")
                        case ToolExecutionCompleteData(tool_call_id=call_id, success=success):
                            start = trace.started.get(call_id)
                            if start is not None and is_issue_query(start):
                                # Never print headers, arguments, payloads or remote errors.
                                print(
                                    f"[mcp] github/list_issues completed id={call_id} "
                                    f"success={success}"
                                )

                unsubscribe = session.on(on_event)
                try:
                    reply = await session.send_and_wait(
                        "Use the GitHub MCP list_issues tool exactly once, with "
                        f"owner={TARGET_REPO_OWNER!r} and repo={TARGET_REPO_NAME!r}. "
                        "We are reviewing this workshop's examples/01_simple_chat.py "
                        "for error handling and cleanup; issues are context, not "
                        "proof of a code defect. "
                        "List the 3 most recently opened issues on "
                        f"{TARGET_REPO_OWNER}/{TARGET_REPO_NAME}. For each issue, "
                        "give its number, title, author and URL. If the tool fails, "
                        "report that failure; do not answer from memory or invent data. "
                        "An empty issue list is a valid result.",
                        timeout=180,
                    )
                    if reply is None:
                        raise RuntimeError("Session became idle without an assistant message.")
                    queries = [
                        call_id for call_id, start in trace.started.items()
                        if is_issue_query(start)
                    ]
                    if not queries or any(
                        trace.successful_content(call_id) is None for call_id in queries
                    ):
                        raise RuntimeError(
                            "No complete successful GitHub issue query for the target "
                            "repository; an uninvoked, failed or unmatched call is not success."
                        )
                    print(
                        f"[host] MCP_ISSUES_VERIFIED repo={TARGET_REPO_OWNER}/{TARGET_REPO_NAME}"
                    )
                    print(reply.data.content)
                finally:
                    unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
