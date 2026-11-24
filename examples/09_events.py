"""
Example 09: watch the loop, every step is an event (deck slide 18).

Streaming on, two read-only built-in tools, and one handler that prints each
tool start and the answer as it streams in. The demo repository's calc.py has
a planted bug.

Run: python examples/09_events.py
"""

import asyncio

from copilot import CopilotClient, ToolSet
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageDeltaData, ToolExecutionStartData

from _demo_repo import make_demo_repo


def on_event(event):
    match event.data:
        case ToolExecutionStartData(tool_name=name):
            print(f"\n[tool] {name} started")
        case AssistantMessageDeltaData(delta_content=text):
            print(text or "", end="", flush=True)


async def main() -> None:
    repo = make_demo_repo()
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            working_directory=str(repo),
            permissions={"on_request": PermissionHandler.approve_all},  # demo
            tools={"available_tools": ToolSet().add_builtin(["glob", "view"])},
            events={"streaming": True, "on_event": on_event})
        await session.send_and_wait("What does calc.py do?", timeout=120)
        print()


if __name__ == "__main__":
    asyncio.run(main())
