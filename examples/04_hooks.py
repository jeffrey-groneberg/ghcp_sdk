"""
Example 04: hooks run your code around every tool call.

on_pre_tool_use runs before a tool, on_post_tool_use after a success and
on_post_tool_use_failure after a failure. Returning None means "no opinion".
Example 12 uses a pre-tool hook to deny calls.

Run: python examples/04_hooks.py
"""

import asyncio

from copilot import CopilotClient, ToolSet
from copilot.session import PermissionHandler


async def on_pre_tool_use(hook_input, invocation):
    print(f"[pre]    {hook_input['toolName']}")


async def on_post_tool_use(hook_input, invocation):
    print(f"[post]   {hook_input['toolName']}")


async def on_post_tool_use_failure(hook_input, invocation):
    print(f"[failed] {hook_input['toolName']}")


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            permissions={"on_request": PermissionHandler.approve_all},  # two read-only tools
            tools={"available_tools": ToolSet().add_builtin(["glob", "view"])},
            hooks={"handlers": {
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
                "on_post_tool_use_failure": on_post_tool_use_failure,
            }})
        reply = await session.send_and_wait(
            "List the Python files in the examples folder.", timeout=120)
        print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
