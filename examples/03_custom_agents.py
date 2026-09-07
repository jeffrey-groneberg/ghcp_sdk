"""
Example 03 — Custom agents

A *custom agent* is a named persona you bundle with the session: a system
prompt, tool scope, and a description. This uses stable SDK 1.0.13.
Tool filters narrow exposure; they are not an operating-system sandbox.

This demo defines two agents in the same session and switches between
them mid-conversation:

    researcher  → answers questions about the codebase, never edits
    reviewer    → critiques a file for bugs / clarity

Concepts covered:
  * Declaring multiple agents via `custom_agents=[...]`
  * Picking the initial agent with `agent="..."`
  * Listing registered personas with `session.rpc.agent.list()`
  * Inspecting the active persona with `session.rpc.agent.get_current()`
  * Switching agents at runtime with `session.rpc.agent.select(...)`

Run:
    python examples/03_custom_agents.py
"""

import asyncio

from copilot import CopilotClient
from copilot.rpc import AgentSelectRequest
from copilot.session import PermissionHandler


# Each agent is a plain dict. The most important keys are:
#   name        → identifier you use to select the agent later
#   prompt      → the system prompt that shapes its behaviour
#   tools       → built-in tool names this agent is *allowed* to use
#                 (`grep`, `glob`, `view`, `bash`, `edit`, ...)
#   description → shown to the model when listing available agents
AGENTS = [
    {
        "name": "researcher",
        "description": "Read-only code researcher.",
        "tools": ["grep", "glob", "view"],
        "prompt": "You explore code and answer questions. Never modify files.",
    },
    {
        "name": "reviewer",
        "description": "Code reviewer focused on bugs and security.",
        "tools": ["grep", "glob", "view"],
        "prompt": "You review code for bugs, security issues, and clarity.",
    },
]


async def main() -> None:
    async with asyncio.timeout(360):
        await run_conversation()


async def run_conversation() -> None:
    async with CopilotClient() as client:
        # `custom_agents=AGENTS` registers our personas with the session.
        # `agent="researcher"` makes that one the active agent for the first
        # turn — without this kwarg the default agent would be used.
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-5-mini",
            custom_agents=AGENTS,
            agent="researcher",
            # Apply the read-tool scope session-wide as well as per persona.
            # approve_all is acceptable only in a trusted, non-sensitive checkout.
            available_tools=["builtin:grep", "builtin:glob", "builtin:view"],
        ) as session:

            # `session.rpc` is the SDK's window onto the JSON-RPC server.
            # `agent.list()` returns every persona registered with the session
            # so we can confirm both AGENTS were accepted.
            listing = await session.rpc.agent.list()
            print("Registered agents:",
                  ", ".join(a.name for a in listing.agents))

            # `agent.get_current()` tells us which persona is active. This is
            # the cheap, definitive way to verify the swap actually happened
            # (responses alone are circumstantial evidence).
            current = await session.rpc.agent.get_current()
            if current.agent is None or current.agent.name != "researcher":
                raise RuntimeError("The researcher persona was not selected.")
            print(f"Active persona: {current.agent.name}\n")

            # First turn handled by the researcher. Note the longer timeout —
            # this agent has to do a few grep + view tool calls before it can
            # answer, so 60s (the default) is sometimes too short.
            reply = await session.send_and_wait(
                "What programming language is this project written in?",
                timeout=120,
            )
            if reply is None:
                raise RuntimeError("Researcher became idle without an assistant message.")
            print("Researcher:", reply.data.content, "\n")

            # Mid-conversation agent switch. Calling `.agent.select(...)`
            # swaps the active persona; the next prompt will be answered by
            # the reviewer, but the conversation history is preserved.
            await session.rpc.agent.select(AgentSelectRequest(name="reviewer"))

            # Confirm the swap before we send anything else.
            current = await session.rpc.agent.get_current()
            if current.agent is None or current.agent.name != "reviewer":
                raise RuntimeError("The reviewer persona was not selected.")
            print(f"--- swapped --- Active persona: {current.agent.name}\n")

            reply = await session.send_and_wait(
                "Review examples/01_simple_chat.py for error handling issues.",
                timeout=120,
            )
            if reply is None:
                raise RuntimeError("Reviewer became idle without an assistant message.")
            print("Reviewer:", reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
