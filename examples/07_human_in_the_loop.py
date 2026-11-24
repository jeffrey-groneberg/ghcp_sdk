"""
Example 07: a human in the loop.

The agent asks you a question through its built-in ask_user tool, then wants to
run one shell command. Your code approves only that exact command, and only
after you type y. PermissionDecisionApproveOnce and PermissionDecisionReject
are experimental in SDK 2.0.1.

Run: python examples/07_human_in_the_loop.py
"""

import asyncio
import sys

from copilot import CopilotClient, ToolSet
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject

SHELL = "powershell" if sys.platform == "win32" else "bash"
COMMAND = "echo Hello from the Copilot SDK"


async def on_user_input(request, invocation):  # the agent called ask_user
    answer = await asyncio.to_thread(input, f"\n[agent asks] {request['question']}\n> ")
    return {"answer": answer, "wasFreeform": True}


async def on_permission(request, invocation):  # the exact command, then a human yes
    command = getattr(request, "full_command_text", "")
    if command != COMMAND:
        print(f"[approval] rejected: {command or request}")
        return PermissionDecisionReject(feedback=f"Only `{COMMAND}` is allowed.")
    answer = await asyncio.to_thread(input, f"\n[approval] run `{command}`? [y/N] ")
    if answer.strip().lower() == "y":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="The user said no.")


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            tools={"available_tools": ToolSet().add_builtin(["ask_user", SHELL])},
            permissions={"on_request": on_permission},
            interaction={"on_user_input_request": on_user_input})
        reply = await session.send_and_wait(
            f"Ask me for my name with ask_user. Then run exactly this command with {SHELL}, "
            f"once: {COMMAND}\nFinally greet me by name and report the command's output, "
            "or that it was not approved.", timeout=300)
        print(f"\n{reply.data.content if reply else 'no answer'}")


if __name__ == "__main__":
    asyncio.run(main())
