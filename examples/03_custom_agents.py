"""
Example 03 — Custom agents

A *custom agent* is a named persona you bundle with the session: a system
prompt, an allowlist of tools, and a description. The model can be told
to "act as" one of them and is restricted to that agent's toolset.

This demo defines two agents in the same session and switches between
them mid-conversation:

    researcher  → answers questions about the codebase, never edits
    reviewer    → critiques a file for bugs / clarity

Concepts covered:
  * Declaring multiple agents via `custom_agents=[...]`
  * Picking the initial agent with `agent="..."`
  * Switching agents at runtime with `session.rpc.agent.select(...)`

Run:
    python examples/03_custom_agents.py
"""

import asyncio

from copilot import CopilotClient
from copilot.generated.rpc import AgentSelectRequest
from copilot.session import PermissionHandler


# Each agent is a plain dict. The most important keys are:
#   name        → identifier you use to select the agent later
#   prompt      → the system prompt that shapes its behaviour
#   tools       → built-in tool names this agent is *allowed* to use
#                 (`grep`, `glob`, `view`, `bash`, `write`, ...)
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
    async with CopilotClient() as client:
        # `custom_agents=AGENTS` registers our personas with the session.
        # `agent="researcher"` makes that one the active agent for the first
        # turn — without this kwarg the default agent would be used.
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            custom_agents=AGENTS,
            agent="researcher",
        ) as session:

            # First turn handled by the researcher. Note the longer timeout —
            # this agent has to do a few grep + view tool calls before it can
            # answer, so 60s (the default) is sometimes too short.
            reply = await session.send_and_wait(
                "What programming language is this project written in?",
                timeout=120,
            )
            if reply:
                print("Researcher:", reply.data.content, "\n")

            # Mid-conversation agent switch. `session.rpc` exposes the
            # underlying JSON-RPC namespaces (`agent`, `permissions`,
            # `tools`, `model`, ...). Calling `.agent.select(...)` swaps
            # the active persona; the next prompt will be answered by the
            # reviewer, but the conversation history is preserved.
            await session.rpc.agent.select(AgentSelectRequest(name="reviewer"))

            reply = await session.send_and_wait(
                "Review examples/01_simple_chat.py for error handling issues.",
                timeout=120,
            )
            if reply:
                print("Reviewer:", reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
