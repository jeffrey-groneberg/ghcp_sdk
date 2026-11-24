"""
Example 10: each session runs as its user, with only your tools (deck slide 24).

The pattern for a multi-user service. The client runs in empty mode (no host
shell, files or default tools) and has no identity of its own. Each session
gets one user's GitHub token and an explicit tool allow-list. Empty mode needs
storage you name, here a per-tenant base directory. In production, pass
github={"token_provider": ...} for short-lived tokens. session.rpc.git_hub_auth
is experimental in SDK 2.0.1.

Run: python examples/10_identity.py
"""

import asyncio
import subprocess
import tempfile

from pydantic import BaseModel, Field

from copilot import CopilotClient, RuntimeConnection, define_tool
from copilot.session_events import ToolExecutionCompleteData


class BuildParams(BaseModel):
    build_id: int = Field(description="CI build number")


@define_tool(description="Failed tests of CI build", skip_permission=True)
async def get_failed_tests(params: BuildParams) -> dict:
    return {"build": params.build_id, "failed": ["test_login"],  # fictional demo data
            "error": "TimeoutError: auth service timed out after 30 s"}


def user_token() -> str:  # stand-in for the signed-in user's OAuth token; never printed
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def on_event(event):
    match event.data:
        case ToolExecutionCompleteData(success=False, error=error):
            print(f"[tool refused] {error.message if error else ''}")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tenant-alice-") as TENANT_HOME:
        client = CopilotClient(
            mode="empty",                                  # no ambient host tools
            runtime=RuntimeConnection.for_default(base_directory=TENANT_HOME),
            github={"use_logged_in_user": False})
        async with client:
            session = await client.create_session(
                github={"token": user_token()},                # runs as this user only
                tools={"definitions": [get_failed_tests],
                       "available_tools": ["custom:*"]},       # explicit allow-list
                events={"on_event": on_event})
            runtime_auth = await client.get_auth_status()
            session_auth = await session.rpc.git_hub_auth.get_status()
            print(f"runtime signed in: {runtime_auth.is_authenticated} · "
                  f"session signed in: {session_auth.is_authenticated} "
                  f"({getattr(session_auth.auth_type, 'value', None)})")
            reply = await session.send_and_wait(
                "Why did build 4711 fail? Then list the files in the current directory. "
                "Answer in at most two sentences.", timeout=120)
            print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
