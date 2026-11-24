"""
Example 03: custom agents give each role its own tools (deck slide 21).

A reviewer (read-only tools) finds the bug in a disposable demo repository,
then a fixer (view and edit) fixes it in the same session. The agent switch,
session.rpc.agent.select with AgentSelectRequest, is experimental in SDK 2.0.1.

Run: python examples/03_custom_agents.py
"""

import asyncio
import subprocess

from copilot import CopilotClient
from copilot.rpc import AgentSelectRequest
from copilot.session import PermissionHandler

from _demo_repo import make_demo_repo

reviewer = {"name": "reviewer", "description": "Finds bugs, never edits",
            "prompt": "Review only.", "tools": ["view", "grep", "glob"]}
fixer = {"name": "fixer", "description": "Fixes one bug, minimal edit",
         "prompt": "Make the smallest fix.", "tools": ["view", "edit"]}


async def main() -> None:
    repo = make_demo_repo()  # calc.py: add(a, b) returns a - b
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            working_directory=str(repo),
            permissions={"on_request": PermissionHandler.approve_all},  # demo repo
            agents={"definitions": [reviewer, fixer], "selected": "reviewer"})
        bug = await session.send_and_wait("Find the bug in calc.py.", timeout=180)
        print("reviewer:", bug.data.content if bug else "no answer")
        await session.rpc.agent.select(AgentSelectRequest(name="fixer"))
        fix = await session.send_and_wait("Fix that bug.", timeout=180)
        print("fixer:", fix.data.content if fix else "no answer")
    diff = subprocess.run(["git", "diff", "--unified=0"], cwd=repo, capture_output=True, text=True)
    print(diff.stdout)


if __name__ == "__main__":
    asyncio.run(main())
